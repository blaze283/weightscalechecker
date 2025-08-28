# app_real.py
"""
Production-ready demo (NOT production). This Streamlit app:
 - Verifies NIN/BVN with pluggable providers (Mono, VerifyMe, OnePipe, YouVerify, or custom URL)
 - Uses Argon2 for PIN hashing
 - Sends OTP via Twilio (if configured) or logs to SMS table
 - Provides wallet: deposit, withdraw, transfer, tx history
 - Uses SQLite for persistence: banking_real_full.db

Before running:
 - pip install streamlit requests argon2-cffi twilio python-dotenv
 - create .streamlit/secrets.toml with provider & Twilio creds (see below)
"""

import streamlit as st
import sqlite3
import requests
import os
from datetime import datetime, timedelta
import random
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# ---------------------------
# CONFIG / DB
# ---------------------------
st.set_page_config(page_title="Banking App — NIN/BVN + Wallet (Full)", layout="centered")

DB_PATH = "banking_real_full.db"
ph = PasswordHasher()  # Argon2

# Provider selection:
# st.secrets must contain PROVIDER (one of: mono, verifyme, youverify, onepipe, custom)
# plus PROVIDER_API_KEY and optionally PROVIDER_BASE_URL (for custom)
PROVIDER = st.secrets.get("PROVIDER", "custom").lower()
PROVIDER_API_KEY = st.secrets.get("PROVIDER_API_KEY", None)
PROVIDER_BASE_URL = st.secrets.get("PROVIDER_BASE_URL", None)  # used for 'custom' or provider-specific override

# Twilio (optional) for real SMS / OTP sending
TWILIO_SID = st.secrets.get("TWILIO_SID", None)
TWILIO_TOKEN = st.secrets.get("TWILIO_TOKEN", None)
TWILIO_FROM = st.secrets.get("TWILIO_FROM", None)

# Optional email/SMTP could be added similarly (not included here to keep code focused)

# ---------------------------
# DB helpers
# ---------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        nin TEXT,
        bvn TEXT,
        pin_hash TEXT,
        verified INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE NOT NULL,
        balance REAL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        from_user INTEGER,
        to_user INTEGER,
        amount REAL,
        type TEXT,
        note TEXT,
        time TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sms_log (
        id INTEGER PRIMARY KEY,
        recipient TEXT,
        message TEXT,
        time TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY,
        phone TEXT,
        otp TEXT,
        expire_at TEXT,
        used INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    conn.commit()
    return conn

if not os.path.exists(DB_PATH):
    conn = init_db()
else:
    conn = get_db()

# ---------------------------
# Utilities
# ---------------------------
def now_iso():
    return datetime.utcnow().isoformat()

def log_sms(recipient, message):
    cur = conn.cursor()
    cur.execute("INSERT INTO sms_log (recipient, message, time) VALUES (?, ?, ?)",
                (recipient, message, now_iso()))
    conn.commit()

def store_otp(phone, otp, ttl_minutes=5):
    expire_at = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).isoformat()
    cur = conn.cursor()
    cur.execute("INSERT INTO otps (phone, otp, expire_at, used, created_at) VALUES (?,?,?,?,?)",
                (phone, otp, expire_at, 0, now_iso()))
    conn.commit()

def verify_otp(phone, otp):
    cur = conn.cursor()
    cur.execute("SELECT * FROM otps WHERE phone = ? AND otp = ? AND used = 0 ORDER BY id DESC LIMIT 1", (phone, otp))
    row = cur.fetchone()
    if not row:
        return False, "OTP not found"
    if datetime.fromisoformat(row["expire_at"]) < datetime.utcnow():
        return False, "OTP expired"
    # mark used
    cur.execute("UPDATE otps SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    return True, "OK"

def add_user(name, phone, nin=None, bvn=None, pin=None, verified=False):
    cur = conn.cursor()
    pin_hash = ph.hash(pin) if pin else None
    cur.execute("INSERT INTO users (name, phone, nin, bvn, pin_hash, verified, created_at) VALUES (?,?,?,?,?,?,?)",
                (name, phone, nin, bvn, pin_hash, int(verified), now_iso()))
    conn.commit()
    user_id = cur.lastrowid
    cur.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?,?)", (user_id, 0.0))
    conn.commit()
    return user_id

def get_user_by_phone(phone):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    return cur.fetchone()

def verify_pin_for_user(phone, pin):
    user = get_user_by_phone(phone)
    if not user or not user["pin_hash"]:
        return False
    try:
        ph.verify(user["pin_hash"], pin)
        return True
    except VerifyMismatchError:
        return False

def get_balance(user_id):
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,))
    r = cur.fetchone()
    return float(r["balance"]) if r else 0.0

def set_balance(user_id, new_balance):
    cur = conn.cursor()
    cur.execute("UPDATE wallets SET balance = ? WHERE user_id = ?", (float(new_balance), user_id))
    conn.commit()

def add_transaction(from_user, to_user, amount, ttype, note=""):
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (from_user, to_user, amount, type, note, time) VALUES (?,?,?,?,?,?)",
                (from_user, to_user, float(amount), ttype, note, now_iso()))
    conn.commit()

def get_transactions_for_user(user_id, limit=100):
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE from_user = ? OR to_user = ? ORDER BY id DESC LIMIT ?",
                (user_id, user_id, limit))
    return cur.fetchall()

# ---------------------------
# Provider adapters
# ---------------------------
def call_provider(url, payload, headers=None):
    if headers is None:
        headers = {}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        return {"status": "success", "raw": r.json()}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e), "raw": None}

# Mono adapter (Mono Lookup docs show Bearer header and endpoints like /lookup/bvn, /lookup/nin)
def provider_verify_mono(kind, id_value):
    # kind in {"nin", "bvn"}
    base = PROVIDER_BASE_URL or "https://api.withmono.com"  # example base if not set
    if kind == "nin":
        url = f"{base}/lookup/nin"
        payload = {"nin": id_value}
    else:
        url = f"{base}/lookup/bvn"
        payload = {"bvn": id_value}
    headers = {"Authorization": f"Bearer {PROVIDER_API_KEY}", "Content-Type": "application/json"}
    return call_provider(url, payload, headers)

# VerifyMe adapter (docs: vapi.verifyme.ng or docs.verifyme.ng)
def provider_verify_verifyme(kind, id_value):
    base = PROVIDER_BASE_URL or "https://vapi.verifyme.ng/v1/verifications"
    if kind == "nin":
        # sample: POST /verifications/identities/nin/:ref  (some providers use path param)
        url = f"{base}/identities/nin"
        payload = {"nin": id_value}
    else:
        url = f"{base}/identities/bvn"
        payload = {"bvn": id_value}
    headers = {"Authorization": f"Bearer {PROVIDER_API_KEY}", "Content-Type": "application/json"}
    return call_provider(url, payload, headers)

# Dojah / YouVerify / OnePipe / Generic adapters — we attempt to call a configured base path
def provider_verify_generic(kind, id_value):
    if not PROVIDER_BASE_URL:
        return {"status": "error", "message": "PROVIDER_BASE_URL not set for generic provider"}
    endpoint = PROVIDER_BASE_URL
    payload = {kind: id_value}
    headers = {"Authorization": f"Bearer {PROVIDER_API_KEY}"} if PROVIDER_API_KEY else {}
    return call_provider(endpoint, payload, headers)

def verify_identity(kind, id_value):
    """
    Unified verification function.
    kind: 'nin' or 'bvn'
    """
    if PROVIDER == "mono":
        return provider_verify_mono(kind, id_value)
    elif PROVIDER == "verifyme":
        return provider_verify_verifyme(kind, id_value)
    else:
        # fallback: treat provider base as custom endpoint, post {kind: value}
        return provider_verify_generic(kind, id_value)

# ---------------------------
# Twilio SMS (optional)
# ---------------------------
def send_sms_via_twilio(to_phone, message):
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        # fallback: log
        log_sms(to_phone, f"(SIMULATED) {message}")
        return {"status": "simulated", "message": "Twilio not configured; SMS logged"}
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(body=message, from_=TWILIO_FROM, to=to_phone)
        log_sms(to_phone, f"Twilio SID:{msg.sid} — {message}")
        return {"status": "sent", "sid": msg.sid}
    except Exception as e:
        log_sms(to_phone, f"(TWILIO ERROR) {str(e)} — {message}")
        return {"status": "error", "message": str(e)}

# ---------------------------
# UI
# ---------------------------
st.title("Banking App — NIN/BVN + Wallet (Full)")
st.caption("Add provider credentials in .streamlit/secrets.toml. Providers: mono, verifyme, onepipe, youverify, or custom base URL.")

menu = st.sidebar.selectbox("Menu", ["Register", "Login", "Admin: Seed / Inspect", "SMS Log", "Provider Status"])

# ------------- REGISTER -------------
if menu == "Register":
    st.header("Register — identity verification required")
    with st.form("register"):
        name = st.text_input("Full name")
        phone = st.text_input("Phone (with country code, e.g. +2348012345678)")
        nin = st.text_input("NIN (optional)")
        bvn = st.text_input("BVN (optional)")
        pin = st.text_input("Choose a 4-digit numeric PIN", type="password")
        pin2 = st.text_input("Confirm PIN", type="password")
        submit = st.form_submit_button("Verify and create")
    if submit:
        if not name or not phone or not pin:
            st.error("Name, phone and PIN required")
        elif pin != pin2:
            st.error("PINs do not match")
        elif not (nin or bvn):
            st.error("Provide either NIN or BVN")
        else:
            verified = False
            # call provider(s)
            if nin:
                st.info("Verifying NIN with provider...")
                res = verify_identity("nin", nin.strip())
                if res.get("status") == "success":
                    verified = True
                    st.success("NIN verification successful")
                    st.json(res.get("raw"))
                else:
                    st.error(f"NIN verification failed: {res.get('message')}")
            if (not verified) and bvn:
                st.info("Verifying BVN with provider...")
                res = verify_identity("bvn", bvn.strip())
                if res.get("status") == "success":
                    verified = True
                    st.success("BVN verification successful")
                    st.json(res.get("raw"))
                else:
                    st.error(f"BVN verification failed: {res.get('message')}")
            if verified:
                if get_user_by_phone(phone.strip()):
                    st.error("Phone already registered")
                else:
                    uid = add_user(name.strip(), phone.strip(),
                                   nin.strip() if nin else None,
                                   bvn.strip() if bvn else None,
                                   pin=pin.strip(), verified=True)
                    # send welcome SMS or OTP
                    log_msg = f"Welcome {name}. Your account is created and verified."
                    resp = send_sms_via_twilio(phone.strip(), log_msg)
                    st.success(f"Account created (id {uid}). SMS status: {resp.get('status')}")
            else:
                st.error("Could not verify identity with provided NIN/BVN. Check values and provider config.")

# ------------- LOGIN -------------
elif menu == "Login":
    st.header("Login")
    phone = st.text_input("Phone (with country code)", key="login_phone")
    pin = st.text_input("PIN (optional)", type="password", key="login_pin")
    if st.button("Login with PIN"):
        user = get_user_by_phone(phone.strip())
        if not user:
            st.error("No account with that phone")
        else:
            try:
                if verify_pin_for_user(phone.strip(), pin.strip()):
                    st.session_state.user_id = user["id"]
                    st.success(f"Welcome back, {user['name']}")
                    st.experimental_rerun()
                else:
                    st.error("Wrong PIN")
            except Exception as e:
                st.error("PIN verification failed")
    if st.button("Send OTP"):
        # generate OTP and send via Twilio (or log)
        if not phone:
            st.error("Enter phone")
        else:
            otp = str(random.randint(100000, 999999))
            store_otp(phone.strip(), otp, ttl_minutes=10)
            send_sms_via_twilio(phone.strip(), f"Your OTP is {otp}")
            st.success("OTP sent (or logged). Use it to login below.")
    # OTP login
    otp_val = st.text_input("OTP (if sent)", key="otp_login")
    if st.button("Login with OTP"):
        ok, msg = verify_otp(phone.strip(), otp_val.strip())
        if ok:
            user = get_user_by_phone(phone.strip())
            if not user:
                st.error("No account for that phone")
            else:
                st.session_state.user_id = user["id"]
                st.success("Logged in with OTP")
                st.experimental_rerun()
        else:
            st.error(f"OTP failed: {msg}")

    # if session present, show dashboard
    if st.session_state.get("user_id"):
        uid = st.session_state.user_id
        user = get_user_by_phone(get_user(uid)["phone"]) if False else get_user(uid)  # ensure fresh fetch
        st.markdown("---")
        st.subheader("Dashboard")
        st.write(f"Name: {user['name']}")
        st.write(f"Phone: {user['phone']}")
        st.write(f"Verified: {'Yes' if user['verified'] else 'No'}")
        st.write(f"Balance: ₦{get_balance(uid):,.2f}")

        st.markdown("### Actions")
        c1, c2, c3 = st.columns(3)
        with c1:
            amount = st.number_input("Top-up amount", min_value=0.0, value=0.0, key="top_amt")
            if st.button("Top-up"):
                if amount > 0:
                    set_balance(uid, get_balance(uid) + amount)
                    add_transaction(None, uid, amount, "deposit", "Top-up")
                    send_sms_via_twilio(user["phone"], f"You've been credited ₦{amount:.2f}")
                    st.success("Top-up successful")
                    st.experimental_rerun()
                else:
                    st.error("Enter amount > 0")
        with c2:
            wamount = st.number_input("Withdraw amount", min_value=0.0, value=0.0, key="wd_amt")
            if st.button("Withdraw"):
                if wamount <= 0:
                    st.error("Enter amount > 0")
                elif wamount > get_balance(uid):
                    st.error("Insufficient balance")
                else:
                    set_balance(uid, get_balance(uid) - wamount)
                    add_transaction(uid, None, wamount, "withdraw", "Withdrawal")
                    send_sms_via_twilio(user["phone"], f"You withdrew ₦{wamount:.2f}")
                    st.success("Withdraw successful")
                    st.experimental_rerun()
        with c3:
            to_phone = st.text_input("Recipient phone", key="r_phone")
            tamount = st.number_input("Send amount", min_value=0.0, value=0.0, key="send_amt")
            note = st.text_input("Note", key="send_note")
            if st.button("Send"):
                if tamount <= 0:
                    st.error("Enter amount > 0")
                elif tamount > get_balance(uid):
                    st.error("Insufficient balance")
                else:
                    recipient = get_user_by_phone(to_phone.strip())
                    if not recipient:
                        st.error("Recipient not found")
                    elif not recipient["verified"]:
                        st.error("Recipient not verified")
                    else:
                        set_balance(uid, get_balance(uid) - tamount)
                        set_balance(recipient["id"], get_balance(recipient["id"]) + tamount)
                        add_transaction(uid, recipient["id"], tamount, "transfer", note)
                        send_sms_via_twilio(recipient["phone"], f"You received ₦{tamount:.2f} from {user['name']}")
                        send_sms_via_twilio(user["phone"], f"You sent ₦{tamount:.2f} to {recipient['phone']}")
                        st.success("Transfer complete")
                        st.experimental_rerun()

        st.markdown("---")
        st.subheader("Recent transactions")
        txs = get_transactions_for_user(uid)
        if not txs:
            st.info("No transactions")
        else:
            for t in txs:
                from_p = "SYSTEM" if not t["from_user"] else get_user(t["from_user"])["phone"]
                to_p = "SYSTEM" if not t["to_user"] else get_user(t["to_user"])["phone"]
                st.write(f"[{t['time']}] {t['type'].upper()} ₦{t['amount']:.2f} — {t['note']} (from {from_p} to {to_p})")

        if st.button("Logout"):
            del st.session_state["user_id"]
            st.experimental_rerun()

# ------------- ADMIN -------------
elif menu == "Admin: Seed / Inspect":
    st.header("Admin tools")
    if st.button("Seed example users (if empty)"):
        if not get_user_by_phone("+234800000001"):
            add_user("Alice Verified", "+234800000001", nin="12345678901", pin="1234", verified=True)
            uid = get_user_by_phone("+234800000001")["id"]
            set_balance(uid, 1000.0)
        if not get_user_by_phone("+234800000002"):
            add_user("Bob Verified", "+234800000002", bvn="98765432109", pin="4321", verified=True)
            uid = get_user_by_phone("+234800000002")["id"]
            set_balance(uid, 300.0)
        st.success("Seeded")
    st.markdown("### Users")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    for u in cur.fetchall():
        st.write(dict(u))
    st.markdown("### Wallets")
    cur.execute("SELECT * FROM wallets")
    for w in cur.fetchall():
        st.write(dict(w))
    st.markdown("### Transactions")
    cur.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 100")
    for t in cur.fetchall():
        st.write(dict(t))

# ------------- SMS LOG -------------
elif menu == "SMS Log":
    st.header("SMS / OTP Log (last 200)")
    cur = conn.cursor()
    cur.execute("SELECT * FROM sms_log ORDER BY id DESC LIMIT 200")
    for r in cur.fetchall():
        st.write(f"[{r['time']}] To: {r['recipient']} — {r['message']}")

# ------------- PROVIDER STATUS -------------
elif menu == "Provider Status":
    st.header("Provider diagnostics")
    st.write("Provider:", PROVIDER)
    st.write("Provider base URL:", PROVIDER_BASE_URL)
    st.write("Provider API key present:", bool(PROVIDER_API_KEY))
    st.write("Twilio configured:", bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM))
    st.markdown("You can test verification endpoints from here:")
    test_kind = st.radio("Test kind", ["nin", "bvn"])
    test_value = st.text_input("Test value")
    if st.button("Run test"):
        res = verify_identity(test_kind, test_value.strip())
        st.json(res)

# Footer
st.markdown("---")
st.caption("Security notes: store secrets in your deploy platform's secret store; obtain provider approvals before production; use TLS and KMS for keys; implement rate-limiting and fraud controls.")
