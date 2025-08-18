import streamlit as st
import sqlite3, bcrypt, base64, mimetypes

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Weight Converter", page_icon="⚖️", layout="centered")

DB = "users.db"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    conn.commit(); conn.close()

def add_user(username, password):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users VALUES (?, ?)", (username, hashed))
    conn.commit(); conn.close()

def check_user(username, password):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    return row and bcrypt.checkpw(password.encode(), row[0].encode())

init_db()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = ""

# ---------------- BACKGROUND ----------------
def set_bg(upload):
    if upload:
        mime, _ = mimetypes.guess_type(upload.name)
        data = base64.b64encode(upload.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:{mime};base64,{data}");
            background-size: cover; background-position: center;
        }}
        .card {{
            background: rgba(255,255,255,0.8);
            padding: 20px; border-radius: 15px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            margin: 15px 0;
        }}
        </style>
        """, unsafe_allow_html=True)

# ---------------- CALCULATOR ----------------
def converter_page():
    st.title(f"⚖️ Weight Converter - Welcome {st.session_state.user}")
    if st.button("🚪 Logout"): 
        st.session_state.logged_in=False; st.experimental_rerun()

    bg = st.file_uploader("Upload background", type=["jpg","png"])
    set_bg(bg)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    unit = st.selectbox("Select unit", ["Kilograms", "Pounds"])
    weight = st.number_input("Enter weight", min_value=0.1, step=0.1)
    st.markdown("</div>", unsafe_allow_html=True)

    if weight:
        if unit=="Kilograms":
            lbs = weight * 2.20462
            st.markdown(f"<div class='card'><b>{weight:.1f} kg = {lbs:.1f} lbs</b></div>", unsafe_allow_html=True)
            weight_kg = weight
        else:
            kg = weight * 0.453592
            st.markdown(f"<div class='card'><b>{weight:.1f} lbs = {kg:.1f} kg</b></div>", unsafe_allow_html=True)
            weight_kg = kg

        height = st.number_input("Enter height (m)", min_value=0.5, max_value=3.0, value=1.70)
        bmi = weight_kg/(height**2)

        if bmi < 18.5:
            color = "#3498db"; status = "Underweight"
        elif bmi < 25:
            color = "#2ecc71"; status = "Normal"
        elif bmi < 30:
            color = "#f39c12"; status = "Overweight"
        else:
            color = "#e74c3c"; status = "Obese"

        st.markdown(f"""
        <div class='card' style='background:{color}; color:white; text-align:center;'>
            <h3>BMI: {bmi:.1f} ({status})</h3>
        </div>
        """, unsafe_allow_html=True)

# ---------------- AUTH ----------------
def login_page():
    st.title("🔑 Login / Sign Up")
    tab = st.radio("Choose", ["Login","Sign Up"])
    if tab=="Login":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login") and check_user(u,p):
            st.session_state.logged_in=True; st.session_state.user=u; st.experimental_rerun()
    else:
        u = st.text_input("New Username")
        p1 = st.text_input("Password", type="password")
        p2 = st.text_input("Confirm Password", type="password")
        if st.button("Sign Up"):
            if p1==p2 and u:
                try: add_user(u,p1); st.success("✅ Account created! Please login.")
                except: st.error("⚠️ User already exists")
            else: st.error("❌ Passwords must match")

# ---------------- MAIN ----------------
if st.session_state.logged_in:
    converter_page()
else:
    login_page()
