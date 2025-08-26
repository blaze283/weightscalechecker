# fitness_app.py
import streamlit as st
import sqlite3
import base64
import requests
import pandas as pd
import datetime
import time
import io
import os

# ----------------- CONFIG -----------------
st.set_page_config(page_title="Fitness & BMI Pro", page_icon="💪", layout="wide")

# Put your YouTube API key here (optional). If empty, built-in video links will be used.
YOUTUBE_API_KEY = "AIzaSyAzTZjx9rIS6eFJitzP1QOU02kvperunqQ"  # replace or leave blank

DB_FILE = "app.db"
DEFAULT_USER = "guest"

# ----------------- DATABASE HELPERS -----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # users: username unique, password (plaintext here — consider hashing in prod)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    # progress: username, date (ISO), weight_kg (real)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TEXT,
            weight REAL
        )
    """)
    # preferences: username unique, theme, unit, bg_color, bg_image (base64 text)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            username TEXT PRIMARY KEY,
            theme TEXT,
            unit TEXT,
            bg_color TEXT,
            bg_image BLOB
        )
    """)
    # routines: store custom routines created by users (json text)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            json TEXT
        )
    """)
    conn.commit()
    conn.close()

def db_execute(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(query, params)
    rows = None
    if fetch:
        rows = cur.fetchall()
    conn.commit()
    conn.close()
    return rows

# ----------------- AUTH HELPERS -----------------
def add_user_db(username, password):
    try:
        db_execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        # create default preferences
        db_execute("INSERT OR REPLACE INTO preferences (username, theme, unit, bg_color, bg_image) VALUES (?, ?, ?, ?, ?)",
                   (username, "Light", "Kilograms", "#f0f2f6", None))
        return True
    except Exception as e:
        return False

def check_user_db(username, password):
    rows = db_execute("SELECT password FROM users WHERE username=?", (username,), fetch=True)
    if rows and rows[0][0] == password:
        return True
    return False

def get_preferences(username):
    rows = db_execute("SELECT theme,unit,bg_color,bg_image FROM preferences WHERE username=?", (username,), fetch=True)
    if rows:
        theme, unit, bg_color, bg_image = rows[0]
        return {"theme": theme or "Light", "unit": unit or "Kilograms", "bg_color": bg_color, "bg_image": bg_image}
    # default
    return {"theme": "Light", "unit": "Kilograms", "bg_color": "#f0f2f6", "bg_image": None}

def save_preferences(username, theme, unit, bg_color, bg_image_bytes):
    db_execute(
        "INSERT OR REPLACE INTO preferences (username, theme, unit, bg_color, bg_image) VALUES (?, ?, ?, ?, ?)",
        (username, theme, unit, bg_color, bg_image_bytes)
    )

def add_progress(username, date_iso, weight_kg):
    db_execute("INSERT INTO progress (username, date, weight) VALUES (?, ?, ?)", (username, date_iso, weight_kg))

def get_progress(username):
    rows = db_execute("SELECT date, weight FROM progress WHERE username=? ORDER BY date", (username,), fetch=True)
    return rows or []

def save_routine(username, title, json_text):
    db_execute("INSERT INTO routines (username, title, json) VALUES (?, ?, ?)", (username, title, json_text))

def get_routines(username):
    rows = db_execute("SELECT id, title, json FROM routines WHERE username=?", (username,), fetch=True)
    return rows or []

# ----------------- INIT -----------------
init_db()

# ----------------- UI UTILS -----------------
def set_background_theme(theme, bg_color=None, bg_image_b64=None):
    text_color = "#FFFFFF" if theme == "Dark" else "#000000"
    if bg_image_b64:
        st.markdown(f"""
        <style>
        .stApp {{
            background: url("data:image/png;base64,{bg_image_b64}") no-repeat center center fixed;
            background-size: cover;
            color: {text_color};
        }}
        </style>
        """, unsafe_allow_html=True)
    else:
        bg = bg_color if bg_color else ("#0e1117" if theme == "Dark" else "#f0f2f6")
        st.markdown(f"""
        <style>
        .stApp {{
            background-color: {bg};
            color: {text_color};
        }}
        input, textarea, select {{
            color: {text_color} !important;
        }}
        </style>
        """, unsafe_allow_html=True)

def card_markdown(html, unsafe=True):
    st.markdown(f'<div style="background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; box-shadow:0 2px 6px rgba(0,0,0,0.08); color:inherit;">{html}</div>', unsafe_allow_html=unsafe)

# ----------------- YOUTUBE SEARCH -----------------
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
def youtube_search(query, max_results=4):
    if not YOUTUBE_API_KEY:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY
    }
    try:
        r = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=6)
        r.raise_for_status()
        items = r.json().get("items", [])
        videos = []
        for it in items:
            vid = it["id"]["videoId"]
            title = it["snippet"]["title"]
            thumb = it["snippet"]["thumbnails"]["medium"]["url"]
            videos.append({"id": vid, "title": title, "thumb": thumb, "url": f"https://www.youtube.com/watch?v={vid}"})
        return videos
    except Exception:
        return []

# ----------------- PREDEFINED EXERCISES / PROGRAMS -----------------
# For reliability we include built-in YouTube links (fallback) + video query keywords
EXERCISES = {
    "Standard Push-ups": {"query": "standard push up tutorial", "fallback": "https://www.youtube.com/watch?v=IODxDxX7oi4"},
    "Wide Push-ups": {"query": "wide push ups form", "fallback": "https://www.youtube.com/watch?v=pvIjsG5Svck"},
    "Diamond Push-ups": {"query": "diamond push ups", "fallback": "https://www.youtube.com/watch?v=J0DnG1_S92I"},
    "Incline Push-ups": {"query": "incline push ups", "fallback": "https://www.youtube.com/watch?v=IODxDxX7oi4"},
    "Plank": {"query": "how to plank", "fallback": "https://www.youtube.com/watch?v=B296mZDhrP4"},
    "Jumping Jacks": {"query": "jumping jacks exercise", "fallback": "https://www.youtube.com/watch?v=c4DAnQ6DtF8"},
    "Warm-up": {"query": "upper body warm up", "fallback": "https://www.youtube.com/watch?v=HHt0Z1m2G9E"},
    "Cool-down": {"query": "stretching cooldown", "fallback": "https://www.youtube.com/watch?v=5pW8hHT4JmU"}
}

PROGRAMS = {
    "Beginner Push-Up Routine": [
        {"name": "Warm-up", "duration": 45},
        {"name": "Incline Push-ups", "duration": 30},
        {"name": "Rest", "duration": 30},
        {"name": "Standard Push-ups", "duration": 20},
        {"name": "Rest", "duration": 45},
        {"name": "Plank", "duration": 30},
        {"name": "Cool-down", "duration": 60},
    ],
    "Full Body Quick (Tabata style)": [
        {"name": "Warm-up", "duration": 60},
        {"name": "Jumping Jacks", "duration": 20},
        {"name": "Rest", "duration": 10},
        {"name": "Standard Push-ups", "duration": 20},
        {"name": "Rest", "duration": 10},
    ]
}

# ----------------- SESSION STATE -----------------
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "running" not in st.session_state:
    st.session_state.running = False
if "paused" not in st.session_state:
    st.session_state.paused = False
if "sequence" not in st.session_state:
    st.session_state.sequence = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "time_left" not in st.session_state:
    st.session_state.time_left = 0
if "total_time" not in st.session_state:
    st.session_state.total_time = 0
if "elapsed" not in st.session_state:
    st.session_state.elapsed = 0

# ----------------- SIDEBAR NAV + SETTINGS -----------------
st.sidebar.title("🏋️ Fitness Pro")
nav = st.sidebar.radio("Navigate", ["Home", "Programs", "Workout", "Progress", "Profile", "Settings"], index=["Home","Programs","Workout","Progress","Profile","Settings"].index(st.session_state.page))
st.session_state.page = nav

# Auth controls in sidebar
st.sidebar.markdown("---")
if "username" not in st.session_state or not st.session_state.username:
    st.sidebar.info("Not signed in")
else:
    st.sidebar.success(f"Signed in as {st.session_state.username}")

# quick logout
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.experimental_rerun()

# ----------------- AUTH UI -----------------
def auth_ui():
    st.header("Sign In / Sign Up")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Login")
        login_user = st.text_input("Username", key="login_user_input")
        login_pass = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Login"):
            if check_user_db(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.success("Logged in ✅")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
    with col2:
        st.subheader("Sign Up")
        su_user = st.text_input("New username", key="signup_user_input")
        su_pass = st.text_input("New password", type="password", key="signup_pass_input")
        if st.button("Create account"):
            if add_user_db(su_user, su_pass):
                st.session_state.logged_in = True
                st.session_state.username = su_user
                st.success("Account created and logged in ✅")
                st.experimental_rerun()
            else:
                st.error("Username might already exist")

# ----------------- PAGE: HOME -----------------
def page_home():
    st.title("🏠 Home")
    st.markdown("Welcome to your Fitness & BMI app. Quick actions below.")
    if not st.session_state.logged_in:
        st.info("Please sign in first to save progress and preferences.")
    # quick BMI box
    st.subheader("Quick BMI Calculator")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        feet = st.number_input("Feet", min_value=1, max_value=8, value=5, key="home_feet")
    with col2:
        inches = st.number_input("Inches", min_value=0, max_value=11, value=7, key="home_inches")
    with col3:
        unit = st.selectbox("Unit", ["Kilograms", "Pounds"], key="home_unit")
        weight_val = st.number_input("Weight", min_value=0.1, value=70.0, step=0.1, key="home_weight")
    if st.button("Calculate BMI", key="home_calc"):
        height_m = (feet*12 + inches) * 0.0254
        weight_kg = weight_val if unit=="Kilograms" else weight_val * 0.453592
        bmi = weight_kg / (height_m**2)
        cat, emoji, style, diet, workout, query = get_bmi_category(bmi)
        st.markdown(f'<div style="{style} padding:10px; border-radius:8px;"><b>{emoji} BMI {bmi:.1f} — {cat}</b></div>', unsafe_allow_html=True)
        st.write("Diet tips:")
        st.info(diet)
        st.write("Workout tips:")
        st.success(workout)

# ----------------- PAGE: PROGRAMS -----------------
def page_programs():
    st.title("📚 Programs")
    st.markdown("Choose a program, preview it, or save a custom routine.")
    col1, col2 = st.columns([2,1])
    with col1:
        for p_name, blocks in PROGRAMS.items():
            st.markdown(f"### {p_name}")
            st.write("• " + "\n• ".join([f"{b['name']} — {b['duration']}s" for b in blocks]))
            if st.button(f"Start {p_name}", key=f"start_{p_name}"):
                # build sequence into session
                seq = []
                for r in range(1):  # single round default; user can adjust later in Workout page
                    for b in blocks:
                        # lookup video
                        ex = EXERCISES.get(b["name"], None)
                        if ex:
                            query = ex["query"]
                            vidlist = youtube_search(query, max_results=1) if YOUTUBE_API_KEY else []
                            video = vidlist[0]["url"] if vidlist else ex["fallback"]
                        else:
                            video = None
                        seq.append({"name": b["name"], "duration": b["duration"], "video": video})
                st.session_state.sequence = seq
                st.session_state.current_index = 0
                st.session_state.time_left = seq[0]["duration"] if seq else 0
                st.session_state.total_time = sum(x["duration"] for x in seq)
                st.session_state.elapsed = 0
                st.session_state.running = True
                st.session_state.paused = False
                st.session_state.page = "Workout"
                st.experimental_rerun()
    with col2:
        st.markdown("### Custom Routine")
        new_title = st.text_input("Routine title")
        st.markdown("Add blocks below (name,duration sec) — press Add Block to append then Save Routine.")
        block_name = st.selectbox("Exercise", list(EXERCISES.keys()))
        block_dur = st.number_input("Duration (sec)", min_value=5, value=30, step=5)
        if st.button("Add Block"):
            # hold temporary blocks in session
            if "temp_blocks" not in st.session_state:
                st.session_state.temp_blocks = []
            st.session_state.temp_blocks.append({"name": block_name, "duration": block_dur})
            st.success("Block added")
        if "temp_blocks" in st.session_state and st.session_state.temp_blocks:
            st.write("Current blocks:")
            for b in st.session_state.temp_blocks:
                st.write(f"- {b['name']} ({b['duration']}s)")
            if st.button("Save Routine"):
                if not st.session_state.logged_in:
                    st.warning("Sign in to save routines")
                else:
                    import json
                    save_routine(st.session_state.username, new_title or f"Routine {datetime.datetime.now().isoformat()}", json.dumps(st.session_state.temp_blocks))
                    st.success("Saved routine")
                    st.session_state.temp_blocks = []

# ----------------- PAGE: WORKOUT -----------------
def build_seq_from_session(default_rounds=1, override_work=None, override_rest=None):
    # if session already has sequence, keep it; else build from Program selection inside Workout page
    if st.session_state.sequence:
        return st.session_state.sequence
    # default: pick first program
    first_prog = next(iter(PROGRAMS.values()))
    seq = []
    for block in first_prog:
        name = block["name"]
        dur = block["duration"]
        # overrides
        if override_work and "Rest" not in name:
            dur = override_work
        if override_rest and "Rest" in name:
            dur = override_rest
        ex = EXERCISES.get(name)
        if ex:
            vids = youtube_search(ex["query"], max_results=1) if YOUTUBE_API_KEY else []
            video = vids[0]["url"] if vids else ex["fallback"]
        else:
            video = None
        seq.append({"name": name, "duration": dur, "video": video})
    return seq

def page_workout():
    st.title("🎬 Workout")
    st.markdown("Control your workout session. Start/Pause/Reset, or skip steps.")

    # Build or show sequence
    if not st.session_state.sequence:
        st.markdown("No sequence loaded. Choose a program on Programs page or load a saved routine on Profile.")
        if st.button("Load Beginner Push-Up"):
            st.session_state.sequence = build_seq_from_session()
            st.session_state.current_index = 0
            st.session_state.time_left = st.session_state.sequence[0]["duration"]
            st.session_state.total_time = sum(b["duration"] for b in st.session_state.sequence)
            st.session_state.elapsed = 0
            st.session_state.running = True
            st.experimental_rerun()
        return

    # show current block video and timer
    seq = st.session_state.sequence
    idx = st.session_state.current_index
    if idx < 0: idx = 0
    if idx >= len(seq):
        st.success("Workout finished 🎉")
        # optionally clear sequence
        if st.button("Finish & Clear"):
            st.session_state.sequence = []
            st.session_state.running = False
            st.session_state.current_index = 0
            st.session_state.time_left = 0
            st.session_state.total_time = 0
            st.session_state.elapsed = 0
            st.experimental_rerun()
        return

    block = seq[idx]
    left = st.session_state.time_left if st.session_state.time_left>0 else block["duration"]
    # video area
    colv, colr = st.columns([2,1])
    with colv:
        st.markdown(f"### {block['name']}  —  Round {idx+1}/{len(seq)}")
        if block["video"]:
            # embed YouTube link
            st.video(block["video"])
        else:
            st.info("No video for this exercise.")

    with colr:
        st.markdown("#### Timer")
        st.markdown(f"<div style='font-size:48px; text-align:center;'>{int(left)//60:02d}:{int(left)%60:02d}</div>", unsafe_allow_html=True)
        st.markdown(f"**Total elapsed:** {int(st.session_state.elapsed)}s / {int(st.session_state.total_time)}s")
        # controls
        c1, c2, c3 = st.columns(3)
        if c1.button("▶️ Start/Resume"):
            st.session_state.running = True
            st.session_state.paused = False
            st.experimental_rerun()
        if c2.button("⏸️ Pause"):
            st.session_state.paused = True
            st.session_state.running = False
        if c3.button("⏮️ Reset"):
            st.session_state.running = False
            st.session_state.paused = False
            st.session_state.current_index = 0
            st.session_state.time_left = seq[0]["duration"]
            st.session_state.elapsed = 0
            st.experimental_rerun()
        c4, c5 = st.columns(2)
        if c4.button("⏭️ Next"):
            # move to next immediately
            st.session_state.current_index += 1
            if st.session_state.current_index < len(seq):
                st.session_state.time_left = seq[st.session_state.current_index]["duration"]
            st.experimental_rerun()
        if c5.button("🔁 Previous"):
            st.session_state.current_index = max(0, st.session_state.current_index - 1)
            st.session_state.time_left = seq[st.session_state.current_index]["duration"]
            st.experimental_rerun()

    # Timer ticking (drive by rerun)
    if st.session_state.running:
        time.sleep(1)  # block execution to act as timer tick
        st.session_state.time_left -= 1
        st.session_state.elapsed += 1
        if st.session_state.time_left <= 0:
            # advance
            st.session_state.current_index += 1
            if st.session_state.current_index >= len(seq):
                st.success("Workout Complete 🎉")
                st.session_state.running = False
                # keep index at end
            else:
                st.session_state.time_left = seq[st.session_state.current_index]["duration"]
        st.experimental_rerun()

# ----------------- PAGE: PROGRESS -----------------
def page_progress():
    st.title("📈 Progress")
    if not st.session_state.logged_in:
        st.info("Sign in to log and view your progress.")
        return
    st.markdown("Log your weight and view history & charts.")
    col1, col2 = st.columns(2)
    with col1:
        date_in = st.date_input("Date", datetime.date.today())
    with col2:
        pref = get_preferences(st.session_state.username)
        unit = pref.get("unit", "Kilograms")
        w = st.number_input(f"Weight ({unit})", value=70.0, step=0.1, min_value=0.1)
    if st.button("Add entry"):
        # convert to kg if needed
        weight_kg = w if unit=="Kilograms" else (w * 0.453592)
        add_progress(st.session_state.username, date_in.isoformat(), weight_kg)
        st.success("Saved")
    # fetch and show table
    rows = get_progress(st.session_state.username)
    if not rows:
        st.info("No progress logged yet.")
        return
    df = pd.DataFrame(rows, columns=["date","weight_kg"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    # filters
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    start, end = st.date_input("Filter range", value=(min_date, max_date))
    mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
    df_filtered = df[mask]
    st.dataframe(df_filtered.assign(weight_display = (df_filtered["weight_kg"] if get_preferences(st.session_state.username)["unit"]=="Kilograms" else df_filtered["weight_kg"] / 0.453592)))
    st.line_chart(df_filtered.set_index("date")["weight_kg"])

# ----------------- PAGE: PROFILE -----------------
def page_profile():
    st.title("👤 Profile & Saved Routines")
    if not st.session_state.logged_in:
        st.info("Sign in to manage profile.")
        return
    prefs = get_preferences(st.session_state.username)
    st.subheader("Preferences")
    theme = st.selectbox("Theme", ["Light","Dark"], index=0 if prefs["theme"]=="Light" else 1)
    unit = st.selectbox("Weight Unit", ["Kilograms","Pounds"], index=0 if prefs["unit"]=="Kilograms" else 1)
    bg_color = st.color_picker("Background color", value=prefs.get("bg_color") or "#f0f2f6")
    uploaded = st.file_uploader("Upload background image (optional)", type=["png","jpg","jpeg"])
    if st.button("Save preferences"):
        img_b64 = None
        if uploaded:
            img_b64 = base64.b64encode(uploaded.read())
        save_preferences(st.session_state.username, theme, unit, bg_color, img_b64)
        st.success("Saved preferences")
        st.experimental_rerun()

    st.subheader("Saved Routines")
    rts = get_routines(st.session_state.username)
    if not rts:
        st.info("No saved routines")
    else:
        for rid, title, json_text in rts:
            st.markdown(f"**{title}**")
            st.write(json_text)

# ----------------- PAGE: SETTINGS -----------------
def page_settings():
    st.title("⚙️ Settings")
    st.markdown("Global app settings and theme preview.")
    # preview preferences for signed in user
    if st.session_state.logged_in:
        prefs = get_preferences(st.session_state.username)
    else:
        prefs = {"theme":"Light","unit":"Kilograms","bg_color":"#f0f2f6","bg_image":None}
    set_background_choice = st.selectbox("Preview theme", ["Light","Dark"], index=0 if prefs["theme"]=="Light" else 1)
    preview_color = st.color_picker("Preview background color", prefs["bg_color"] or "#f0f2f6")
    set_background_theme(set_background_choice, preview_color, None)
    st.info("Preferences saved per-user in the database when set in Profile page.")

# ----------------- ROUTE PAGES -----------------
if st.session_state.page == "Home":
    if not st.session_state.logged_in:
        auth_ui()
    page_home()
elif st.session_state.page == "Programs":
    if not st.session_state.logged_in:
        auth_ui()
    page_programs()
elif st.session_state.page == "Workout":
    if not st.session_state.logged_in:
        auth_ui()
    page_workout()
elif st.session_state.page == "Progress":
    if not st.session_state.logged_in:
        auth_ui()
    page_progress()
elif st.session_state.page == "Profile":
    if not st.session_state.logged_in:
        auth_ui()
    page_profile()
elif st.session_state.page == "Settings":
    page_settings()

# ----------------- END -----------------
