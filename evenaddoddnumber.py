import streamlit as st
import base64

# ---------------- SESSION STATE ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "users" not in st.session_state:
    st.session_state.users = {"test": "1234"}  # demo user

# ---------------- THEMES ----------------
def apply_theme(mode="light", bg_color=None, bg_image=None):
    if mode == "dark":
        text_color = "#FFFFFF"
        input_bg = "#333333"
        input_text = "#FFFFFF"
        button_bg = "#555555"
        button_text = "#FFFFFF"
        default_bg = "#121212"
    else:
        text_color = "#000000"
        input_bg = "#FFFFFF"
        input_text = "#000000"
        button_bg = "#e0e0e0"
        button_text = "#000000"
        default_bg = "#f0f2f6"

    if bg_image:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:image/png;base64,{bg_image}") no-repeat center center fixed;
                background-size: cover;
                color: {text_color};
            }}
            input, textarea {{
                background-color: {input_bg} !important;
                color: {input_text} !important;
            }}
            .stButton>button {{
                background-color: {button_bg};
                color: {button_text};
                border-radius: 8px;
                padding: 0.4em 1em;
            }}
            </style>
            """, unsafe_allow_html=True
        )
    else:
        bg_color = bg_color or default_bg
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-color: {bg_color};
                color: {text_color};
            }}
            input, textarea {{
                background-color: {input_bg} !important;
                color: {input_text} !important;
            }}
            .stButton>button {{
                background-color: {button_bg};
                color: {button_text};
                border-radius: 8px;
                padding: 0.4em 1em;
            }}
            </style>
            """, unsafe_allow_html=True
        )

# ---------------- BMI CATEGORY ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return ("Underweight", "⚠️", "background-color:#FFDDC1; color:#000;",
                "🍠 Eat more carbs, proteins, healthy fats.\n🥛 Drink milkshakes & smoothies.\n🥩 Try peanut butter, avocados, fish.",
                "🏋️ Strength training\n🚶 Brisk walks\n🧘 Light yoga")
    elif 18.5 <= bmi < 24.9:
        return ("Normal", "✅", "background-color:#C1FFD7; color:#000;",
                "🥗 Balanced meals with veggies, proteins, carbs.\n💧 Stay hydrated.\n🍊 Snack on fruits & nuts.",
                "🏃 Jogging / Running\n🏋️ Mix strength + cardio\n🚴 Cycling")
    elif 25 <= bmi < 29.9:
        return ("Overweight", "⚠️", "background-color:#FFFAC1; color:#000;",
                "🥦 Eat fiber-rich foods.\n🥩 Cut fried foods & sugary drinks.\n🥗 Focus on portion control.",
                "🏋️ HIIT workouts\n🏊 Swimming\n🚶 Daily walks")
    else:
        return ("Obese", "❌", "background-color:#FFBDBD; color:#000;",
                "🥗 Adopt a calorie-deficit diet.\n🥩 Choose lean proteins.\n🥦 Eat veggies & whole grains.\n🚫 Avoid processed foods.",
                "🚶 Start with walking\n🏋️ Gradually add strength training\n🧘 Yoga & stretching")

# ---------------- BACKGROUND CUSTOMIZATION ----------------
st.sidebar.title("🎨 Customize Background")
theme_mode = st.sidebar.radio("Theme Mode:", ["Light", "Dark"])
bg_choice = st.sidebar.radio("Choose Background Type:", ["Default", "Color", "Image"])

picked_color, img_data = None, None
if bg_choice == "Color":
    picked_color = st.sidebar.color_picker("Pick a background color", "#f0f2f6")
elif bg_choice == "Image":
    uploaded_img = st.sidebar.file_uploader("Upload an image", type=["png","jpg","jpeg"])
    if uploaded_img:
        img_data = base64.b64encode(uploaded_img.read()).decode()

apply_theme(theme_mode.lower(), bg_color=picked_color, bg_image=img_data)

# ---------------- AUTH SYSTEM ----------------
if not st.session_state.logged_in:
    st.title("🔐 Login / Sign Up")

    choice = st.radio("Choose an option:", ["Login", "Sign Up"])

    if choice == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in st.session_state.users and st.session_state.users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful ✅")
                st.experimental_rerun()
            else:
                st.error("Invalid username or password ❌")

    else:  # Sign Up
        new_user = st.text_input("Choose a Username")
        new_pass = st.text_input("Choose a Password", type="password")
        if st.button("Sign Up"):
            if new_user in st.session_state.users:
                st.error("Username already exists ❌")
            else:
                st.session_state.users[new_user] = new_pass
                st.success("Account created! ✅ Redirecting...")
                st.session_state.logged_in = True
                st.session_state.username = new_user
                st.experimental_rerun()

# ---------------- MAIN APP ----------------
if st.session_state.logged_in:
    st.title(f"Welcome, {st.session_state.username}! 🎉")

    # Weight input
    unit = st.selectbox("Select Your Weight Unit:", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter Your Weight in {unit}", step=0.1, min_value=0.0)

    # Height input
    st.markdown('<div class="info-card">📏 Enter Your Height</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        feet = st.number_input("Feet", min_value=1, max_value=8, step=1, value=5)
    with col2:
        inches = st.number_input("Inches", min_value=0, max_value=11, step=1, value=7)

    height_m = (feet * 12 + inches) * 0.0254

    if height_m > 0 and weight > 0:
        weight_kg = weight if unit == "Kilograms" else weight * 0.453592
        bmi = weight_kg / (height_m ** 2)
        category, emoji, style, diet_tips, workout_tips = get_bmi_category(bmi)

        st.markdown(f'<div class="result-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>', unsafe_allow_html=True)

        # Diet Tips
        st.markdown(f"""
        <div class="info-card" style="text-align:left;">
        🍽️ <b>Suggested Diet Plan:</b><br>
        <pre style="white-space: pre-wrap; font-size:16px;">{diet_tips}</pre>
        </div>
        """, unsafe_allow_html=True)

        # Workout Tips
        st.markdown(f"""
        <div class="info-card" style="text-align:left;">
        🏋️ <b>Workout Tips:</b><br>
        <pre style="white-space: pre-wrap; font-size:16px;">{workout_tips}</pre>
        </div>
        """, unsafe_allow_html=True)

    # Logout
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.experimental_rerun()
