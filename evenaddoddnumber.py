import streamlit as st

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Fitness & BMI App",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------------- CUSTOM CSS ----------------
def inject_custom_css():
    st.markdown("""
    <style>
    * { font-family: 'Segoe UI', sans-serif; }
    .main { max-width: 800px; margin: auto; }
    .info-card {
        background-color: #f9f9f9;
        border-radius: 12px;
        padding: 12px 16px;
        margin: 10px 0;
        font-size: 18px;
        text-align: center;
        box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
    }
    .result-card {
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        font-size: 20px;
        font-weight: bold;
        text-align: center;
        box-shadow: 0px 2px 10px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ---------------- BMI CATEGORY FUNCTION ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return (
            "Underweight", "🟦", "background-color:#d0e7ff;",
            """🍽️ Eat high-calorie nutritious foods.
🥛 Drink milk or protein shakes between meals.
🍗 Add lean meats, fish, and eggs.
🥑 Include healthy fats (avocado, nuts, olive oil).
🛏️ Rest well to support weight gain.""",
            """🏋️ Focus on strength training (light weights).
🤸 Add bodyweight exercises (push-ups, squats).
🚶 Gentle walks to build stamina.
🧘 Stretch for flexibility.
📅 Exercise 3–4 times per week."""
        )
    elif bmi < 25:
        return (
            "Normal weight", "🟩", "background-color:#d6f5d6;",
            """🥗 Eat balanced meals (veggies, fruits, grains).
🍗 Keep steady protein intake (fish, chicken, beans).
💧 Drink 2–3L water daily.
🏃 Stay active for at least 30 min/day.
😴 Sleep 7–8 hours each night.""",
            """🏋️ Mix cardio & strength training.
🚴 Try cycling, swimming, or jogging.
🤸 Add flexibility training (yoga, pilates).
⚽ Play sports for fun & fitness.
📅 Stay consistent 4–5 days/week."""
        )
    elif bmi < 30:
        return (
            "Overweight", "🟨", "background-color:#fff5cc;",
            """🥦 Eat more high-fiber foods (vegetables, legumes).
🍵 Replace soda with water/green tea.
🍞 Switch to whole grains.
🚶 Walk 8,000–10,000 steps daily.
⚖️ Watch portion sizes & calories.""",
            """🏃 Do cardio 4–5x weekly (brisk walk, jog, cycling).
🏋️ Add resistance training 2–3x weekly.
🤸 Do core exercises (planks, sit-ups).
🚶 Increase daily activity (stairs, walking).
📅 Track workouts & progress."""
        )
    else:
        return (
            "Obese", "🟥", "background-color:#ffd6cc;",
            """🥬 Eat veggies, lean protein, whole grains.
🍭 Cut sugar drinks & junk food.
🚴 Exercise 30 min/day at comfortable pace.
📉 Aim for slow weight loss (0.5–1kg/week).
👨‍⚕️ Consult doctor/nutritionist for support.""",
            """🚶 Start with low-impact cardio (walking, swimming).
🧘 Gentle yoga or stretching daily.
🏋️ Light strength training (with supervision).
🚴 Cycling for endurance.
📅 Build gradually & stay consistent."""
        )

# ---------------- WEIGHT INPUT ----------------
st.markdown('<div class="info-card">⚖️ Enter Your Weight</div>', unsafe_allow_html=True)
unit = st.selectbox("Select Unit", ["Kilograms", "Pounds"])
weight = st.number_input(f"Enter Your Weight ({unit})", min_value=1.0, step=0.5)

# ---------------- HEIGHT INPUT ----------------
st.markdown('<div class="info-card">📏 Enter Your Height</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    feet = st.number_input("Feet", min_value=1, max_value=8, step=1, value=5)
with col2:
    inches = st.number_input("Inches", min_value=0, max_value=11, step=1, value=7)

# Convert feet+inches → meters
height_m = (feet * 12 + inches) * 0.0254

# ---------------- BMI CALCULATION ----------------
if height_m > 0 and weight > 0:
    weight_kg = weight if unit == "Kilograms" else weight * 0.453592
    bmi = weight_kg / (height_m ** 2)
    category, emoji, style, diet_tips, workout_tips = get_bmi_category(bmi)

    st.markdown(f'<div class="result-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>', unsafe_allow_html=True)

    # Diet Tips
    st.markdown(f"""
    <div class="info-card" style="text-align:left;">
    🍽️ <b>Diet Tips:</b><br>
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
