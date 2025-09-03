import streamlit as st
import sqlite3
import base64
import mimetypes
from datetime import datetime, timedelta

# ------------------- DATABASE -------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                password TEXT,
                plan TEXT,
                trial_end DATE
            )""")
conn.commit()

# ------------------- UTILS / CONVERSIONS -------------------
def kg_to_lbs(kg):
    return kg * 2.20462

def lbs_to_kg(lbs):
    return lbs * 0.45359237

def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight", "🔵"
    elif 18.5 <= bmi < 25:
        return "Normal weight", "🟢"
    elif 25 <= bmi < 30:
        return "Overweight", "🟡"
    else:
        return "Obese", "🔴"

# ------------------- MEAL & EXERCISE PLANS -------------------
meal_plan = {
    "Monday": {"Breakfast": "Oatmeal + Banana (08:00)", "Lunch": "Grilled chicken + Veggies (13:00)", "Dinner": "Salmon + Brown rice (19:00)", "Snack": "Nuts (16:00)"},
    "Tuesday": {"Breakfast": "Scrambled eggs + Toast (08:00)", "Lunch": "Beef stir fry (13:00)", "Dinner": "Tuna salad (19:00)", "Snack": "Yogurt (16:00)"},
    "Wednesday": {"Breakfast": "Smoothie + Protein (08:00)", "Lunch": "Chicken wrap (13:00)", "Dinner": "Grilled fish (19:00)", "Snack": "Apple (16:00)"},
    "Thursday": {"Breakfast": "Pancakes + Berries (08:00)", "Lunch": "Rice + Beans (13:00)", "Dinner": "Steak + Vegetables (19:00)", "Snack": "Carrots (16:00)"},
    "Friday": {"Breakfast": "Boiled eggs + Avocado (08:00)", "Lunch": "Turkey sandwich (13:00)", "Dinner": "Pasta + Chicken (19:00)", "Snack": "Granola (16:00)"},
    "Saturday": {"Breakfast": "French toast + Orange (09:00)", "Lunch": "Vegetable soup (13:00)", "Dinner": "Grilled prawns (19:00)", "Snack": "Popcorn (16:00)"},
    "Sunday": {"Breakfast": "Smoothie bowl (09:00)", "Lunch": "Chicken salad (13:00)", "Dinner": "Beef stew (19:00)", "Snack": "Dark chocolate (16:00)"}
}

exercise_plan = {
    "Beginner": [
        {"time": "07:00", "activity": "10 min walk"},
        {"time": "07:15", "activity": "15 squats"},
        {"time": "07:20", "activity": "10 push-ups"}
    ],
    "Intermediate": [
        {"time": "06:30", "activity": "30 min jog"},
        {"time": "07:10", "activity": "20 squats"},
        {"time": "07:20", "activity": "15 push-ups"},
        {"time": "07:30", "activity": "Plank 1 min"}
    ],
    "Advanced": [
        {"time": "06:00", "activity": "45 min run"},
        {"time": "07:00", "activity": "30 squats"},
        {"time": "07:15", "activity": "20 push-ups"},
        {"time": "07:30", "activity": "HIIT 20 mins"}
    ]
}

# ------------------- AUTH FUNCTIONS -------------------
def signup(email, password):
    trial_end = datetime.now() + timedelta(days=7)  # free 7-day trial
    try:
        c.execute("INSERT INTO users (email, password, plan, trial_end) VALUES (?, ?, ?, ?)",
                  (email, password, "Free Trial", trial_end.strftime("%Y-%m-%d")))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, "This email is already registered."

def login(email, password):
    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    return c.fetchone()

def get_user_by_email(email):
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    return c.fetchone()

def update_plan(user_id, new_plan):
    c.execute("UPDATE users SET plan=? WHERE id=?", (new_plan, user_id))
    conn.commit()

def check_plan(user):
    plan, trial_end = user[3], user[4]
    if plan == "Free Trial":
        try:
            if datetime.now() > datetime.strptime(trial_end, "%Y-%m-%d"):
                return "Expired"
        except Exception:
            return "Expired"
    return plan

# ------------------- STYLES & BACKGROUND -------------------
def inject_custom_css():
    st.markdown("""
    <style>
    .main-container {
        max-width: 1000px;
        margin: 0 auto;
        padding: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 8px 18px rgba(0,0,0,0.12);
        color: white;
        text-align: center;
        margin: 10px 0;
        border: 1px solid rgba(255,255,255,0.15);
    }
    .result-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 14px;
        border-radius: 10px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        color: white;
        text-align: center;
        margin: 10px 0;
        font-weight: 600;
    }
    .info-card {
        background: rgba(255,255,255,0.95);
        padding: 12px;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin: 10px 0;
        border-left: 4px solid #667eea;
    }
    .title-header {
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4, #45b7d1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 18px;
    }
    .upload-section {
        background: rgba(248,249,250,0.9);
        padding: 14px;
        border-radius: 10px;
        border: 2px dashed #e9ecef;
        margin: 12px 0;
        text-align: center;
    }
    .stSelectbox > div > div {
        background: white;
        border-radius: 8px;
        border: 2px solid #e9ecef;
        font-size: 16px !important;
    }
    .stNumberInput > div > div > input {
        background: white;
        border-radius: 8px;
        border: 2px solid #e9ecef;
        font-size: 16px !important;
        text-align: center;
    }
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animated-result {
        animation: slideIn 0.45s ease-out;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_background(bg_image):
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded_image = base64.b64encode(bg_image.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.35), rgba(0,0,0,0.35)), 
                             url("data:{mime_type};base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .info-card, .upload-section {{
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(6px);
        }}
        </style>
        """, unsafe_allow_html=True)

# ------------------- STREAMLIT APP -------------------
st.set_page_config(page_title="Health & Weight App", page_icon="⚖️", layout="centered")
inject_custom_css()

if "user" not in st.session_state:
    st.session_state.user = None

st.markdown('<h1 class="title-header">⚖️ Health & Weight Companion ⚖️</h1>', unsafe_allow_html=True)

# Authentication UI
if not st.session_state.user:
    auth_tab1, auth_tab2 = st.tabs(["Login", "Sign Up"])
    with auth_tab1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.subheader("Login")
        login_email = st.text_input("Email", key="login_email")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            user = login(login_email, login_pass)
            if user:
                st.session_state.user = user
                st.success("✅ Logged in successfully")
                st.experimental_rerun()
            else:
                st.error("❌ Invalid email or password")
        st.markdown('</div>', unsafe_allow_html=True)

    with auth_tab2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.subheader("Sign Up (7-day free trial)")
        signup_email = st.text_input("Email", key="signup_email")
        signup_pass = st.text_input("Create Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            ok, err = signup(signup_email, signup_pass)
            if ok:
                st.session_state.user = login(signup_email, signup_pass)
                st.success("🎉 Account created — you are now logged in and have a 7-day free trial!")
                st.experimental_rerun()
            else:
                st.error(f"❌ {err}")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    user = st.session_state.user
    st.sidebar.success(f"👋 Hello, {user[1]}")
    st.sidebar.markdown("### Account")
    st.sidebar.write(f"- Email: **{user[1]}**")
    plan_status = check_plan(user)
    st.sidebar.write(f"- Plan: **{plan_status}**")
    if st.sidebar.button("Log out"):
        st.session_state.user = None
        st.experimental_rerun()

    # If trial expired -> show plan options
    if plan_status == "Expired":
        st.error("⚠️ Your free trial has expired. Choose a plan to continue accessing premium content.")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Basic (₦2000/mo)"):
                update_plan(user[0], "Basic")
                st.success("✅ Subscribed to Basic")
                st.experimental_rerun()
        with c2:
            if st.button("Pro (₦4000/mo)"):
                update_plan(user[0], "Pro")
                st.success("✅ Subscribed to Pro")
                st.experimental_rerun()
        with c3:
            if st.button("Premium (₦6000/mo)"):
                update_plan(user[0], "Premium")
                st.success("✅ Subscribed to Premium")
                st.experimental_rerun()
    else:
        st.info(f"📌 Current Plan: **{plan_status}**")

        # Background upload & converter section
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.markdown("### 🖼️ Customize Background (optional)")
        bg_image = st.file_uploader("Upload background image (jpg, png)", type=["jpg", "jpeg", "png"])
        st.markdown('</div>', unsafe_allow_html=True)
        apply_background(bg_image)

        # Converter & Metrics
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.subheader("📏 Weight Converter & Units")
            unit = st.selectbox("Select unit", ["Kilograms (kg)", "Pounds (lbs)"], key="unit_main")
            weight = st.number_input("Enter weight", min_value=0.1, max_value=999.9, step=0.1, format="%.1f", key="weight_main")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.subheader("Quick Tools")
            # quick conversion buttons for sample weights
            if st.button("Convert 70 kg ↔ lbs"):
                if "Kilograms" in unit:
                    st.session_state.weight_main = 70.0
                else:
                    st.session_state.weight_main = 154.3
            st.markdown("</div>", unsafe_allow_html=True)

        # Show conversion results only if weight > 0
        if weight > 0:
            st.markdown('<div class="animated-result">', unsafe_allow_html=True)
            if "Kilograms" in unit:
                converted = kg_to_lbs(weight)
                stones = converted / 14
                ounces = converted * 16
                grams = weight * 1000
                st.markdown(f'''
                    <div class="result-card">
                        <h3>🎯 {weight:.1f} kg = {converted:.1f} lbs</h3>
                    </div>
                ''', unsafe_allow_html=True)

                c3, c4, c5 = st.columns(3)
                with c3:
                    st.markdown(f'<div class="metric-card"><h4>🪨 Stones</h4><h2>{stones:.1f}</h2></div>', unsafe_allow_html=True)
                with c4:
                    st.markdown(f'<div class="metric-card"><h4>⚖️ Ounces</h4><h2>{ounces:.0f}</h2></div>', unsafe_allow_html=True)
                with c5:
                    st.markdown(f'<div class="metric-card"><h4>📊 Grams</h4><h2>{grams:.0f}</h2></div>', unsafe_allow_html=True)

            else:
                converted = lbs_to_kg(weight)
                stones = weight / 14
                ounces = weight * 16
                grams = converted * 1000
                st.markdown(f'''
                    <div class="result-card">
                        <h3>🎯 {weight:.1f} lbs = {converted:.1f} kg</h3>
                    </div>
                ''', unsafe_allow_html=True)

                c3, c4, c5 = st.columns(3)
                with c3:
                    st.markdown(f'<div class="metric-card"><h4>🪨 Stones</h4><h2>{stones:.1f}</h2></div>', unsafe_allow_html=True)
                with c4:
                    st.markdown(f'<div class="metric-card"><h4>⚖️ Ounces</h4><h2>{ounces:.0f}</h2></div>', unsafe_allow_html=True)
                with c5:
                    st.markdown(f'<div class="metric-card"><h4>📊 Grams</h4><h2>{grams:.0f}</h2></div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

            # BMI calculator (height in meters)
            st.markdown("---")
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.subheader("🧮 BMI Calculator")
            height_m = st.number_input("Enter your height in meters (e.g., 1.70)", min_value=0.5, max_value=3.0, step=0.01, value=1.70, format="%.2f", key="height_m")
            if height_m > 0:
                weight_kg = weight if "Kilograms" in unit else lbs_to_kg(weight)
                bmi = weight_kg / (height_m ** 2)
                cat, emoji = get_bmi_category(bmi)
                st.markdown(f'''
                    <div class="result-card">
                        <h3>{emoji} BMI: {bmi:.1f}</h3>
                        <p>Category: <strong>{cat}</strong></p>
                    </div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown("👆 Enter your weight to see conversions, BMI, and other metrics.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Meal plan
        st.markdown("---")
        st.header("🍽️ Weekly Meal Plan (with times)")
        for day, meals in meal_plan.items():
            with st.expander(day):
                for meal, food in meals.items():
                    st.write(f"- **{meal}**: {food}")

        # Exercise plan
        st.markdown("---")
        st.header("🏃 Exercise Plan")
        level = st.selectbox("Choose your fitness level:", ["Beginner", "Intermediate", "Advanced"], key="exercise_level")
        st.write(f"**{level} Routine (times suggested):**")
        for ex in exercise_plan[level]:
            st.write(f"- {ex['time']} — {ex['activity']}")

        # Footer
        st.markdown("---")
        st.markdown('<div style="text-align:center;color:#666;margin-top:12px"><small>Made with ❤️ using Streamlit — your health companion.</small></div>', unsafe_allow_html=True)
