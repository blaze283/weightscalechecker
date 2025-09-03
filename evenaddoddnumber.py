import streamlit as st
import sqlite3
from datetime import datetime, timedelta

# ------------------- DATABASE -------------------
conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT,
                plan TEXT,
                trial_end DATE
            )""")
conn.commit()

# ------------------- BMI FUNCTION -------------------
def calculate_bmi(weight, height):
    bmi = weight / (height/100)**2
    if bmi < 18.5:
        status = "Underweight"
    elif 18.5 <= bmi < 24.9:
        status = "Normal weight"
    elif 25 <= bmi < 29.9:
        status = "Overweight"
    else:
        status = "Obese"
    return bmi, status

# ------------------- MEAL PLAN -------------------
meal_plan = {
    "Monday": {"Breakfast": "Oatmeal + Banana", "Lunch": "Grilled chicken + Veggies", "Dinner": "Salmon + Brown rice", "Snack": "Nuts"},
    "Tuesday": {"Breakfast": "Scrambled eggs + Toast", "Lunch": "Beef stir fry", "Dinner": "Tuna salad", "Snack": "Yogurt"},
    "Wednesday": {"Breakfast": "Smoothie + Protein", "Lunch": "Chicken wrap", "Dinner": "Grilled fish", "Snack": "Apple"},
    "Thursday": {"Breakfast": "Pancakes + Berries", "Lunch": "Rice + Beans", "Dinner": "Steak + Vegetables", "Snack": "Carrots"},
    "Friday": {"Breakfast": "Boiled eggs + Avocado", "Lunch": "Turkey sandwich", "Dinner": "Pasta + Chicken", "Snack": "Granola"},
    "Saturday": {"Breakfast": "French toast + Orange", "Lunch": "Vegetable soup", "Dinner": "Grilled prawns", "Snack": "Popcorn"},
    "Sunday": {"Breakfast": "Smoothie bowl", "Lunch": "Chicken salad", "Dinner": "Beef stew", "Snack": "Dark chocolate"}
}

# ------------------- EXERCISE PLAN -------------------
exercise_plan = {
    "Beginner": ["10 min walk", "15 squats", "10 push-ups"],
    "Intermediate": ["30 min jog", "20 squats", "15 push-ups", "Plank 1 min"],
    "Advanced": ["45 min run", "30 squats", "20 push-ups", "HIIT 20 mins"]
}

# ------------------- AUTH SYSTEM -------------------
def signup(username, password):
    trial_end = datetime.now() + timedelta(days=7)  # free 7-day trial
    c.execute("INSERT INTO users (username, password, plan, trial_end) VALUES (?, ?, ?, ?)",
              (username, password, "Free Trial", trial_end.strftime("%Y-%m-%d")))
    conn.commit()

def login(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone()

def check_plan(user):
    plan, trial_end = user[3], user[4]
    if plan == "Free Trial" and datetime.now() > datetime.strptime(trial_end, "%Y-%m-%d"):
        return "Expired"
    return plan

# ------------------- STREAMLIT APP -------------------
st.set_page_config(page_title="Fitness App", page_icon="🏋️", layout="centered")
st.title("🏋️ Fitness & Health App")

# Session state
if "user" not in st.session_state:
    st.session_state.user = None

# Authentication
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            user = login(username, password)
            if user:
                st.session_state.user = user
                st.success("✅ Logged in successfully")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")

    with tab2:
        new_user = st.text_input("Create Username", key="signup_user")
        new_pass = st.text_input("Create Password", type="password", key="signup_pass")
        if st.button("Sign Up"):
            signup(new_user, new_pass)
            st.session_state.user = login(new_user, new_pass)  # Auto-login after signup
            st.success("🎉 Account created! You are now logged in.")
            st.rerun()

else:
    user = st.session_state.user
    st.sidebar.success(f"👋 Welcome, {user[1]}")

    plan_status = check_plan(user)
    if plan_status == "Expired":
        st.error("⚠️ Your free trial has expired. Please choose a plan.")
        if st.button("Upgrade to Basic (₦2000/month)"):
            c.execute("UPDATE users SET plan=? WHERE id=?", ("Basic", user[0]))
            conn.commit()
            st.success("✅ Subscribed to Basic Plan")
            st.rerun()
    else:
        st.info(f"📌 Current Plan: {plan_status}")

        # ------------------- BMI -------------------
        st.header("⚖️ BMI Calculator")
        weight = st.number_input("Enter your weight (kg):", min_value=1.0, max_value=300.0, step=0.5)
        height = st.number_input("Enter your height (cm):", min_value=50.0, max_value=250.0, step=0.5)
        if st.button("Check BMI"):
            bmi, status = calculate_bmi(weight, height)
            st.success(f"Your BMI is {bmi:.1f} → {status}")

        # ------------------- Converter -------------------
        st.header("🔄 Weight Converter")
        unit = st.radio("Convert weight to:", ["kg to lbs", "lbs to kg"])
        val = st.number_input("Enter value to convert:", 0.0, 500.0, 0.0)
        if unit == "kg to lbs":
            st.write(f"{val} kg = {val * 2.205:.2f} lbs")
        else:
            st.write(f"{val} lbs = {val / 2.205:.2f} kg")

        # ------------------- Meal Plan -------------------
        st.header("🍽️ Weekly Meal Plan")
        for day, meals in meal_plan.items():
            with st.expander(day):
                for meal, food in meals.items():
                    st.write(f"- {meal}: {food}")

        # ------------------- Exercise Plan -------------------
        st.header("🏃 Exercise Plan")
        level = st.selectbox("Choose your fitness level:", ["Beginner", "Intermediate", "Advanced"])
        st.write(f"**{level} Routine:**")
        for ex in exercise_plan[level]:
            st.write(f"- {ex}")
