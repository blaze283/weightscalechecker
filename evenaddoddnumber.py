# app.py
import streamlit as st
import sqlite3
import bcrypt
import base64
import mimetypes
import json
import io
import os
from datetime import datetime, date, time, timedelta
import smtplib
from email.message import EmailMessage

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="LMB Weight Scale Checker", page_icon="⚖️", layout="centered")
DB_PATH = "users.db"

# -----------------------
# DB connection & schema (stable)
# -----------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Users
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT
)
""")

# Settings (base)
c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER UNIQUE,
    theme TEXT DEFAULT 'light',
    accent_color TEXT DEFAULT '#667eea'
)
""")
conn.commit()

# Add optional columns if missing (safe migration)
_optional_cols = {
    "background_blob": "BLOB",
    "background_mime": "TEXT",
    "smtp_host": "TEXT",
    "smtp_port": "INTEGER",
    "smtp_email": "TEXT",
    "smtp_password": "TEXT"
}
for col, coltype in _optional_cols.items():
    try:
        c.execute(f"ALTER TABLE settings ADD COLUMN {col} {coltype}")
    except sqlite3.OperationalError:
        pass
conn.commit()

# Saved plans
c.execute("""
CREATE TABLE IF NOT EXISTS saved_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    created_at TEXT,
    plan_json TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# Reminders
c.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    message TEXT,
    recipient_email TEXT,
    send_at TEXT,
    created_at TEXT,
    sent INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# -----------------------
# Utility functions: auth & settings
# -----------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_user(email: str, password: str):
    try:
        h = hash_password(password)
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.lower(), h))
        conn.commit()
        uid = c.lastrowid
        c.execute("INSERT OR IGNORE INTO settings (user_id, theme, accent_color) VALUES (?, 'light', '#667eea')", (uid,))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "That email is already registered."

def get_user_by_email(email: str):
    c.execute("SELECT * FROM users WHERE email=?", (email.lower(),))
    return c.fetchone()

def authenticate(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if verify_password(password, user[2]):
        return user
    return None

def get_settings(user_id: int):
    c.execute("""SELECT theme, accent_color, background_blob, background_mime,
                        smtp_host, smtp_port, smtp_email, smtp_password
                 FROM settings WHERE user_id=?""", (user_id,))
    r = c.fetchone()
    if r:
        return {
            "theme": r[0] or "light",
            "accent_color": r[1] or "#667eea",
            "background_blob": r[2],
            "background_mime": r[3],
            "smtp_host": r[4],
            "smtp_port": r[5],
            "smtp_email": r[6],
            "smtp_password": r[7],
        }
    c.execute("INSERT OR IGNORE INTO settings (user_id, theme, accent_color) VALUES (?, 'light', '#667eea')", (user_id,))
    conn.commit()
    return {"theme":"light","accent_color":"#667eea","background_blob":None,"background_mime":None,"smtp_host":None,"smtp_port":None,"smtp_email":None,"smtp_password":None}

def save_settings(user_id:int, theme:str, accent_color:str, smtp:dict=None, bg_blob:bytes=None, bg_mime:str=None):
    if smtp:
        c.execute("""
            UPDATE settings
            SET theme=?, accent_color=?, smtp_host=?, smtp_port=?, smtp_email=?, smtp_password=?
            WHERE user_id=?
        """, (theme, accent_color, smtp.get("host"), smtp.get("port"), smtp.get("email"), smtp.get("password"), user_id))
    else:
        c.execute("UPDATE settings SET theme=?, accent_color=? WHERE user_id=?", (theme, accent_color, user_id))
    if bg_blob is not None:
        c.execute("UPDATE settings SET background_blob=?, background_mime=? WHERE user_id=?", (bg_blob, bg_mime, user_id))
    conn.commit()

def get_background(user_id:int):
    c.execute("SELECT background_blob, background_mime FROM settings WHERE user_id=?", (user_id,))
    r = c.fetchone()
    return (r[0], r[1]) if r else (None, None)

# -----------------------
# Planner helpers
# -----------------------
def lbs_to_kg(lbs): return lbs * 0.45359237
def kg_to_lbs(kg): return kg * 2.20462
def bmi_calc(weight_kg, height_m):
    return (weight_kg / (height_m**2)) if (height_m and height_m>0) else None

BASE_MEALS = {
    "Breakfast": ["Oatmeal + banana", "Scrambled eggs + toast", "Smoothie + protein", "Pancakes + berries", "Boiled eggs + avocado"],
    "Lunch": ["Grilled chicken + veggies", "Beef stir-fry + rice", "Tuna salad + greens", "Rice & beans", "Turkey sandwich"],
    "Dinner": ["Salmon + brown rice", "Grilled fish + salad", "Steak + vegetables", "Pasta + chicken", "Vegetable soup + bread"],
    "Snack": ["Nuts", "Yogurt", "Apple", "Carrots & hummus", "Granola"]
}

def meal_default_time(meal_type):
    return {"Breakfast":"08:00","Lunch":"13:00","Dinner":"19:00","Snack":"16:00"}.get(meal_type,"12:00")

def estimate_maintenance_calories(weight_kg):
    return max(1200, int(round(weight_kg * 25)))

def make_weekly_meal_plan(target_cal):
    dist = {"Breakfast": 0.25, "Lunch": 0.30, "Dinner": 0.30, "Snack": 0.15}
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {}
    for i,day in enumerate(days):
        day_meals = {}
        for mtype, choices in BASE_MEALS.items():
            choice = choices[i % len(choices)]
            cal = int(round(target_cal * dist[mtype]))
            day_meals[mtype] = {"item": choice, "time": meal_default_time(mtype), "cal": cal}
        plan[day] = day_meals
    return plan

def make_weekly_exercise_plan(bmi_cat):
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {}
    for d in days:
        if bmi_cat == "Underweight":
            plan[d] = [{"time":"07:00","activity":"Light cardio (15 min)"},{"time":"07:20","activity":"Strength training (30 min)"}]
        elif bmi_cat == "Normal":
            if d in ["Monday","Wednesday","Friday"]:
                plan[d] = [{"time":"06:30","activity":"Cardio (30 min)"},{"time":"07:10","activity":"Strength (30 min)"}]
            else:
                plan[d] = [{"time":"07:00","activity":"Mobility / Stretch (20 min)"}]
        elif bmi_cat == "Overweight":
            if d in ["Monday","Wednesday","Friday"]:
                plan[d] = [{"time":"06:00","activity":"Moderate cardio (35 min)"},{"time":"06:40","activity":"Strength (25 min)"}]
            else:
                plan[d] = [{"time":"07:00","activity":"Brisk walk (30-40 min)"}]
        else:
            plan[d] = [{"time":"06:00","activity":"Low-impact cardio (30-40 min)"}]
    return plan

# -----------------------
# Reminders helpers
# -----------------------
def save_reminder(user_id:int, title:str, message:str, recipient:str, send_at_iso:str):
    c.execute("INSERT INTO reminders (user_id, title, message, recipient_email, send_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, title, message, recipient, send_at_iso, datetime.utcnow().isoformat()))
    conn.commit()

def list_reminders(user_id:int, include_sent=False):
    if include_sent:
        c.execute("SELECT id, title, recipient_email, send_at, sent FROM reminders WHERE user_id=? ORDER BY send_at DESC", (user_id,))
    else:
        c.execute("SELECT id, title, recipient_email, send_at, sent FROM reminders WHERE user_id=? AND sent=0 ORDER BY send_at ASC", (user_id,))
    return c.fetchall()

def mark_reminder_sent(reminder_id:int):
    c.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
    conn.commit()

def send_email_via_smtp(smtp_host, smtp_port, smtp_email, smtp_password, to_email, subject, body):
    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=15)
    server.ehlo()
    server.starttls()
    server.login(smtp_email, smtp_password)
    server.send_message(msg)
    server.quit()
    return True

def check_and_send_due_reminders():
    now_iso = datetime.utcnow().isoformat()
    c.execute("""
        SELECT r.id, r.title, r.message, r.recipient_email, s.smtp_host, s.smtp_port, s.smtp_email, s.smtp_password
        FROM reminders r JOIN settings s ON r.user_id = s.user_id
        WHERE r.sent=0 AND r.send_at <= ?
    """, (now_iso,))
    rows = c.fetchall()
    sent = 0
    failed = 0
    for rid, title, message, recipient, host, port, mail, pw in rows:
        if not (host and port and mail and pw):
            failed += 1
            continue
        try:
            send_email_via_smtp(host, port or 587, mail, pw, recipient, title or "Reminder", message or "")
            mark_reminder_sent(rid)
            sent += 1
        except Exception:
            failed += 1
    return {"sent": sent, "failed": failed}

# -----------------------
# UI helpers
# -----------------------
def apply_theme(theme:str, accent_color:str):
    if theme == "dark":
        base_bg = "#0b0f12"
        text = "#e6eef6"
    else:
        base_bg = "#ffffff"
        text = "#0b1724"
    css = f"""
    <style>
    .stApp {{ background-color: {base_bg}; color: {text}; }}
    .stButton>button {{ background-color: {accent_color}; color: white; border-radius: 8px; }}
    .stDownloadButton>button {{ background: {accent_color}; color: white; border-radius: 8px; }}
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div, .stTextArea textarea {{
        border: 1px solid {accent_color} !important; border-radius:6px;
    }}
    .stMarkdown h1, .stMarkdown h2 {{ color: {text}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_background_from_blob(blob:bytes, mime:str):
    if not blob:
        return
    try:
        b64 = base64.b64encode(blob).decode()
        m = mime or "image/png"
        css = f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.18), rgba(0,0,0,0.18)), url("data:{m};base64,{b64}");
            background-size: cover; background-position: center;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    except Exception:
        pass

# -----------------------
# App UI & flow
# -----------------------
if "user" not in st.session_state:
    st.session_state.user = None

st.title("⚖️ LMB Weight Scale Checker")

# --- AUTH ---
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        st.subheader("Login")
        login_email = st.text_input("Email", key="login_email")
        login_pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            u = authenticate(login_email.strip().lower(), login_pw)
            if u:
                st.session_state.user = u
                st.success("Logged in — welcome!")
                st.rerun()
            else:
                st.error("Invalid credentials")
    with tab2:
        st.subheader("Sign up (auto-login)")
        signup_email = st.text_input("Email", key="signup_email")
        signup_pw = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Sign Up"):
            ok, err = create_user(signup_email.strip().lower(), signup_pw)
            if ok:
                st.session_state.user = get_user_by_email(signup_email.strip().lower())
                st.success("Account created and logged in!")
                st.rerun()
            else:
                st.error(err)
    st.stop()

# --- MAIN APP (logged in) ---
user = st.session_state.user
user_id = user[0]
settings = get_settings(user_id)

# apply theme and background
apply_theme(settings.get("theme") or "light", settings.get("accent_color") or "#667eea")
bg_blob, bg_mime = settings.get("background_blob"), settings.get("background_mime")
if bg_blob:
    render_background_from_blob(bg_blob, bg_mime)

# Sidebar nav
st.sidebar.markdown(f"**User:** {user[1]}")
nav = st.sidebar.radio("Navigate", ["Home","Settings","Reminders","Saved Plans","Logout"])

if nav == "Logout":
    st.session_state.user = None
    st.rerun()

# --- HOME ---
if nav == "Home":
    st.header("🏠 Personalized Planner")
    col1, col2, col3 = st.columns([1.2,1,1])
    with col1:
        unit = st.selectbox("Weight unit", ["Kilograms (kg)","Pounds (lbs)"])
        weight_input = st.number_input("Weight", min_value=0.1, max_value=999.9, value=70.0, format="%.1f")
    with col2:
        feet = st.number_input("Height (feet)", min_value=1, max_value=8, value=5)
    with col3:
        inches = st.number_input("Height (inches)", min_value=0, max_value=11, value=7)

    weight_kg = weight_input if unit.startswith("Kilograms") else lbs_to_kg(weight_input)
    height_m = (feet*12 + inches) * 0.0254
    bmi = bmi_calc(weight_kg, height_m) if height_m>0 else None

    if bmi:
        cat = "Underweight" if bmi < 18.5 else "Normal" if bmi < 25 else "Overweight" if bmi < 30 else "Obese"
        st.metric("BMI", f"{bmi:.1f}", delta=cat)
        maintenance = estimate_maintenance_calories(weight_kg)
        target = maintenance + 500 if cat=="Underweight" else maintenance if cat=="Normal" else max(1200, maintenance-400) if cat=="Overweight" else max(1200, maintenance-600)
        st.write(f"Estimated maintenance: **{maintenance} kcal/day** • Target: **{int(target)} kcal/day**")
        if st.button("Generate Weekly Meal & Exercise Plan"):
            weekly_meals = make_weekly_meal_plan(target)
            weekly_ex = make_weekly_exercise_plan(cat)
            plan = {"created":datetime.utcnow().isoformat(), "weight_kg":weight_kg, "height_m":height_m, "bmi":bmi, "bmi_category":cat, "target_kcal":int(target), "meals":weekly_meals, "exercise":weekly_ex}
            st.session_state["latest_plan"] = plan
            st.success("Plan generated — scroll down to view.")

    if "latest_plan" in st.session_state:
        p = st.session_state["latest_plan"]
        st.subheader("Weekly Meal Plan")
        for day, meals in p["meals"].items():
            with st.expander(f"{day} — approx {sum(m['cal'] for m in meals.values())} kcal"):
                for meal_name, meal_info in meals.items():
                    st.write(f"- **{meal_name} ({meal_info['time']})**: {meal_info['item']} — **{meal_info['cal']} kcal**")
        st.subheader("Weekly Exercise Plan")
        for day, acts in p["exercise"].items():
            with st.expander(day):
                for a in acts:
                    st.write(f"- {a['time']} — {a['activity']}")
        colA, colB = st.columns(2)
        with colA:
            plan_name = st.text_input("Plan name", value=f"My plan {date.today()}")
            if st.button("Save plan to account"):
                c.execute("INSERT INTO saved_plans (user_id, name, created_at, plan_json) VALUES (?, ?, ?, ?)",
                          (user_id, plan_name, datetime.utcnow().isoformat(), json.dumps(p)))
                conn.commit()
                st.success("Plan saved to your account.")
        with colB:
            st.download_button("Download plan (JSON)", data=json.dumps(p, indent=2), file_name="weekly_plan.json", mime="application/json")

# --- SETTINGS ---
elif nav == "Settings":
    st.header("⚙️ Settings & Customization")
    st.write("Customize theme, pick accent color, upload a background (drag & drop), and optionally configure SMTP for email reminders.")
    theme_choice = st.selectbox("Theme", ["light","dark"], index=0 if settings.get("theme","light")=="light" else 1)
    accent = st.color_picker("Accent color", settings.get("accent_color") or "#667eea")
    uploaded = st.file_uploader("Upload background image (jpg/png) — drag & drop supported", type=["jpg","jpeg","png"])
    st.markdown("#### Optional: SMTP (used to send reminders)")
    smtp_host = st.text_input("SMTP host (e.g. smtp.gmail.com)", value=settings.get("smtp_host") or "")
    smtp_port = st.number_input("SMTP port", value=int(settings.get("smtp_port") or 587))
    smtp_email = st.text_input("SMTP login email", value=settings.get("smtp_email") or "")
    smtp_password = st.text_input("SMTP password (will be stored)", type="password", value=settings.get("smtp_password") or "")

    if st.button("Save Settings"):
        blob = None
        mime = None
        if uploaded:
            blob = uploaded.read()
            mime = mimetypes.guess_type(uploaded.name)[0] or "image/png"
        smtp = {"host": smtp_host or None, "port": smtp_port or None, "email": smtp_email or None, "password": smtp_password or None}
        save_settings(user_id, theme_choice, accent, smtp=smtp, bg_blob=blob, bg_mime=mime)
        st.success("Settings saved. Theme/background will apply after reload.")
        st.rerun()

# --- REMINDERS ---
elif nav == "Reminders":
    st.header("⏰ Reminders")
    st.info("Save reminders (scheduled) or Send Now using SMTP credentials in Settings.")
    title = st.text_input("Title")
    message = st.text_area("Message")
    recipient = st.text_input("Recipient email", value=user[1])
    send_date = st.date_input("Send date", value=date.today())
    send_time = st.time_input("Send time (UTC)", value=(datetime.utcnow() + timedelta(minutes=1)).time().replace(second=0,microsecond=0))
    send_dt = datetime.combine(send_date, send_time)
    if st.button("Save reminder"):
        save_reminder(user_id, title, message, recipient, send_dt.isoformat())
        st.success("Reminder saved.")
    if st.button("Send now using saved SMTP"):
        s = get_settings(user_id)
        if not (s.get("smtp_host") and s.get("smtp_email") and s.get("smtp_password")):
            st.error("SMTP not configured. Add SMTP settings in Settings page.")
        else:
            try:
                send_email_via_smtp(s["smtp_host"], s.get("smtp_port") or 587, s["smtp_email"], s["smtp_password"], recipient, title or "Reminder", message or "")
                st.success("Email sent.")
            except Exception as e:
                st.error(f"Failed to send email: {e}")

    st.markdown("---")
    st.subheader("Pending reminders")
    pending = list_reminders(user_id, include_sent=False)
    if pending:
        for rid, t, rec, send_at, sent in pending:
            st.write(f"- **{t}** → {rec} at {send_at}")
            c1, c2 = st.columns([1,1])
            if c1.button("Send now", key=f"send_{rid}"):
                s = get_settings(user_id)
                if not (s.get("smtp_host") and s.get("smtp_email") and s.get("smtp_password")):
                    st.error("Set SMTP in Settings first.")
                else:
                    try:
                        send_email_via_smtp(s["smtp_host"], s.get("smtp_port") or 587, s["smtp_email"], s["smtp_password"], rec, t or "Reminder", "Scheduled reminder")
                        mark_reminder_sent(rid)
                        st.success("Sent & marked as sent.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
            if c2.button("Delete", key=f"del_{rid}"):
                c.execute("DELETE FROM reminders WHERE id=?", (rid,))
                conn.commit()
                st.rerun()
    else:
        st.write("No pending reminders.")

    st.markdown("---")
    if st.button("Check & send due reminders (now)"):
        res = check_and_send_due_reminders()
        st.success(f"Sent: {res['sent']}, Failed/Skipped: {res['failed']}")

# --- SAVED PLANS ---
elif nav == "Saved Plans":
    st.header("💾 Saved Plans")
    c.execute("SELECT id, name, created_at FROM saved_plans WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    if rows:
        for pid, name, created in rows:
            st.write(f"**{name}** — {created}")
            col1, col2 = st.columns([1,1])
            if col1.button("Load", key=f"load_{pid}"):
                c.execute("SELECT plan_json FROM saved_plans WHERE id=?", (pid,))
                r = c.fetchone()
                if r:
                    st.session_state["latest_plan"] = json.loads(r[0])
                    st.success("Plan loaded into view.")
                    st.rerun()
            if col2.button("Delete", key=f"delplan_{pid}"):
                c.execute("DELETE FROM saved_plans WHERE id=?", (pid,))
                conn.commit()
                st.rerun()
    else:
        st.write("No saved plans yet.")
