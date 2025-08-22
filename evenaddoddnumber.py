import streamlit as st
import base64
import mimetypes
import sqlite3



# =================== CONFIG ===================
st.set_page_config(
    page_title="Weight Converter",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

DB_FILE = "users.db"

# =================== DATABASE SETUP ===================
def init_db():
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
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
    conn.commit()
    conn.close()

def get_user(username: str):
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

# =================== DIET PLANS ===================
def get_diet_plan(bmi_category):
    plans = {
        "Underweight": """🍽️ **Diet Plan for Underweight**
- Eat **high-calorie nutritious foods** (nuts, avocados, dairy, whole grains).
- Include **protein shakes & smoothies**.
- Eat **5–6 small meals daily**.
- Strength training helps build muscle mass.""",

        "Normal weight": """🥗 **Diet Plan for Normal Weight**
- Maintain a **balanced diet** (fruits, veggies, lean protein, whole grains).
- Keep **portion control** in mind.
- Stay hydrated 💧.
- Regular exercise to maintain your weight.""",

        "Overweight": """🥦 **Diet Plan for Overweight**
- Choose **low-calorie, high-fiber foods** (vegetables, fruits, beans).
- Cut down on **sugar & refined carbs**.
- Use smaller plates to control portions.
- Aim for **150 mins of moderate activity per week**.""",

        "Obese": """🥬 **Diet Plan for Obesity**
- Focus on **vegetables, lean protein, and whole grains**.
- Avoid **junk food, fried foods, and sugary drinks**.
- Try **meal prepping** to avoid overeating.
- Consult a **nutritionist/doctor** for a personalized plan.
- Add **daily walks/exercise** gradually."""
    }
    return plans.get(bmi_category, "⚠️ No plan available.")

# =================== AUTH ===================
def login_view():
    st.markdown('<div class="title-header">🔑 Login</div>', unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        login_btn = st.form_submit_button("Login")

    if login_btn:
        user = get_user(username.strip())
        if user and bcrypt.checkpw(password.encode(), user[1].encode()):
            st.session_state.logged_in = True
            st.session_state.username = user[0]
            st.toast(f"Welcome back, {user[0]}!", icon="✅")
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
            st.warning("⚠️ Password must be at least 4 characters.")
            return
        if pw1 != pw2:
            st.error("❌ Passwords do not match.")
            return
        if get_user(u):
            st.error("❌ Username already exists.")
            return

        add_user(u, pw1)
        st.session_state.logged_in = True
        st.session_state.username = u
        st.toast("✅ Account created. You are now logged in.", icon="🎉")
        st.rerun()

def auth_gate():
    inject_custom_css()
    tab = st.segmented_button("Authentication", options=["Login", "Sign Up"], default=st.session_state.auth_tab)
    st.session_state.auth_tab = tab
    if tab == "Login":
        login_view()
    else:
        signup_view()

# =================== APP PAGE ===================
def app_page():
    inject_custom_css()
    st.markdown(f'<div class="title-header">⚖️ Welcome {st.session_state["username"]}! ⚖️</div>', unsafe_allow_html=True)

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.toast("Logged out.", icon="👋")
        st.rerun()

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

            st.markdown(
                f'<div class="result-card bmi-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>',
                unsafe_allow_html=True
            )

            # 🎯 Show dietary plan
            diet_plan = get_diet_plan(category)
            st.markdown(f'<div class="info-card">{diet_plan}</div>', unsafe_allow_html=True)

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

