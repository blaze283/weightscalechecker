import streamlit as st
import base64

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="BMI & Fitness App", page_icon="💪", layout="centered")

# ---------------- USER DATA (simple in-memory store) ----------------
users = {"admin": "1234"}  # default user

# ---------------- BACKGROUND ----------------
def set_background(color=None, image=None):
    if image is not None:
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:image/png;base64,{image}") no-repeat center center fixed;
                background-size: cover;
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
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        # default background
        st.markdown(
            """
            <style>
            .stApp { background-color: #f0f2f6; }
            </style>
            """,
            unsafe_allow_html=True
        )

# ---------------- CUSTOM STYLES ----------------
st.markdown("""
<style>
.info-card {
    background-color: #ffffffaa;
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    box-shadow: 1px 1px 5px rgba(0,0,0,0.1);
    text-align: center;
    font-size: 18px;
}
.result-card {
    padding: 15px;
    border-radius: 12px;
    margin: 10px 0;
    font-size: 20px;
    font-weight: bold;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ---------------- BACKGROUND CUSTOMIZATION ----------------
st.sidebar.title("🎨 Customize Background")
bg_choice = st.sidebar.radio("Choose Background Type:", ["Default", "Color", "Image"])

if bg_choice == "Color":
    picked_color = st.sidebar.color_picker("Pick a background color", "#f0f2f6")
    set_background(color=picked_color)

elif bg_choice == "Image":
    uploaded_img = st.sidebar.file_uploader("Upload an image", type=["png","jpg","jpeg"])
    if uploaded_img:
        img_data = base64.b64encode(uploaded_img.read()).decode()
        set_background(image=img_data)
    else:
        set_background()

else:
    set_background()

# ---------------- BMI CATEGORIES ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return (
            "Underweight",
            "🟦",
            "background-color:#d0e7ff;",
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
            "Normal weight",
            "🟩",
            "background-color:#d6f5d6;",
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
            "Overweight",
            "🟨",
            "background-color:#fff5cc;",
            """🥦 Eat more veggies & fiber-rich foods.
🍵 Replace soda with water or g
