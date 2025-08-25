import streamlit as st
import base64

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="BMI & Fitness App", page_icon="💪", layout="centered")

# ---------------- USER DATA (simple in-memory store) ----------------
users = {"admin": "1234"}  # default user

# ---------------- BACKGROUND ----------------
def set_background(color=None, image=None, dark_mode=False):
    if image is not None:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:image/png;base64,{image}") no-repeat center center fixed;
                background-size: cover;
                color: {"white" if dark_mode else "black"};
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
                color: {"white" if dark_mode else "black"};
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        bg_color = "#111111" if dark_mode else "#f0f2f6"
        text_color = "white" if dark_mode else "black"
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-color: {bg_color};
                color: {text_color};
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

# ---------------- BMI CATEGORIES ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return (
            "Underweight", "🟦", "background-color:#d0e7ff;",
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
            "Normal weight", "🟩", "background-color:#d6f5d6;",
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
            "Overweight", "🟨", "background-color:#fff5cc;",
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
            "Obese", "🟥", "background-color:#ffd6cc;",
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

# ---------------- LOGIN SYSTEM ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- SIDEBAR SETTINGS ----------------
st.sidebar.title("⚙️ Settings")

# Dark/Light mode
dark_mode = st.sidebar.radio("Theme", ["Light", "Dark"]) == "Dark"

# Background customization
bg_choice = st.sidebar.radio("Background Type", ["Default", "Color", "Image"])

if bg_choice == "Color":
    picked_color = st.sidebar.color_picker("Pick a background color", "#f0f2f6" if not dark_mode else "#111111")
    set_background(color=picked_color, dark_mode=dark_mode)

elif bg_choice == "Image":
    uploaded_img = st.sidebar.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        img_data = base64.b64encode(uploaded_img.read()).decode()
        set_background(image=img_data, dark_mode=dark_mode)
    else:
        set_background(dark_mode=dark_mode)

else:
    set_background(dark_mode=dark_mode)

# ---------------- STYLES ----------------
card_bg = "#222222aa" if dark_mode else "#ffffffaa"
text_color = "white" if dark_mode else "black"

st.markdown(f"""
<style>
.info-card {{
    background-color: {card_bg};
    color: {text_color};
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    box-shadow: 1px 1px 5px rgba(0,0,0,0.3);
    text-align: center;
    font-size: 18px;
}}
.result-card {{
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    font-size: 20px;
    font-weight: bold;
    text-align: center;
}}
</style>
""", unsafe_allow_html=True)

# ---------------- APP LOGIC ----------------
if not st.session_state.logged_in:
    choice = st.sidebar.radio("Account", ["Login", "Sign Up"])

    if choice == "Login":
        st.markdown('<div class="info-card">🔑 Login</div>', unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.success("Login successful ✅")
            else:
                st.error("Invalid username or password ❌")

    else:
        st.markdown('<div class="info-card">🆕 Sign Up</div>', unsafe_allow_html=True)
        new_user = st.text_input("Choose a Username")
        new_pass = st.text_input("Choose a Password", type="password")
        if st.button("Sign Up"):
            if new_user in users:
                st.error("Username already exists ❌")
            else:
                users[new_user] = new_pass
                st.success("Account created! Please login ✅")

else:
    # ---------------- MAIN APP ----------------
    st.markdown('<div class="info-card">💪 Welcome to the BMI & Fitness App</div>', unsafe_allow_html=True)

    # Weight input
    unit = st.radio("Select Your Weight Unit:", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter Your Weight in {unit}:", min_value=1.0, step=0.5)

    # Height input
    st.markdown('<div class="info-card">📏 Enter Your Height</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        feet = st.number_input("Feet", min_value=1, max_value=8, step=1, value=5)
    with col2:
        inches = st.number_input("Inches", min_value=0, max_value=11, step=1, value=7)

    # BMI calculation
    height_m = (feet * 12 + inches) * 0.0254
    if height_m > 0 and weight > 0:
        weight_kg = weight if unit == "Kilograms" else weight * 0.453592
        bmi = weight_kg / (height_m ** 2)
        category, emoji, style, diet_tips, workout_tips = get_bmi_category(bmi)

        st.markdown(f'<div class="result-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="info-card"><b>🍽️ Diet Tips:</b><br>{diet_tips.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="info-card"><b>🏋️ Workout Tips:</b><br>{workout_tips.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.experimental_rerun()
