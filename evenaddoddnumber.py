import streamlit as st
import sqlite3
import base64
import mimetypes
import os, json, uuid
from datetime import datetime, timedelta
import bcrypt

# =========================
# App Config
# =========================
st.set_page_config(page_title="Health & Weight App", page_icon="⚖️", layout="centered")

DB_PATH = "users.db"
REMEMBER_FILE = "remember_me.json"

# =========================
# Database Setup
# =========================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT,
    plan TEXT,
    trial_end DATE,
    remember_token TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER UNIQUE,
    theme TEXT DEFAULT 'light',
    default_unit TEXT DEFAULT 'Kilograms (kg)',
    FOREIGN KEY(user_id) REFERENCES users(id)
)""")
conn.commit()

# =========================
# Helpers: Auth & Settings
# =========================
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_user(email: str, password: str):
    trial_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        c.execute("INSERT INTO users (email, password_hash, plan, trial_end) VALUES (?, ?, ?, ?)",
                  (email, hash_password(password), "Free Trial", trial_end))
        conn.commit()
        user = get_user_by_email(email)
        # default settings row
        c.execute("INSERT OR IGNORE INTO settings (user_id, theme, default_unit) VALUES (?, 'light', 'Kilograms (kg)')",
                  (user[0],))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "This email is already registered."

def get_user_by_email(email: str):
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    return c.fetchone()

def login(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if verify_password(password, user[2]):
        return user
    return None

def set_remember_me(user_id: int, enabled: bool):
    if enabled:
        token = str(uuid.uuid4())
        c.execute("UPDATE users SET remember_token=? WHERE id=?", (token, user_id))
        conn.commit()
        with open(REMEMBER_FILE, "w") as f:
            json.dump({"uid": user_id, "token": token}, f)
    else:
        c.execute("UPDATE users SET remember_token=NULL WHERE id=?", (user_id,))
        conn.commit()
        if os.path.exists(REMEMBER_FILE):
            os.remove(REMEMBER_FILE)

def try_auto_login():
    if not os.path.exists(REMEMBER_FILE):
        return None
    try:
        data = json.load(open(REMEMBER_FILE, "r"))
        uid, token = data.get("uid"), data.get("token")
        if not uid or not token:
            return None
        c.execute("SELECT * FROM users WHERE id=? AND remember_token=?", (uid, token))
        row = c.fetchone()
        return row
    except Exception:
        return None

def update_plan(user_id: int, new_plan: str):
    c.execute("UPDATE users SET plan=? WHERE id=?", (new_plan, user_id))
    conn.commit()

def get_settings(user_id: int):
    c.execute("SELECT theme, default_unit FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        return {"theme": row[0], "default_unit": row[1]}
    # ensure defaults
    c.execute("INSERT OR IGNORE INTO settings (user_id, theme, default_unit) VALUES (?, 'light', 'Kilograms (kg)')", (user_id,))
    conn.commit()
    return {"theme": "light", "default_unit": "Kilograms (kg)"}

def save_settings(user_id: int, theme: str, default_unit: str):
    c.execute("UPDATE settings SET theme=?, default_unit=? WHERE user_id=?", (theme, default_unit, user_id))
    conn.commit()

def plan_status(user) -> str:
    plan, trial_end = user[3], user[4]
    if plan == "Free Trial":
        try:
            if datetime.now() > datetime.strptime(trial_end, "%Y-%m-%d"):
                return "Expired"
        except Exception:
            return "Expired"
    return plan

# =========================
# UI: Themes & Styling
# =========================
def inject_css(theme: str):
    # Light / Dark palettes
    if theme == "dark":
        base_bg = "rgba(17,18,20,1)"
        card_bg = "rgba(32,35,39,0.9)"
        text = "#EAECEF"
        accent = "#7dd3fc"
        gradient1 = "#0ea5e9"
        gradient2 = "#6366f1"
    else:
        base_bg = "white"
        card_bg = "rgba(255,255,255,0.95)"
        text = "#111827"
        accent = "#2563eb"
        gradient1 = "#667eea"
        gradient2 = "#764ba2"

    st.markdown(f"""
    <style>
    .stApp {{
        color: {text};
        background: {base_bg};
    }}
    .title-header {{
        background: linear-gradient(90deg, {gradient1}, {gradient2});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 10px;
    }}
    .info-card {{
        background: {card_bg};
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        margin: 10px 0;
        border-left: 4px solid {accent};
    }}
    .metric-card {{
        background: linear-gradient(135deg, {gradient1} 0%, {gradient2} 100%);
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 8px 18px rgba(0,0,0,0.15);
        color: white;
        text-align: center;
        margin: 10px 0;
        border: 1px solid rgba(255,255,255,0.12);
    }}
    .result-card {{
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 14px;
        border-radius: 10px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.12);
        color: white;
        text-align: center;
        margin: 12px 0;
        font-weight: 600;
    }}
    .upload-section {{
        background: rgba(248,249,250,0.08);
        padding: 14px;
        border-radius: 10px;
        border: 2px dashed rgba(229,231,235,0.35);
        margin: 12px 0;
        text-align: center;
    }}
    @keyframes slideIn {{
        from {{ opacity: 0; transform: translateY(12px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .animated-result {{ animation: slideIn 0.45s ease-out; }}
    </style>
    """, unsafe_allow_html=True)

def apply_background(bg_file):
    if bg_file is not None:
        mime_type, _ = mimetypes.guess_type(bg_file.name)
        encoded = base64.b64encode(bg_file.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.25), rgba(0,0,0,0.25)),
                              url("data:{mime_type};base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """, unsafe_allow_html=True)

# =========================
# Conversions & BMI
# =========================
def kg_to_lbs(kg): return kg * 2.20462
def lbs_to_kg(lbs): return lbs * 0.45359237

def bmi_category(bmi: float):
    if bmi < 18.5: return "Underweight", "🔵"
    if bmi < 25:   return "Normal weight", "🟢"
    if bmi < 30:   return "Overweight", "🟡"
    return "Obese", "🔴"

# =========================
# Pages
# =========================
def page_home(user, settings):
    inject_css(settings["theme"])
    st.markdown('<h1 class="title-header">⚖️ Health & Weight Companion</h1>', unsafe_allow_html=True)

    st.sidebar.markdown("### Account")
    st.sidebar.write(f"Email: **{user[1]}**")
    st.sidebar.write(f"Plan: **{plan_status(user)}**")

    # Quick nav
    page = st.sidebar.radio("Navigate", ["Converter & BMI", "Subscription", "Settings", "Log out"])

    if page == "Converter & BMI":
        converter_bmi_page(user, settings)
    elif page == "Subscription":
        subscription_page(user)
    elif page == "Settings":
        settings_page(user, settings)
    else:
        # Log out
        set_remember_me(user[0], False)
        st.session_state.user = None
        st.rerun()

def converter_bmi_page(user, settings):
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.markdown("### 🖼️ Optional: Customize Background")
    bg = st.file_uploader("Upload background image (jpg/png)", type=["jpg", "jpeg", "png"])
    st.markdown('</div>', unsafe_allow_html=True)
    apply_background(bg)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.subheader("📏 Select Unit")
        unit = st.selectbox("", ["Kilograms (kg)", "Pounds (lbs)"], index=0 if settings["default_unit"].startswith("Kilograms") else 1, key="unit_sel")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.subheader("🔢 Enter Weight")
        weight = st.number_input("", min_value=0.1, max_value=999.9, step=0.1, format="%.1f", key="weight_in")
        st.markdown('</div>', unsafe_allow_html=True)

    if weight > 0:
        st.markdown('<div class="animated-result">', unsafe_allow_html=True)
        if "Kilograms" in unit:
            converted = kg_to_lbs(weight)
            stones = converted / 14
            ounces = converted * 16
            grams = weight * 1000

            st.markdown(f'<div class="result-card"><h3>🎯 {weight:.1f} kg = {converted:.1f} lbs</h3></div>', unsafe_allow_html=True)
            c3, c4, c5 = st.columns(3)
            with c3: st.markdown(f'<div class="metric-card"><h4>🪨 Stones</h4><h2>{stones:.1f}</h2></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><h4>⚖️ Ounces</h4><h2>{ounces:.0f}</h2></div>', unsafe_allow_html=True)
            with c5: st.markdown(f'<div class="metric-card"><h4>📊 Grams</h4><h2>{grams:.0f}</h2></div>', unsafe_allow_html=True)
        else:
            converted = lbs_to_kg(weight)
            stones = weight / 14
            ounces = weight * 16
            grams = converted * 1000

            st.markdown(f'<div class="result-card"><h3>🎯 {weight:.1f} lbs = {converted:.1f} kg</h3></div>', unsafe_allow_html=True)
            c3, c4, c5 = st.columns(3)
            with c3: st.markdown(f'<div class="metric-card"><h4>🪨 Stones</h4><h2>{stones:.1f}</h2></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="metric-card"><h4>⚖️ Ounces</h4><h2>{ounces:.0f}</h2></div>', unsafe_allow_html=True)
            with c5: st.markdown(f'<div class="metric-card"><h4>📊 Grams</h4><h2>{grams:.0f}</h2></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # BMI with height in feet + inches
        st.markdown("---")
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.subheader("🧮 BMI Calculator (Feet + Inches)")
        ch1, ch2 = st.columns(2)
        with ch1:
            feet = st.number_input("Height (feet)", 1, 8, value=5)
        with ch2:
            inches = st.number_input("Height (inches)", 0, 11, value=7)
        height_m = (feet * 12 + inches) * 0.0254
        if height_m > 0:
            weight_kg = weight if "Kilograms" in unit else lbs_to_kg(weight)
            bmi = weight_kg / (height_m ** 2)
            cat, emoji = bmi_category(bmi)
            st.markdown(f'<div class="result-card"><h3>{emoji} BMI: {bmi:.1f}</h3><p>Category: <strong>{cat}</strong></p></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Meal & Exercise (simple)
        st.markdown("---")
        st.subheader("🍽️ Sample Day Meal Plan (with times)")
        st.write("- Breakfast (08:00): Oatmeal + Banana")
        st.write("- Lunch (13:00): Grilled Chicken + Veggies")
        st.write("- Snack (16:00): Nuts")
        st.write("- Dinner (19:00): Salmon + Brown Rice")

        st.markdown("---")
        st.subheader("🏃 Sample Exercise (Beginner)")
        st.write("- 07:00 — 10 min walk")
        st.write("- 07:15 — 15 squats")
        st.write("- 07:20 — 10 push-ups")

def subscription_page(user):
    st.markdown('<h3 class="title-header">💳 Subscription</h3>', unsafe_allow_html=True)
    status = plan_status(user)
    st.info(f"Current plan: **{status}**")

    if status == "Expired":
        st.warning("Your free trial has ended. Choose a plan to continue.")
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Basic")
        st.write("₦2000 / month")
        if st.button("Pay Basic"):
            simulate_payment_and_activate(user[0], "Basic")
    with col2:
        st.subheader("Pro")
        st.write("₦4000 / month")
        if st.button("Pay Pro"):
            simulate_payment_and_activate(user[0], "Pro")
    with col3:
        st.subheader("Premium")
        st.write("₦6000 / month")
        if st.button("Pay Premium"):
            simulate_payment_and_activate(user[0], "Premium")
    st.markdown('</div>', unsafe_allow_html=True)

    st.caption("Demo payment: this simulates a successful payment and activates your plan immediately.")

def simulate_payment_and_activate(user_id: int, plan: str):
    # In real life, call Flutterwave/Paystack here and verify -> then:
    update_plan(user_id, plan)
    st.success(f"✅ Payment successful! Your plan is now **{plan}**.")
    st.rerun()

def settings_page(user, settings):
    st.markdown('<h3 class="title-header">⚙️ Settings</h3>', unsafe_allow_html=True)
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    theme = st.selectbox("Theme", ["light", "dark"], index=0 if settings["theme"] == "light" else 1)
    default_unit = st.selectbox("Default weight unit", ["Kilograms (kg)", "Pounds (lbs)"],
                                index=0 if settings["default_unit"].startswith("Kilograms") else 1)
    remember = st.checkbox("Remember me on this device", value=os.path.exists(REMEMBER_FILE))
    if st.button("Save Settings"):
        save_settings(user[0], theme, default_unit)
        set_remember_me(user[0], remember)
        st.success("✅ Settings saved.")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Auth Screen
# =========================
def auth_screen():
    # Try auto-login
    if "user" not in st.session_state or st.session_state.user is None:
        auto = try_auto_login()
        if auto:
            st.session_state.user = auto

    if st.session_state.get("user"):
        user = st.session_state.user
        settings = get_settings(user[0])
        page_home(user, settings)
        return

    st.markdown('<h1 class="title-header">Welcome — Sign in or Create an Account</h1>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        email = st.text_input("Email", key="login_email")
        pw = st.text_input("Password", type="password", key="login_pw")
        remember = st.checkbox("Remember me")
        if st.button("Login"):
            user = login(email, pw)
            if user:
                st.session_state.user = user
                set_remember_me(user[0], remember)
                st.success("✅ Logged in!")
                st.rerun()
            else:
                st.error("❌ Invalid email or password")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        email = st.text_input("Email", key="signup_email")
        pw = st.text_input("Create password", type="password", key="signup_pw")
        if st.button("Sign Up"):
            ok, err = create_user(email, pw)
            if ok:
                user = login(email, pw)  # auto-login
                st.session_state.user = user
                set_remember_me(user[0], True)  # default remember new users
                st.success("🎉 Account created! You’re logged in with a 7-day free trial.")
                st.rerun()
            else:
                st.error(f"❌ {err}")
        st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Entry
# =========================
def main():
    # Use user theme even on auth screen (light by default)
    user = st.session_state.get("user")
    theme = "light"
    if user:
        theme = get_settings(user[0])["theme"]
    inject_css(theme)
    auth_screen()

if __name__ == "__main__":
    main()
