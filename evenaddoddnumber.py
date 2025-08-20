import streamlit as st
import base64
import mimetypes
import sqlite3
import bcrypt

# =================== CONFIG ===================
st.set_page_config(
    page_title="Weight Converter & BMI",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DB_FILE = "users.db"

# =================== DATABASE ===================
def init_db():
    """Initialize user database."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_user(username: str, password: str):
    """Add a new user to the database."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
    conn.commit()
    conn.close()

def get_user(username: str):
    """Retrieve user by username."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT username, password_hash FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    return user

# =================== SESSION STATE ===================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "auth_tab" not in st.session_state:
    st.session_state.auth_tab = "Login"
if "bg_uploaded" not in st.session_state:
    st.session_state.bg_uploaded = None

init_db()

# =================== STYLES ===================
def inject_custom_css():
    st.markdown("""
    <style>
    * { font-family: 'Segoe UI', sans-serif; }
    .main-container { max-width: 800px; margin: 0 auto; padding: 20px; }
    .metric-card, .result-card, .info-card, .title-header {
        background: rgba(255,255,255,0.85);
        padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        color: black;
    }
    .metric-card { text-align: center; font-weight: bold; }
    .result-card { text-align: center; font-size: 18px; margin: 15px 0; }
    .bmi-card { border-radius: 30px !important; font-size: 20px; font-weight: bold; padding: 20px; }
    .title-header { font-size: 2.2rem; text-align: center; font-weight: bold; margin-bottom: 30px; }
    </style>
    """, unsafe_allow_html=True)

# =================== BACKGROUND ===================
def apply_background(bg_image):
    """Set custom background image."""
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded_image = base64.b64encode(bg_image.read()).decode()
        st.session_state.bg_uploaded = True
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:{mime_type};base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """, unsafe_allow_html=True)

# =================== CONVERSIONS ===================
def kg_to_lbs(kg): return kg * 2.20462
def lbs_to_kg(lbs): return lbs * 0.453592

def get_bmi_category(bmi):
    """Return BMI category, emoji, and style."""
    if bmi < 18.5:
        return "Underweight", "🔵", "background-color: rgba(0, 123, 255, 0.85); color: white;"
    elif 18.5 <= bmi < 25:
        return "Normal weight", "🟢", "background-color: rgba(40, 167, 69, 0.85); color: white;"
    elif 25 <= bmi < 30:
        return "Overweight", "🟡", "background-color: rgba(255, 193, 7, 0.85); color: white;"
    else:
        return "Obese", "🔴", "background-color: rgba(220, 53, 69, 0.85); color: white;"

def feet_inches_to_meters(feet: float, inches: float) -> float:
    """Convert feet/inches to meters."""
    total_inches = (feet * 12) + inches
    return total_inches * 0.0254

# =================== AUTH ===================
def login_view():
    st.markdown('<div class="title-header">🔑 Login</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        user = get_user(username.strip())
        if user and bcrypt.checkpw(password.encode(), user[1].encode()):
            st.session_state.logged_in = True
            st.session_state.username = user[0]
            st.success(f"✅ Welcome back, {user[0]}!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

def signup_view():
    st.markdown('<div class="title-header">📝 Sign Up</div>', unsafe_allow_html=True)
    with st.form("signup_form"):
        username = st.text_input("Choose Username")
        pw1 = st.text_input("Choose Password", type="password")
        pw2 = st.text_input("Confirm Password", type="password")
        create_btn = st.form_submit_button("Create Account")

    if create_btn:
        u = username.strip()
        if not u or not pw1 or not pw2:
            st.warning("⚠️ Please fill all fields.")
        elif " " in u:
            st.warning("⚠️ Username cannot contain spaces.")
        elif len(pw1) < 4:
            st.warning("⚠️ Password must be at least 4 characters.")
        elif pw1 != pw2:
            st.error("❌ Passwords do not match.")
        elif get_user(u):
            st.error("❌ Username already exists.")
        else:
            add_user(u, pw1)
            st.session_state.logged_in = True
            st.session_state.username = u
            st.success("🎉 Account created. You are now logged in.")
            st.rerun()

def auth_gate():
    inject_custom_css()
    tab = st.radio("Choose Option", ["Login", "Sign Up"], index=0 if st.session_state.auth_tab == "Login" else 1)
    st.session_state.auth_tab = tab
    login_view() if tab == "Login" else signup_view()

# =================== MAIN APP ===================
def app_page():
    inject_custom_css()
    st.markdown(f'<div class="title-header">⚖️ Welcome {st.session_state["username"]}! ⚖️</div>', unsafe_allow_html=True)

    if st.button("🚪 Logout", use_container_width=True):
        for key in st.session_state.keys():
            st.session_state[key] = None
        st.session_state.logged_in = False
        st.success("👋 Logged out.")
        st.rerun()

    # Upload background image
    bg_image = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png"])
    apply_background(bg_image)

    # Weight input
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="info-card">📏 Select Unit</div>', unsafe_allow_html=True)
        unit = st.selectbox("", ["Kilograms (kg)", "Pounds (lbs)"])
    with col2:
        st.markdown('<div class="info-card">🔢 Enter Weight</div>', unsafe_allow_html=True)
        weight = st.number_input("", min_value=0.1, max_value=999.9, step=0.1, format="%.1f")

    if weight > 0:
        if "Kilograms" in unit:
            converted = kg_to_lbs(weight)
            stones = converted / 14
            ounces = converted * 16
            grams = weight * 1000
        else:
            converted = lbs_to_kg
