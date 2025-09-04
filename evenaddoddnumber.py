# app.py
import streamlit as st
import sqlite3
import bcrypt
import base64
import mimetypes
import json
import os
from datetime import datetime, date, timedelta
import smtplib
from email.message import EmailMessage

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="LMB Weight Scale Checker", page_icon="⚖️", layout="centered")
DB_PATH = "users.db"

# -----------------------
# DB connection & schema
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

# Settings
c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER UNIQUE,
    theme TEXT DEFAULT 'light',
    accent_color TEXT DEFAULT '#667eea'
)
""")
conn.commit()

# Add optional columns
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
# Utility functions
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
# APP START
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

# --- MAIN APP ---
user = st.session_state.user
user_id = user[0]
settings = get_settings(user_id)

apply_theme(settings.get("theme") or "light", settings.get("accent_color") or "#667eea")
bg_blob, bg_mime = settings.get("background_blob"), settings.get("background_mime")
if bg_blob:
    render_background_from_blob(bg_blob, bg_mime)

# Sidebar
st.sidebar.markdown(f"**User:** {user[1]}")
nav = st.sidebar.radio("Navigate", ["Home","Settings","Reminders","Saved Plans","Logout"])

if nav == "Logout":
    st.session_state.user = None
    st.rerun()

# --- SETTINGS PAGE (updated with Remove Background) ---
elif nav == "Settings":
    st.header("⚙️ Settings & Customization")
    st.write("Customize theme, pick accent color, upload/remove a background, and configure SMTP for reminders.")

    theme_choice = st.selectbox("Theme", ["light","dark"], index=0 if settings.get("theme","light")=="light" else 1)
    accent = st.color_picker("Accent color", settings.get("accent_color") or "#667eea")

    uploaded = st.file_uploader("Upload background image", type=["jpg","jpeg","png"])

    if st.button("Remove Background"):
        c.execute("UPDATE settings SET background_blob=NULL, background_mime=NULL WHERE user_id=?", (user_id,))
        conn.commit()
        st.success("Background removed.")
        st.rerun()

    st.markdown("#### Optional: SMTP (for reminders)")
    smtp_host = st.text_input("SMTP host", value=settings.get("smtp_host") or "")
    smtp_port = st.number_input("SMTP port", value=int(settings.get("smtp_port") or 587))
    smtp_email = st.text_input("SMTP login email", value=settings.get("smtp_email") or "")
    smtp_password = st.text_input("SMTP password", type="password", value=settings.get("smtp_password") or "")

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
