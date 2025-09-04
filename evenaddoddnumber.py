# app.py
import streamlit as st
import sqlite3
import bcrypt
import base64
import mimetypes
import json
from datetime import datetime, date, time, timedelta
import smtplib
from email.message import EmailMessage

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="LMB Weight Scale Checker", page_icon="⚖️", layout="centered")
DB_PATH = "users.db"

# -----------------------
# Database (stable schema)
# -----------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Users table (simple: id, email, password_hash)
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT
)
""")

# Settings table (one row per user; stores theme, accent color, optional background image blob, SMTP)
c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER UNIQUE,
    theme TEXT DEFAULT 'light',
    accent_color TEXT DEFAULT '#667eea',
    background_blob BLOB,
    smtp_host TEXT,
    smtp_port INTEGER,
    smtp_email TEXT,
    smtp_password TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# Reminders table
c.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    message TEXT,
    recipient_email TEXT,
    send_at TEXT,       -- ISO datetime string in UTC
    created_at TEXT,
    sent INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# -----------------------
# Helper functions
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
        # create default settings row for this user
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
    c.execute("SELECT theme, accent_color, smtp_host, smtp_port, smtp_email, smtp_password FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        return {
            "theme": row[0] or "light",
            "accent_color": row[1] or "#667eea",
            "smtp_host": row[2],
            "smtp_port": row[3],
            "smtp_email": row[4],
            "smtp_password": row[5]
        }
    # ensure a settings row
    c.execute("INSERT OR IGNORE INTO settings (user_id, theme, accent_color) VALUES (?, 'light', '#667eea')", (user_id,))
    conn.commit()
    return {"theme":"light","accent_color":"#667eea","smtp_host":None,"smtp_port":None,"smtp_email":None,"smtp_password":None}

def save_settings(user_id: int, theme: str, accent_color: str, smtp: dict = None, bg_blob: bytes = None):
    if smtp:
        c.execute("""
            UPDATE settings SET theme=?, accent_color=?, smtp_host=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE user_id=?
        """, (theme, accent_color, smtp.get("host"), smtp.get("port"), smtp.get("email"), smtp.get("password"), user_id))
    else:
        c.execute("UPDATE settings SET theme=?, accent_color=? WHERE user_id=?", (theme, accent_color, user_id))
    if bg_blob is not None:
        c.execute("UPDATE settings SET background_blob=? WHERE user_id=?", (bg_blob, user_id))
    conn.commit()

def get_background_blob(user_id: int):
    c.execute("SELECT background_blob FROM settings WHERE user_id=?", (user_id,))
    r = c.fetchone()
    return r[0] if r else None

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

# -----------------------
# Email sending (immediate)
# -----------------------
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
    results = {"sent":0, "failed":0}
    for rid, title, message, recipient, host, port, mail, pw in rows:
        if not (host and port and mail and pw):
            results["failed"] += 1
            continue
        try:
            send_email_via_smtp(host, port, mail, pw, recipient, title or "Reminder", message or "")
            mark_reminder_sent(rid)
            results["sent"] += 1
        except Exception:
            results["failed"] += 1
    return results

# -----------------------
# Planner logic
# -----------------------
def lbs_to_kg(lbs): return lbs * 0.45359237
def kg_to_lbs(kg): return kg * 2.20462
def bmi_calc(weight_kg, height_m):
    return weight_kg / (height_m**2) if height_m > 0 else None

BASE_MEALS = {
    "Breakfast": ["Oatmeal + banana", "Scrambled eggs + toast", "Smoothie + protein", "Pancakes + berries", "Boiled eggs + avocado"],
    "Lunch": ["Grilled chicken + veggies", "Beef stir-fry + rice", "Tuna salad + greens", "Rice & beans", "Turkey sandwich"],
    "Dinner": ["Salmon + brown rice", "Grilled fish + salad", "Steak + vegetables", "Pasta + chicken", "Vegetable soup + bread"],
    "Snack": ["Nuts", "Yogurt", "Apple", "Carrots & hummus", "Granola"]
}

def meal_default_time(meal_type):
    return {"Breakfast":"08:00","Lunch":"13:00","Dinner":"19:00","Snack":"16:00"}.get(meal_type,"12:00")

def estimate_maintenance_calories(weight_kg):
    return max(1200, weight_kg * 25)

def make_weekly_meal_plan(target_cal):
    dist = {"Breakfast":0.25, "Lunch":0.30, "Dinner":0.30, "Snack":0.15}
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {}
    for i, day in enumerate(days):
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
            plan[d] = [{"time":"06:30","activity":"Cardio (30 min)"}] if d not in ["Tuesday","Thursday"] else [{"time":"07:00","activity":"Mobility (20 min)"}]
        elif bmi_cat == "Overweight":
            plan[d] = [{"time":"06:00","activity":"Brisk walk (35 min)"}] if d not in ["Tuesday","Thursday"] else [{"time":"06:00","activity":"Strength (25 min)"}]
        else:
            plan[d] = [{"time":"06:00","activity":"Low-impact cardio (30-40 min)"}]
    return plan

# -----------------------
# UI helpers
# -----------------------
def render_background_from_blob(blob):
    if not blob:
        return
    try:
        mime_type = "image/png"
        b64 = base64.b64encode(blob).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.18), rgba(0,0,0,0.18)), url("data:{mime_type};base64,{b64}");
            background-size: cover;
            background-position: center;
        }}
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        pass

# -----------------------
# App UI: Auth
# -----------------------
if "user" not in st.session_state:
    st.session_state.user = None

st.title("⚖️ LMB Weight Scale Checker")

if not st.session_state.user:
    tabs = st.tabs(["Login", "Sign Up"])
    with tabs[0]:
        st.subheader("Login")
        login_email = st.text_input("Email", key="login_email")
        login_pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            u = authenticate(login_email.strip().lower(), login_pw)
            if u:
                st.session_state.user = u
                st.success("Logged in — welcome!")
                st.rerun()   # corrected call
            else:
                st.error("Invalid credentials")
    with tabs[1]:
        st.subheader("Sign Up (auto-login)")
        signup_email = st.text_input("Email", key="signup_email")
        signup_pw = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Sign Up"):
            ok, err = create_user(signup_email.strip().lower(), signup_pw)
            if ok:
                st.session_state.user = get_user_by_email(signup_email.strip().lower())
                st.success("Account created & logged in!")
                st.rerun()   # corrected call
            else:
                st.error(err)
    st.stop()

# -----------------------
# Logged in UI
# -----------------------
user = st.session_state.user
user_id = user[0]
settings = get_settings(user_id)

# apply saved background if any
bg_blob = get_background_blob(user_id)
if bg_blob:
    render_background_from_blob(bg_blob)

# Sidebar & navigation
st.sidebar.markdown(f"**User:** {user[1]}")
page = st.sidebar.radio("Navigate", ["Home","Settings","Reminders","Saved Reminders","Logout"])

if page == "Logout":
    st.session_state.user = None
    st.rerun()

# -----------------------
# Home page: measurements & planners
# -----------------------
if page == "Home":
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
    bmi = bmi_calc(weight_kg, height_m)
    if bmi:
        cat = "Underweight" if bmi<18.5 else "Normal" if bmi<25 else "Overweight" if bmi<30 else "Obese"
        st.metric("BMI", f"{bmi:.1f}", delta=cat)
        maintenance = estimate_maintenance_calories(weight_kg)
        target = maintenance + 500 if cat=="Underweight" else maintenance if cat=="Normal" else max(1200, maintenance-400) if cat=="Overweight" else max(1200, maintenance-600)
        st.write(f"Estimated maintenance: **{int(maintenance)} kcal/day** — target: **{int(target)} kcal/day**")
        if st.button("Generate weekly meal & exercise plan"):
            weekly_meals = make_weekly_meal_plan(target)
            weekly_ex = make_weekly_exercise_plan(cat)
            st.session_state["latest_plan"] = {"created":datetime.utcnow().isoformat(), "weight_kg":weight_kg, "height_m":height_m, "bmi":bmi, "bmi_category":cat, "target":int(target), "meals":weekly_meals, "exercise":weekly_ex}
            st.success("Generated — scroll down to view.")
    if "latest_plan" in st.session_state:
        p = st.session_state["latest_plan"]
        st.subheader("Weekly Meal Plan")
        for day, meals in p["meals"].items():
            with st.expander(f"{day} — approx {sum(m['cal'] for m in meals.values())} kcal"):
                for meal_name, meal_info in meals.items():
                    st.write(f"- **{meal_name} ({meal_info['time']})**: {meal_info['item']} — approx **{meal_info['cal']} kcal**")
        st.subheader("Weekly Exercise Plan")
        for day, acts in p["exercise"].items():
            with st.expander(day):
                for a in acts:
                    st.write(f"- {a['time']} — {a['activity']}")
        # allow download
        st.download_button("Download plan (JSON)", data=json.dumps(p, indent=2), file_name="weekly_plan.json", mime="application/json")

# -----------------------
# Settings page
# -----------------------
elif page == "Settings":
    st.header("⚙️ Settings & Customization")
    theme = st.selectbox("Theme", ["light","dark"], index=0 if settings["theme"]=="light" else 1)
    accent = st.color_picker("Accent color", settings["accent_color"] or "#667eea")
    st.markdown("Upload a background image (drag & drop supported)")
    bg = st.file_uploader("Background image", type=["png","jpg","jpeg"])
    st.markdown("### SMTP (optional) — used to send reminder emails")
    smtp_host = st.text_input("SMTP host (e.g. smtp.gmail.com)", value=settings.get("smtp_host") or "")
    smtp_port = st.number_input("SMTP port", value=int(settings.get("smtp_port") or 587))
    smtp_email = st.text_input("SMTP login email", value=settings.get("smtp_email") or "")
    smtp_password = st.text_input("SMTP password (will be stored)", type="password", value=settings.get("smtp_password") or "")
    if st.button("Save settings"):
        blob = bg.read() if bg else None
        smtp = {"host": smtp_host or None, "port": smtp_port or None, "email": smtp_email or None, "password": smtp_password or None}
        save_settings(user_id, theme, accent, smtp=smtp, bg_blob=blob)
        st.success("Settings saved. Background will apply on reload.")
        st.rerun()

# -----------------------
# Reminders page
# -----------------------
elif page == "Reminders":
    st.header("⏰ Reminders")
    st.info("You can Save a reminder for later delivery or Send Now using the SMTP settings configured in Settings.")
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
        if not s.get("smtp_host") or not s.get("smtp_email") or not s.get("smtp_password"):
            st.error("SMTP not configured. Add SMTP details in Settings.")
        else:
            try:
                send_email_via_smtp(s["smtp_host"], s["smtp_port"] or 587, s["smtp_email"], s["smtp_password"], recipient, title or "Reminder", message or "")
                st.success("Email sent.")
            except Exception as e:
                st.error(f"Failed to send email: {e}")
    st.markdown("---")
    st.subheader("Pending reminders")
    rems = list_reminders(user_id, include_sent=False)
    if rems:
        for rid, t, rec, send_at, sent in rems:
            st.write(f"- **{t}** → {rec} at {send_at}")
            cols = st.columns([1,1])
            if cols[0].button("Send now", key=f"send_{rid}"):
                s = get_settings(user_id)
                if not s.get("smtp_host") or not s.get("smtp_email") or not s.get("smtp_password"):
                    st.error("Set SMTP in Settings first.")
                else:
                    try:
                        send_email_via_smtp(s["smtp_host"], s["smtp_port"] or 587, s["smtp_email"], s["smtp_password"], rec, t or "Reminder", "Scheduled reminder")
                        mark_reminder_sent(rid)
                        st.success("Sent & marked as sent.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to send: {e}")
            if cols[1].button("Delete", key=f"del_{rid}"):
                c.execute("DELETE FROM reminders WHERE id=?", (rid,))
                conn.commit()
                st.experimental_rerun()

# -----------------------
# Saved Reminders page
# -----------------------
elif page == "Saved Reminders":
    st.header("Saved reminders (all)")
    allr = list_reminders(user_id, include_sent=True)
    if allr:
        for rid, t, rec, send_at, sent in allr:
            st.write(f"- {t} → {rec} at {send_at} — {'SENT' if sent else 'PENDING'}")
    else:
        st.write("No reminders saved yet.")
