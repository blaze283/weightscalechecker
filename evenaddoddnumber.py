import streamlit as st
import base64

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="BMI Calculator", page_icon="⚖️", layout="centered")

# ---------------- USER DATABASE (in-memory demo) ----------------
if "users" not in st.session_state:
    st.session_state.users = {"admin": "1234"}  # default user

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# ---------------- BMI CATEGORIES ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return (
            "Underweight", "🟦", "background-color:#d0e7ff; color:#000;",
            """🍽️ Eat high-calorie nutritious foods.
🥛 Drink milk or protein shakes between meals.
🍗 Add lean meats, fish, and eggs.
🥑 Include healthy fats (avocados, nuts, olive oil).
🛏️ Get enough rest to support weight gain.""",
            """🏋️ Focus on strength training (push-ups, squats, lifting).
🚶 Light jogging or cycling for stamina.
🧘 Yoga to improve flexibility.
📅 Train 3–4 days a week.
🥤 Don’t skip post-workout meals."""
        )
    elif bmi < 25:
        return (
            "Normal weight", "🟩", "background-color:#d6f5d6; color:#000;",
            """🥗 Maintain a balanced diet with fruits & vegetables.
🍗 Keep protein intake steady (chicken, fish, beans).
💧 Stay hydrated (2–3 liters water daily).
🏃 Exercise 30 min a day.
😴 Sleep 7–8 hours for recovery.""",
            """🏃 Mix cardio & strength training.
⚽ Play sports for fun activity.
🧘 Try yoga or stretching weekly.
📅 Train 4–5 days a week.
🚶 Stay active daily (walks, stairs)."""
        )
    elif bmi < 30:
        return (
            "Overweight", "🟨", "background-color:#fff5cc; color:#000;",
            """🥦 Eat more veggies & fiber-rich foods.
🍵 Replace soda with water or green tea.
🍞 Choose whole grains over white bread/rice.
🚶 Walk 8,000–10,000 steps daily.
⚖️ Track calories & portion sizes.""",
            """🚴 Do cardio (cycling, running, swimming).
🏋️ Add light strength training (bodyweight).
📅 Train at least 5 days a week.
🧘 Try Pilates/yoga for flexibility.
🎯 Focus on gradual progress."""
        )
    else:
        return (
            "Obese", "🟥", "background-color:#ffd6cc; color:#000;",
            """🥬 Eat veggies, lean protein & whole grains.
🍭 Avoid sugar drinks & junk food.
🚴 Exercise at least 30 min most days.
📉 Aim for slow, steady weight loss.
👨‍⚕️ Consult a doctor/nutritionist.""",
            """🚶 Start with low-impact cardio (walking, swimming).
🏋️ Gradually add resistance training.
🧘 Yoga/stretching for mobility.
📅 Exercise 5–6 days weekly.
🎯 Focus on consistency, not speed."""
        )

# ---------------- THEME SYSTEM ----------------
def set_theme(mode="Light", color=None, image=None):
    if image:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:image/png;base64,{image}") no-repeat center center fixed;
                background-size: cover;
                color: {"white" if mode=="Dark" else "black"};
            }}
            input, .stButton>button {{
                background-color: {"white" if mode=="Dark" else "#f0f2f6"} !important;
                color: {"black" if mode=="Dark" else "black"} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    elif color:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-color: {color};
                color: {"white" if mode=="Dark" else "black"};
            }}
            input, .stButton>button {{
                background-color: {"white" if mode=="Dark" else "#f0f2f6"} !important;
                color: {"black" if mode=="Dark" else "black"} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        default_bg = "#0e1117" if mode == "Dark" else "#f0f2f6"
        text_color = "white" if mode == "Dark" else "black"
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-color: {default_bg};
                color: {text_color};
            }}
            input, .stButton>button {{
                background-color: {"white" if mode=="Dark" else "#f0f2f6"} !important;
                color: {"black" if mode=="Dark" else "black"} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# ---------------- BACKGROUND CUSTOMIZATION ----------------
st.sidebar.title("🎨 Customize Theme")
theme_mode = st.sidebar.radio("Choose Theme:", ["Light", "Dark"])
bg_choice = st.sidebar.radio("Background Type:", ["Default", "Color", "Image"])

if bg_choice == "Color":
    picked_color = st.sidebar.color_picker("Pick a background color", "#f0f2f6")
    set_theme(theme_mode, color=picked_color)
elif bg_choice == "Image":
    uploaded_img = st.sidebar.file_uploader("Upload an image", type=["png","jpg","jpeg"])
    if uploaded_img:
        img_data = base64.b64encode(uploaded_img.read()).decode()
        set_theme(theme_mode, image=img_data)
    else:
        set_theme(theme_mode)
else:
    set_theme(theme_mode)

# ---------------- LOGIN / SIGNUP ----------------
users = st.session_state.users

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Sign Up"])

    with tab1:
        st.subheader("Login to Continue")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.experimental_rerun()
            else:
                st.error("Invalid username or password ❌")

    with tab2:
        st.subheader("Create a New Account")
        new_user = st.text_input("Choose a Username", key="signup_user")
        new_pass = st.text_input("Choose a Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            if new_user in users:
                st.error("Username already exists ❌")
            else:
                users[new_user] = new_pass
                st.success("Account created! ✅ Redirecting...")
                st.session_state.logged_in = True
                st.session_state.username = new_user
                st.experimental_rerun()

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:
    st.title("⚖️ BMI Calculator")
    st.markdown(f"👋 Welcome **{st.session_state.username}**!")

    st.markdown("📏 Enter Your Height")
    col1, col2 = st.columns(2)
    with col1:
        feet = st.number_input("Feet", min_value=1, max_value=8, step=1, value=5)
    with col2:
        inches = st.number_input("Inches", min_value=0, max_value=11, step=1, value=7)
    height_m = (feet * 12 + inches) * 0.0254

    unit = st.selectbox("Weight Unit", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter Your Weight in {unit}", step=0.1)

    if height_m > 0 and weight > 0:
        weight_kg = weight if unit == "Kilograms" else weight * 0.453592
        bmi = weight_kg / (height_m ** 2)
        category, emoji, style, diet_tips, workout_tips = get_bmi_category(bmi)

        st.markdown(
            f"""
            <div style="{style} padding:15px; border-radius:10px; margin-top:20px;">
                <h3>Your BMI: {bmi:.2f} {emoji}</h3>
                <b>Category:</b> {category}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### 🥗 Diet Tips")
        st.info(diet_tips)

        st.markdown("### 🏋️ Workout Tips")
        st.success(workout_tips)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.experimental_rerun()
