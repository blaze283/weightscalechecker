# --- BEGIN: smart_device_integration.py (drop into your app) ---
import streamlit as st
import requests
import urllib.parse
import json
import datetime
import base64

# Database helpers expected:
#   db_execute(query, params=(), fetch=False) -> returns rows if fetch=True
# The app we built earlier had this helper. If yours is named differently adapt accordingly.

# Create token storage table if not exists
def init_token_table(db_execute):
    db_execute("""
        CREATE TABLE IF NOT EXISTS device_tokens (
            username TEXT PRIMARY KEY,
            fitbit_access TEXT,
            fitbit_refresh TEXT,
            fitbit_expires INTEGER,
            google_access TEXT,
            google_refresh TEXT,
            google_expires INTEGER
        )
    """, ())

# Save tokens
def save_fitbit_tokens(db_execute, username, access_token, refresh_token, expires_in):
    expires_at = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)).timestamp())
    # Upsert
    db_execute("""
        INSERT INTO device_tokens (username, fitbit_access, fitbit_refresh, fitbit_expires)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            fitbit_access=excluded.fitbit_access,
            fitbit_refresh=excluded.fitbit_refresh,
            fitbit_expires=excluded.fitbit_expires
    """, (username, access_token, refresh_token, expires_at))

def save_google_tokens(db_execute, username, access_token, refresh_token, expires_in):
    expires_at = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)).timestamp())
    db_execute("""
        INSERT INTO device_tokens (username, google_access, google_refresh, google_expires)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            google_access=excluded.google_access,
            google_refresh=excluded.google_refresh,
            google_expires=excluded.google_expires
    """, (username, access_token, refresh_token, expires_at))

def get_tokens(db_execute, username):
    rows = db_execute("SELECT fitbit_access, fitbit_refresh, fitbit_expires, google_access, google_refresh, google_expires FROM device_tokens WHERE username=?", (username,), fetch=True)
    if rows:
        a, r, ae, ga, gr, ge = rows[0]
        return {
            "fitbit": {"access": a, "refresh": r, "expires": ae},
            "google": {"access": ga, "refresh": gr, "expires": ge}
        }
    return {"fitbit": None, "google": None}

# -------- FITBIT OAUTH & API --------
def build_fitbit_auth_url(client_id, redirect_uri, scopes=("activity","heartrate","sleep")):
    scopes_str = " ".join(scopes)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes_str,
        "expires_in": "604800"  # maximal token lifetime (optional)
    }
    return "https://www.fitbit.com/oauth2/authorize?" + urllib.parse.urlencode(params)

def fitbit_exchange_code(client_id, client_secret, code, redirect_uri):
    """
    Exchanges authorization code for tokens with Fitbit.
    Returns dict with access_token, refresh_token, expires_in.
    """
    url = "https://api.fitbit.com/oauth2/token"
    auth = (client_id, client_secret)
    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(url, data=data, auth=auth, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def fitbit_refresh_token(client_id, client_secret, refresh_token):
    url = "https://api.fitbit.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    r = requests.post(url, data=data, auth=(client_id, client_secret), headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=10)
    r.raise_for_status()
    return r.json()

def fitbit_get_daily_activity(access_token, date_str=None):
    # date_str format YYYY-MM-DD or use today
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    url = f"https://api.fitbit.com/1/user/-/activities/date/{date_str}.json"
    r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if r.status_code == 401:
        raise PermissionError("Unauthorized (token expired?)")
    r.raise_for_status()
    return r.json()

# -------- GOOGLE OAUTH (Google Fit) --------
def build_google_auth_url(client_id, redirect_uri, scopes=None):
    if scopes is None:
        scopes = [
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/fitness.activity.write",
            "https://www.googleapis.com/auth/fitness.heart_rate.read",
            "https://www.googleapis.com/auth/fitness.body.read",
        ]
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent"
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

def google_exchange_code(client_id, client_secret, code, redirect_uri):
    url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()

def google_refresh_token(client_id, client_secret, refresh_token):
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()

def google_get_steps(access_token, dataset_start_nanos=None, dataset_end_nanos=None):
    """
    Example: use Google Fitness REST API (aggregates endpoint) to fetch aggregated steps.
    Docs: https://developers.google.com/fit/rest/v1/reference/users/dataset
    Simpler approach: use "aggregate" endpoint:
    POST https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate
    Body: JSON with dataSourceIds or dataTypeName "com.google.step_count.delta"
    Here we request daily steps for last day if dataset times not provided.
    """
    url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    now = int(datetime.datetime.utcnow().timestamp() * 1000)
    if dataset_end_nanos:
        end_ms = int(dataset_end_nanos / 1_000_000)
    else:
        end_ms = now
    if dataset_start_nanos:
        start_ms = int(dataset_start_nanos / 1_000_000)
    else:
        start_ms = end_ms - 24*60*60*1000
    body = {
        "aggregateBy": [{"dataTypeName":"com.google.step_count.delta"}],
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms,
        "bucketByTime": {"durationMillis": 86400000}
    }
    r = requests.post(url, headers={"Authorization":f"Bearer {access_token}", "Content-Type":"application/json"}, json=body, timeout=10)
    if r.status_code == 401:
        raise PermissionError("Unauthorized (token expired?)")
    r.raise_for_status()
    return r.json()

# ---------------- UI PAGE: Connect Devices ----------------
def connect_devices_page(db_execute):
    st.header("🔗 Connect Smartwatch / Health Platform")
    if not st.session_state.logged_in:
        st.info("Sign in to connect a device.")
        return

    init_token_table(db_execute)

    username = st.session_state.username
    st.write("You can connect Fitbit and Google Fit. After connecting you'll be able to import steps, heart rate and workout data.")

    # ---- Config input or env fallback ----
    st.markdown("### App credentials (required for OAuth flows)")
    col1, col2 = st.columns(2)
    with col1:
        fitbit_client_id = st.text_input("Fitbit Client ID", value=st.secrets.get("FITBIT_CLIENT_ID",""), help="Set in Streamlit secrets or paste here.")
        fitbit_client_secret = st.text_input("Fitbit Client Secret", value=st.secrets.get("FITBIT_CLIENT_SECRET",""), type="password")
    with col2:
        google_client_id = st.text_input("Google Client ID", value=st.secrets.get("GOOGLE_CLIENT_ID",""))
        google_client_secret = st.text_input("Google Client Secret", value=st.secrets.get("GOOGLE_CLIENT_SECRET",""), type="password")

    # build redirect URI - Streamlit apps use the same URL + query params. User must add exact redirect in provider console.
    base_url = st.experimental_get_query_params().get("_origin", [""])[0] or st.experimental_get_query_params().get("redirect_uri", [""])[0] or ""
    if not base_url:
        # best-effort derive from server host; when running locally use http://localhost:8501/
        base_url = st.experimental_get_query_params().get("url", [""])[0] or ""
    if not base_url:
        # fallback - tell user to use this as redirect
        st.info("IMPORTANT: set your OAuth redirect URI to your Streamlit app root URL, e.g. `http://localhost:8501/` or your deployed app URL.")
        redirect_uri = st.text_input("OAuth Redirect URI (exact)", value="http://localhost:8501/")
    else:
        redirect_uri = base_url

    st.markdown("---")
    st.subheader("Fitbit (OAuth 2.0)")
    st.write("Click to open Fitbit authorization. After approving, Fitbit redirects back with a code which this page will capture and exchange for tokens.")
    if fitbit_client_id and redirect_uri:
        auth_url = build_fitbit_auth_url(fitbit_client_id, redirect_uri)
        st.markdown(f"[🔗 Open Fitbit Authorization]({auth_url})")
    else:
        st.info("Provide Fitbit Client ID above to generate auth link.")

    st.subheader("Google Fit (OAuth 2.0)")
    if google_client_id and redirect_uri:
        google_url = build_google_auth_url(google_client_id, redirect_uri)
        st.markdown(f"[🔗 Open Google Authorization]({google_url})")
    else:
        st.info("Provide Google Client ID above to generate Google auth link.")

    st.markdown("---")
    st.subheader("Callback handling / Paste code manually")
    params = st.experimental_get_query_params()
    # Fitbit returns `code` in query on successful auth (authorization code flow)
    fitbit_code = params.get("code", [None])[0]
    # Google also returns `code` similarly
    google_code = params.get("code", [None])[0]

    # If we detected a code in query params try to exchange it
    if fitbit_code and fitbit_client_id and fitbit_client_secret:
        st.success("Detected `code` in URL — attempting to exchange for Fitbit tokens...")
        try:
            token_resp = fitbit_exchange_code(fitbit_client_id, fitbit_client_secret, fitbit_code, redirect_uri)
            access_token = token_resp["access_token"]
            refresh_token = token_resp["refresh_token"]
            expires_in = token_resp.get("expires_in", 28800)
            save_fitbit_tokens(db_execute, username, access_token, refresh_token, expires_in)
            st.success("Fitbit connected and tokens saved!")
        except Exception as e:
            st.error(f"Fitbit token exchange failed: {e}")

    if google_code and google_client_id and google_client_secret:
        st.success("Detected `code` in URL — attempting to exchange for Google tokens...")
        try:
            token_resp = google_exchange_code(google_client_id, google_client_secret, google_code, redirect_uri)
            access_token = token_resp["access_token"]
            refresh_token = token_resp.get("refresh_token")
            expires_in = token_resp.get("expires_in", 3600)
            save_google_tokens(db_execute, username, access_token, refresh_token, expires_in)
            st.success("Google connected and tokens saved!")
        except Exception as e:
            st.error(f"Google token exchange failed: {e}")

    st.markdown("---")
    st.subheader("Manual token fallback (paste access token here for quick tests)")
    colA, colB = st.columns(2)
    with colA:
        manual_fitbit = st.text_input("Paste Fitbit access token (optional)")
        if st.button("Save manual Fitbit token"):
            if manual_fitbit:
                save_fitbit_tokens(db_execute, username, manual_fitbit, None, 3600)
                st.success("Saved manual Fitbit token (demo).")
    with colB:
        manual_google = st.text_input("Paste Google access token (optional)")
        if st.button("Save manual Google token"):
            if manual_google:
                save_google_tokens(db_execute, username, manual_google, None, 3600)
                st.success("Saved manual Google token (demo).")

    st.markdown("---")
    st.subheader("Fetch latest data")
    tokens = get_tokens(db_execute, username)
    # Fitbit sample fetch
    if tokens and tokens["fitbit"] and tokens["fitbit"]["access"]:
        st.markdown("**Fitbit data (today)**")
        try:
            fit_json = fitbit_get_daily_activity(tokens["fitbit"]["access"])
            steps = fit_json.get("summary", {}).get("steps")
            calories = fit_json.get("summary", {}).get("caloriesOut")
            st.metric("Steps", steps or "—")
            st.metric("Calories burned", calories or "—")
        except PermissionError:
            st.warning("Fitbit token likely expired — try refreshing token manually or re-connect.")
        except Exception as e:
            st.error("Fitbit fetch error: " + str(e))
    else:
        st.info("No Fitbit token saved for this user.")

    # Google sample fetch (steps via aggregate)
    if tokens and tokens["google"] and tokens["google"]["access"]:
        st.markdown("**Google Fit data (last 24h)**")
        try:
            agg = google_get_steps(tokens["google"]["access"])
            # parse aggregate result for steps
            total_steps = 0
            for bucket in agg.get("bucket", []):
                for dataset in bucket.get("dataset", []):
                    for point in dataset.get("point", []):
                        for val in point.get("value", []):
                            total_steps += val.get("intVal", 0)
            st.metric("Steps (24h)", total_steps)
        except PermissionError:
            st.warning("Google token likely expired — try refreshing token or re-connect.")
        except Exception as e:
            st.error("Google fetch error: " + str(e))
    else:
        st.info("No Google token saved for this user.")

    st.markdown("---")
    st.info("If you want automatic refresh of expired tokens, we can implement refresh_token flows (requires client secrets stored server-side).")

# --- END smart_device_integration.py ---
