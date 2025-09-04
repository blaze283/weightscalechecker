import streamlit as st
import sqlite3
import bcrypt
import base64
from datetime import datetime
import smtplib
from email.message import EmailMessage

# -----------------------
# App Config
# -----------------------
st.set_page_config(page_title="LMB Weight Scale Checker", page_icon="⚖️", layout="centered")
DB_PATH = "users.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# -----------------------
# Database Setup
# -----------------------
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT
)
""")
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
# Helpers
# -----------------------
def hash_password(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def verify_password(pw, hashed): return bcrypt.checkpw(pw.encode(), hashed.encode())

def create_user(email, password):
    try:
        h = hash_password(password)
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.lower(), h))
        conn.commit()
        uid = c.lastrowid
        c.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Email already exists."

def get_user(email):
    c.execute("SELECT * FROM users WHERE email=?", (email.lower(),))
    return c.fetchone()

def authenticate(email, pw):
    user = get_user(email)
    if user and verify_password(pw, user[2]):
        return user
    return None

def send_email(smtp_host, smtp_port, smtp_email, smtp_password, to_email, subject, body):
    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    server = smtplib.SMTP(smtp_host, int(smtp_port))
    server.starttls()
    server.login(smtp_email, smtp_password)
    server.send_message(msg)
    server.quit()

def check_and_send_reminders():
    now = datetime.utcnow().isoformat()
    c.execute("""SELECT r.id, r.title, r.message, r.recipient_email,
                        s.smtp_host, s.smtp_port, s.smtp_email, s.smtp_password
                 FROM reminders r JOIN settings s ON r.user_id=s.user_id
                 WHERE r.sent=0 AND r.send_at <= ?""", (now,))
    rows = c.fetchall()
    for rid, title, msg, rec, host, port, email, pw in rows:
        try:
            send_email(host, port, email, pw, rec, title, msg)
            c.execute("UPDATE reminders SET sent=1 WHERE id=?", (rid,))
            conn.commit()
        except Exception as e:
            st.error(f"Error sending reminder: {e}")

# -----------------------
# Weight / Meal / Exercise Logic
# -----------------------
def lbs_to_kg(lbs): return lbs * 0.45359237
def bmi(weight, height): return weight / (height**2) if height > 0 else None

def meal_plan(calories):
    return {
        "Breakfast": f"Oatmeal + fruit ({int(calories*0.25)} kcal)",
        "Lunch": f"Chicken + rice ({int(calories*0.3)} kcal)",
        "Dinner": f"Fish + vegetables ({int(calories*0.3)} kcal)",
        "Snack": f"Nuts ({int(calories*0.15)} kcal)"
    }

def exercise_plan(bmi_value):
    if bmi_value < 18.5:
        return ["Light cardio 15 min", "Strength training 20 min"]
    elif bmi_value < 25:
        return ["Cardio 30 min", "Strength training 30 min"]
    elif bmi_value < 30:
        return ["Brisk walk 40 min", "Strength training 20 min"]
    else:
        return ["Low-impact cardio 40 min", "Stretching 20 min"]

# -----------------------
# UI: Authentication
# -----------------------
if "user" not in st.session_state: st.session_state.user = None

st.title("⚖️ LMB Weight Scale Checker")

if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            user = authenticate(email, pw)
            if user:
                st.session_state.user = user
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")
    with tab2:
        email = st.text_input("New Email")
        pw = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            ok, err = create_user(email, pw)
            if ok:
                st.session_state.user = get_user(email)
                st.experimental_rerun()
            else:
                st.error(err)
    st.stop()

# -----------------------
# UI: Main App
# -----------------------
user = st.session_state.user
st.sidebar.write(f"Logged in as: {user[1]}")
page = st.sidebar.radio("Menu", ["Home", "Settings", "Reminders", "Logout"])

if page == "Logout":
    st.session_state.user = None
    st.experimental_rerun()

elif page == "Home":
    st.header("🏋️ Weight & Health Planner")
    unit = st.selectbox("Unit", ["kg", "lbs"])
    weight = st.number_input("Weight", min_value=1.0)
    feet = st.number_input("Height (feet)", min_value=1, max_value=8, value=5)
    inches = st.number_input("Height (inches)", min_value=0, max_value=11, value=7)

    height_m = (feet*12 + inches) * 0.0254
    weight_kg = weight if unit=="kg" else lbs_to_kg(weight)
    bmi_value = bmi(weight_kg, height_m)

    if bmi_value:
        st.write(f"Your BMI: **{bmi_value:.1f}**")
        meals = meal_plan(weight_kg*25)
        exercises = exercise_plan(bmi_value)
        st.subheader("Weekly Meal Plan")
        for k,v in meals.items(): st.write(f"- {k}: {v}")
        st.subheader("Weekly Exercise Plan")
        for e in exercises: st.write(f"- {e}")

elif page == "Settings":
    st.header("⚙️ Customize Your Page")
    theme = st.selectbox("Theme", ["Light", "Dark"])
    color = st.color_picker("Accent color", "#667eea")
    bg = st.file_uploader("Upload background image")
    if st.button("Save"):
        blob = bg.read() if bg else None
        c.execute("UPDATE settings SET theme=?, accent_color=?, background_blob=? WHERE user_id=?", (theme, color, blob, user[0]))
        conn.commit()
        st.success("Settings saved!")

elif page == "Reminders":
    st.header("⏰ Reminders")
    title = st.text_input("Title")
    msg = st.text_area("Message")
    rec = st.text_input("Recipient Email", value=user[1])
    send_at = st.text_input("Send at (YYYY-MM-DD HH:MM in UTC)")
    if st.button("Save Reminder"):
        c.execute("INSERT INTO reminders (user_id,title,message,recipient_email,send_at,created_at) VALUES (?,?,?,?,?,?)",
                  (user[0], title, msg, rec, send_at, datetime.utcnow().isoformat()))
        conn.commit()
        st.success("Reminder saved!")
    if st.button("Check & Send Reminders Now"):
        check_and_send_reminders()
        st.success("Checked reminders.")
