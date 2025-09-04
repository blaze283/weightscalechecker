import streamlit as st
import sqlite3
import bcrypt
import json
import mimetypes
import base64
from datetime import datetime

# ---------------- DATABASE ---------------- #
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()

# Users
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT
)
""")

# Settings
c.execute("""
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER UNIQUE,
    theme TEXT DEFAULT 'light',
    accent_color TEXT DEFAULT '#4CAF50',
    background_blob BLOB,
    background_mime TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# Saved plans
c.execute("""
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    created_at TEXT,
    plan_json TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# ---------------- HELPERS ---------------- #
def create_user(email, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(email, password):
    c.execute("SELECT id, password FROM users WHERE email=?", (email,))
    row = c.fetchone()
    if row and bcrypt.checkpw(password.encode(), row[1]):
        return row[0]
    return None

def get_settings(user_id):
    c.execute("SELECT theme, accent_color, background_blob, background_mime FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        return {"theme": row[0], "accent_color": row[1], "background_blob": row[2], "background_mime": row[3]}
    else:
        c.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return {"theme": "light", "accent_color": "#4CAF50", "background_blob": None, "background_mime": None}

def save_settings(user_id, theme, accent_color, bg_blob=None, bg_mime=None):
    c.execute("""
        UPDATE settings
        SET theme=?, accent_color=?, background_blob=?, background_mime=?
        WHERE user_id=?
    """, (theme, accent_color, bg_blob, bg_mime, user_id))
    conn.commit()

def save_plan(user_id, plan_dict):
    c.execute("INSERT INTO plans (user_id, created_at, plan_json) VALUES (?, ?, ?)",
              (user_id, datetime.now().isoformat(), json.dumps(plan_dict)))
    conn.commit()

def get_plans(user_id):
    c.execute("SELECT created_at, plan_json FROM plans WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    return [(row[0], json.loads(row[1])) for row in c.fetchall()]

def apply_theme(theme, accent_color):
    if theme == "dark":
        bg_color, text_color = "#121212", "#e0e0e0"
    else:
        bg_color, text_color = "#ffffff", "#000000"
    css = f"""
    <style>
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
    }}
    .stButton>button {{
        background-color: {accent_color};
        color: white;
        border-radius: 8px;
        padding: 0.4em 1em;
        border: none;
    }}
    .stButton>button:hover {{ opacity: 0.9; }}
    .stTextInput>div>div>input, .stNumberInput input {{
        border: 1px solid {accent_color};
        border-radius: 6px;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_background(blob, mime):
    if blob and mime:
        encoded = base64.b64encode(blob).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:{mime};base64,{encoded}");
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# ---------------- MEAL & WORKOUT GENERATOR ---------------- #
def generate_plan(bmi_category, calories):
    meal_templates = {
        "Underweight": ["Oatmeal", "Chicken & Rice", "Protein Shake", "Steak & Potatoes"],
        "Normal": ["Greek Yogurt", "Salad + Tuna", "Fruit Snack", "Fish & Veggies"],
        "Overweight": ["Smoothie", "Grilled Chicken", "Nuts", "Salmon & Quinoa"],
        "Obese": ["Veggie Omelet", "Soup & Salad", "Fruit", "Lean Protein + Veggies"],
    }
    workouts = {
        "Underweight": ["Strength Training", "Compound Lifts"],
        "Normal": ["Mixed Cardio & Strength"],
        "Overweight": ["Moderate Cardio", "Strength (Light)"],
        "Obese": ["Low-impact Cardio", "Stretching"],
    }
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {"meals": {}, "workouts": {}}
    for day in days:
        plan["meals"][day] = [
            {"meal": meal_templates[bmi_category][0], "time": "08:00"},
            {"meal": meal_templates[bmi_category][1], "time": "13:00"},
            {"meal": meal_templates[bmi_category][2], "time": "16:00"},
            {"meal": meal_templates[bmi_category][3], "time": "19:00"},
        ]
        plan["workouts"][day] = [
            {"workout": workouts[bmi_category][0], "time": "06:00"},
            {"workout": workouts[bmi_category][1], "time": "18:00"},
        ]
    return plan

# ---------------- APP ---------------- #
st.set_page_config(page_title="LMB Weight Scale Checker", layout="centered")

if "user_id" not in st.session_state:
    st.session_state.user_id = None

menu = ["Login", "Sign Up"] if not st.session_state.user_id else ["Home", "Saved Plans", "Settings", "Logout"]
choice = st.sidebar.selectbox("Menu", menu)

# ---- SIGN UP ----
if choice == "Sign Up":
    st.subheader("Create Account")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if create_user(email, password):
            st.success("Account created! Please login.")
        else:
            st.error("Email already exists.")

# ---- LOGIN ----
elif choice == "Login":
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user_id = authenticate_user(email, password)
        if user_id:
            st.session_state.user_id = user_id
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials.")

# ---- LOGGED IN ----
elif st.session_state.user_id:
    user_id = st.session_state.user_id
    settings = get_settings(user_id)

    # Apply theme + background
    apply_theme(settings["theme"], settings["accent_color"])
    render_background(settings["background_blob"], settings["background_mime"])

    # ---- HOME ----
    if choice == "Home":
        st.title("🏋️ LMB Weight Scale Checker")
        weight = st.number_input("Enter your weight (kg)", min_value=1.0, max_value=300.0, step=0.1)
        height_ft = st.number_input("Height (feet)", min_value=1, max_value=8, step=1)
        height_in = st.number_input("Height (inches)", min_value=0, max_value=11, step=1)
        if weight and height_ft:
            height_m = height_ft * 0.3048 + height_in * 0.0254
            bmi = weight / (height_m**2)
            if bmi < 18.5: cat = "Underweight"
            elif bmi < 25: cat = "Normal"
            elif bmi < 30: cat = "Overweight"
            else: cat = "Obese"
            st.write(f"**BMI: {bmi:.1f} → {cat}**")
            calories = 2200 if cat=="Normal" else (2500 if cat=="Underweight" else 1800)
            if st.button("Generate Weekly Meal & Exercise Plan"):
                plan = generate_plan(cat, calories)
                save_plan(user_id, plan)
                st.success("Plan generated and saved!")
                st.json(plan)

    # ---- SAVED PLANS ----
    elif choice == "Saved Plans":
        st.subheader("📚 Your Saved Plans")
        plans = get_plans(user_id)
        if not plans:
            st.info("No saved plans yet.")
        else:
            for created, plan in plans:
                with st.expander(f"Plan from {created}"):
                    st.json(plan)

    # ---- SETTINGS ----
    elif choice == "Settings":
        st.subheader("Customize your app")
        theme_choice = st.radio("Theme", ["light", "dark"], index=0 if settings["theme"]=="light" else 1)
        accent = st.color_picker("Pick accent color", settings["accent_color"])
        uploaded = st.file_uploader("Upload background image", type=["png","jpg","jpeg"])
        blob, mime = settings["background_blob"], settings["background_mime"]
        if uploaded:
            blob = uploaded.read()
            mime = mimetypes.guess_type(uploaded.name)[0] or "image/png"
        if st.button("Save Settings"):
            save_settings(user_id, theme_choice, accent, blob, mime)
            st.success("Settings updated!")
            st.rerun()

    # ---- LOGOUT ----
    elif choice == "Logout":
        st.session_state.user_id = None
        st.success("Logged out.")
        st.rerun()
