import streamlit as st
import sqlite3, os, base64, mimetypes
from passlib.hash import bcrypt
from datetime import datetime
import random

# ==============================
# Database Setup
# ==============================
DB_FILE = "lmb_weight_scale.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            password TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            user_id INTEGER,
            theme TEXT,
            backdrop_color TEXT,
            bg_blob BLOB,
            bg_mime TEXT
        )""")
        conn.commit()

# ==============================
# DB Helpers
# ==============================
def create_user(username, email, password):
    hashed = bcrypt.hash(password)
    with sqlite3.connect(DB_FILE) as conn:
        try:
            conn.execute("INSERT INTO users(username,email,password) VALUES(?,?,?)",
                         (username, email, hashed))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def verify_user(username, password):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT id,password FROM users WHERE username=?",(username,)).fetchone()
        if row and bcrypt.verify(password,row[1]):
            return row[0]
    return None

def get_settings(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT theme,backdrop_color,bg_blob,bg_mime FROM settings WHERE user_id=?",(user_id,)).fetchone()
        if row:
            return {"theme":row[0],"backdrop_color":row[1],"bg_blob":row[2],"bg_mime":row[3]}
        return {}

def save_settings(user_id, theme, backdrop, bg_blob=None, bg_mime=None):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM settings WHERE user_id=?",(user_id,))
        conn.execute("INSERT INTO settings(user_id,theme,backdrop_color,bg_blob,bg_mime) VALUES(?,?,?,?,?)",
                     (user_id, theme, backdrop, bg_blob, bg_mime))
        conn.commit()

# ==============================
# Styling Functions
# ==============================
def apply_theme(theme, backdrop_color):
    if theme == "dark":
        base_bg = "#0b0f12"
        text = "#e6eef6"
    else:
        base_bg = "#ffffff"
        text = "#0b1724"

    css = f"""
    <style>
    .stApp {{
        background-color: {base_bg};
        color: {text};
    }}
    .stButton>button, .stDownloadButton>button {{
        background-color: #667eea;
        color: white;
        border-radius: 8px;
    }}
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div,
    .stTextArea textarea {{
        border: 1px solid #667eea !important;
        border-radius: 6px;
        background-color: rgba(255,255,255,0.85);
    }}
    .stMarkdown, .stMetric, .stExpander, .stText, .stSubheader, .stHeader {{
        background-color: rgba(0,0,0,0.4);
        padding: 0.4rem 0.6rem;
        border-radius: 6px;
        color: {text};
    }}
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background-color: {backdrop_color}55;
        z-index: -1;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_background_from_blob(blob, mime):
    if not blob: return
    try:
        b64 = base64.b64encode(blob).decode()
        css = f"""
        <style>
        .stApp {{
            background-image: url("data:{mime};base64,{b64}");
            background-size: cover;
            background-position: center;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    except Exception:
        pass

# ==============================
# Weight / BMI / Plans
# ==============================
def kg_to_lbs(kg): return kg*2.20462
def lbs_to_kg(lbs): return lbs*0.453592

def get_bmi_category(bmi):
    if bmi < 18.5: return "Underweight","🔵"
    elif bmi < 25: return "Normal","🟢"
    elif bmi < 30: return "Overweight","🟡"
    return "Obese","🔴"

def weekly_meal_plan(category):
    plans = {
        "Underweight": ["🍞 Avocado toast","🍗 Grilled chicken","🥩 Beef stew","🍝 Pasta","🥜 Nuts","🥛 Smoothie","🍚 Rice & beans"],
        "Normal": ["🥗 Salad","🍲 Soup","🍳 Omelet","🍠 Sweet potato","🐟 Salmon","🍌 Fruits","🥒 Veggies & hummus"],
        "Overweight": ["🥦 Steamed veggies","🍎 Fruits","🥗 Green salad","🐓 Lean chicken","🍵 Herbal tea","🍠 Baked potato","🍲 Light soup"],
        "Obese": ["🥬 Kale salad","🥒 Cucumber & hummus","🍎 Apple & nuts","🐟 Grilled fish","🍵 Green tea","🥦 Broccoli","🍲 Veggie soup"]
    }
    return plans.get(category,["🥗 Balanced meals daily"])

def weekly_workout_plan(category):
    plans = {
        "Underweight": ["🏋️ Strength training","🚶 Light cardio","🧘 Yoga","🏋️ Bodyweight","🚴 Cycling","🤸 Flexibility","🏊 Swimming"],
        "Normal": ["🏃 Jogging","🏋️ Gym","🧘 Yoga","🚶 Walking","🚴 Cycling","🏊 Swimming","🤸 Mixed"],
        "Overweight": ["🚶 Brisk walk","🏊 Swimming","🚴 Cycling","🧘 Yoga","🏋️ Light weights","🤸 Aerobics","🚶 Hiking"],
        "Obese": ["🚶 Slow walk","🪑 Chair yoga","🚴 Stationary bike","🧘 Breathing","🚶 Water walking","🤸 Stretch","🚶 Easy walk"]
    }
    return plans.get(category,["🚶 Stay active daily"])

# ==============================
# Pages
# ==============================
def page_dashboard(user_id, settings):
    st.header("⚖️ LMB Weight Scale Checker")

    col1,col2 = st.columns(2)
    with col1: unit = st.selectbox("Select Unit",["Kilograms","Pounds"])
    with col2: weight = st.number_input("Enter Weight",0.1,999.9,70.0,0.1)

    height_ft = st.number_input("Height (ft)",1,8,5)
    height_in = st.number_input("Height (in)",0,11,6)
    height_m = height_ft*0.3048 + height_in*0.0254

    if unit=="Kilograms":
        kg = weight; lbs = kg_to_lbs(weight)
    else:
        kg = lbs_to_kg(weight); lbs = weight

    bmi = kg/(height_m**2)
    cat,emoji = get_bmi_category(bmi)

    st.success(f"Weight: {kg:.1f}kg / {lbs:.1f}lbs\n\nBMI: {bmi:.1f} → {emoji} {cat}")

    st.subheader("🍴 Weekly Meal Plan")
    for d,m in enumerate(weekly_meal_plan(cat),1): st.write(f"Day {d}: {m}")

    st.subheader("💪 Weekly Workout Plan")
    for d,w in enumerate(weekly_workout_plan(cat),1): st.write(f"Day {d}: {w}")

def page_settings(user_id, settings):
    st.header("⚙️ Settings & Customization")
    theme = st.selectbox("Theme",["light","dark"], index=0 if settings.get("theme","light")=="light" else 1)
    backdrop = st.color_picker("Backdrop Tint", settings.get("backdrop_color") or "#667eea")
    bg_file = st.file_uploader("Upload background",["png","jpg","jpeg"])
    if st.button("Save Settings"):
        blob,mime = (None,None)
        if bg_file:
            blob = bg_file.read()
            mime,_ = mimetypes.guess_type(bg_file.name)
        save_settings(user_id, theme, backdrop, blob, mime)
        st.success("✅ Saved! Refresh to apply")

# ==============================
# Main
# ==============================
def main():
    st.set_page_config("LMB Weight Scale Checker","⚖️",layout="centered")
    init_db()

    if "user_id" not in st.session_state: st.session_state.user_id=None

    if not st.session_state.user_id:
        choice = st.sidebar.radio("Login/Signup",["Login","Signup"])
        if choice=="Login":
            u=st.text_input("Username"); p=st.text_input("Password",type="password")
            if st.button("Login"):
                uid=verify_user(u,p)
                if uid: st.session_state.user_id=uid; st.experimental_rerun()
                else: st.error("❌ Invalid login")
        else:
            u=st.text_input("Username"); e=st.text_input("Email"); p=st.text_input("Password",type="password")
            if st.button("Signup"):
                if create_user(u,e,p):
                    uid=verify_user(u,p)
                    st.session_state.user_id=uid
                    st.experimental_rerun()
                else: st.error("❌ Username exists")
        return

    uid=st.session_state.user_id
    settings=get_settings(uid)
    apply_theme(settings.get("theme","light"),settings.get("backdrop_color") or "#667eea")
    render_background_from_blob(settings.get("bg_blob"), settings.get("bg_mime"))

    st.sidebar.title("Navigation")
    page=st.sidebar.radio("Go to",["Dashboard","Settings","Logout"])
    if page=="Dashboard": page_dashboard(uid,settings)
    elif page=="Settings": page_settings(uid,settings)
    elif page=="Logout": st.session_state.user_id=None; st.experimental_rerun()

if __name__=="__main__":
    main()
