import streamlit as st
import base64
import mimetypes
import json
import os
import hashlib

# =================== CONFIG ===================
st.set_page_config(
    page_title="Weight Converter",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

USERS_FILE = "users.json"

# =================== SIMPLE PASSWORD HASH (demo) ===================
def hash_password(pw: str) -> str:
    # Demo-only hashing (no salt). For real apps, use bcrypt/argon2.
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

# =================== PERSISTENCE ===================
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

# Initialize session state
if "users" not in st.session_state:
    st.session_state.users = load_users()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "auth_tab" not in st.session_state:
    st.session_state.auth_tab = "Login"  # or "Sign Up"

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
    .upload-section {
        background: rgba(255,255,255,0.85); padding: 20px; border-radius: 12px;
        border: 2px dashed #dee2e6; margin: 20px 0; text-align: center;
    }
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.9);
        border-radius: 8px; border: 2px solid #ccc;
        font-size: 18px !important; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# =================== BACKGROUND ===================
def apply_background(bg_image):
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded_image = base64.b64encode(bg_image.read()).decode()
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
    if bmi < 18.5:
        return "Underweight", "🔵", "background-color: rgba(0, 123, 255, 0.85); color: white;"
    elif 18.5 <= bmi < 25:
        return "Normal weight", "🟢", "background-color: rgba(40, 167, 69, 0.85); color: white;"
    elif 25 <= bmi < 30:
        return "Overweight", "🟡", "background-color: rgba(255, 193, 7, 0.85); color: white;"
    else:
        return "Obese", "🔴", "background-color: rgba(220, 53, 69, 0.85); color: white;"

# =================== AUTH UI (FORMS) ===================
def login_view():
    st.markdown('<div class="title-header">🔑 Login</div>', unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        u = username.strip()
        p = password
        if u in st.session_state.users and st.session_state.users[u] == hash_password(p):
            st.session_state.logged_in = True
            st.session_state.username = u
            st.toast(f"Welcome back, {u}!", icon="✅")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

def signup_view():
    st.markdown('<div class="title-header">📝 Sign Up</div>', unsafe_allow_html=True)
    with st.form("signup_form", clear_on_submit=False):
        username = st.text_input("Choose Username", key="signup_username")
        pw1 = st.text_input("Choose Password", type="password", key="signup_pw1")
        pw2 = st.text_input("Confirm Password", type="password", key="signup_pw2")
        create_btn = st.form_submit_button("Create Account")

    if create_btn:
        u = username.strip()
        if not u or not pw1 or not pw2:
            st.warning("⚠️ Please fill all fields.")
            return
        if " " in u:
            st.warning("⚠️ Username cannot contain spaces.")
            return
        if len(pw1) < 4:
            st.warning("⚠️ Password must be at least 4 characters (demo constraint).")
            return
        if pw1 != pw2:
            st.error("❌ Passwords do not match.")
            return
        if u in st.session_state.users:
            st.error("❌ Username already exists.")
            return

        # Save to state + disk
        st.session_state.users[u] = hash_password(pw1)
        try:
            save_users(st.session_state.users)
        except Exception as e:
            st.error(f"Could not save user file: {e}")
            return

        # Auto-login after signup
        st.session_state.logged_in = True
        st.session_state.username = u
        st.toast("✅ Account created. You are now logged in.", icon="🎉")
        st.rerun()

def auth_gate():
    inject_custom_css()
    tab = st.segmented_control(
        "Authentication",
        options=["Login", "Sign Up"],
        default=st.session_state.auth_tab
    )
    st.session_state.auth_tab = tab
    if tab == "Login":
        login_view()
    else:
        signup_view()

# =================== APP PAGE ===================
def app_page():
    inject_custom_css()
    st.markdown(f'<div class="title-header">⚖️ Welcome {st.session_state["username"]}! ⚖️</div>', unsafe_allow_html=True)

    top_cols = st.columns([1,1,1])
    with top_cols[0]:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.toast("Logged out.", icon="👋")
            st.rerun()
    with top_cols[1]:
        pass
    with top_cols[2]:
        st.write("")  # spacer

    # Background
    bg_image = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png"])
    apply_background(bg_image)

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="info-card">📏 Select Unit</div>', unsafe_allow_html=True)
        unit = st.selectbox("", ["Kilograms (kg)", "Pounds (lbs)"], key="unit")

    with col2:
        st.markdown('<div class="info-card">🔢 Enter Weight</div>', unsafe_allow_html=True)
        weight = st.number_input("", min_value=0.1, max_value=999.9, step=0.1, format="%.1f")

    # Results
    if weight > 0:
        if "Kilograms" in unit:
            converted_weight = kg_to_lbs(weight)
            stones = converted_weight / 14
            ounces = converted_weight * 16
            grams = weight * 1000
        else:
            converted_weight = lbs_to_kg(weight)
            stones = weight / 14
            ounces = weight * 16
            grams = converted_weight * 1000

        st.markdown(f'''
        <div class="result-card">
            🎯 Conversion Result:<br><b>{weight:.1f} {unit} = {converted_weight:.1f} {'lbs' if "Kilograms" in unit else 'kg'}</b>
        </div>
        ''', unsafe_allow_html=True)

        col3, col4, col5 = st.columns(3)
        col3.markdown(f'<div class="metric-card">🪨 Stones<br>{stones:.1f}</div>', unsafe_allow_html=True)
        col4.markdown(f'<div class="metric-card">⚖️ Ounces<br>{ounces:.0f}</div>', unsafe_allow_html=True)
        col5.markdown(f'<div class="metric-card">📊 Grams<br>{grams:.0f}</div>', unsafe_allow_html=True)

        # BMI Calculator
        st.markdown('<div class="info-card">🧮 Quick BMI Calculator</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card">📏 Enter Your Height (m)</div>', unsafe_allow_html=True)
        height = st.number_input("", min_value=0.5, max_value=3.0, step=0.01, value=1.70)

        if height > 0:
            weight_kg = weight if "Kilograms" in unit else converted_weight
            bmi = weight_kg / (height ** 2)
            category, emoji, style = get_bmi_category(bmi)
            st.markdown(f'<div class="result-card bmi-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-card">👆 Enter your weight above to see conversions!</div>', unsafe_allow_html=True)

    # Footer
    st.markdown('<div class="info-card" style="text-align:center;">💪 Stay healthy and keep tracking! 💪<br><small>Made with ❤️ using Streamlit</small></div>', unsafe_allow_html=True)

# =================== CONTROLLER ===================
def main():
    if not st.session_state.logged_in:
        auth_gate()
    else:
        app_page()

if __name__ == "__main__":
    main()
