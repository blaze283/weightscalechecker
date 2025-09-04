# app.py
import streamlit as st
import sqlite3
import bcrypt
import base64
import mimetypes
import json
import os
import uuid
from datetime import datetime, timedelta

# -------------------------
# Config & DB
# -------------------------
st.set_page_config(page_title="Health & Meal Planner", page_icon="⚖️", layout="centered")
DB_PATH = "users.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Users & plans tables
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password_hash TEXT,
    plan TEXT,
    trial_end DATE
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS saved_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    created_at TEXT,
    plan_json TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# -------------------------
# Utilities: auth + crypto
# -------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_user(email: str, password: str):
    try:
        trial_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        h = hash_password(password)
        c.execute("INSERT INTO users (email, password_hash, plan, trial_end) VALUES (?, ?, ?, ?)",
                  (email, h, "Free Trial", trial_end))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Email already registered."

def get_user_by_email(email: str):
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    return c.fetchone()

def authenticate(email: str, password: str):
    user = get_user_by_email(email)
    if not user: return None
    if verify_password(password, user[2]):
        return user
    return None

def save_plan_db(user_id: int, name: str, plan_obj: dict):
    c.execute("INSERT INTO saved_plans (user_id, name, created_at, plan_json) VALUES (?, ?, ?, ?)",
              (user_id, name, datetime.now().isoformat(), json.dumps(plan_obj)))
    conn.commit()

def list_saved_plans(user_id: int):
    c.execute("SELECT id, name, created_at FROM saved_plans WHERE user_id=? ORDER BY id DESC", (user_id,))
    return c.fetchall()

def load_saved_plan(plan_id: int):
    c.execute("SELECT plan_json FROM saved_plans WHERE id=?", (plan_id,))
    r = c.fetchone()
    return json.loads(r[0]) if r else None

# -------------------------
# Conversions & BMI
# -------------------------
def kg_to_lbs(kg): return kg * 2.20462
def lbs_to_kg(lbs): return lbs * 0.45359237

def bmi_from(weight_kg: float, height_m: float):
    if height_m <= 0: return None
    return weight_kg / (height_m ** 2)

def bmi_category(bmi: float):
    if bmi < 18.5: return "Underweight", "🔵"
    if bmi < 25: return "Normal", "🟢"
    if bmi < 30: return "Overweight", "🟡"
    return "Obese", "🔴"

# -------------------------
# Personalization logic
# -------------------------
def estimate_maintenance_calories(weight_kg: float):
    # Simple rule-of-thumb (no age/sex): maintenance ≈ weight_kg * 25 kcal/day
    return max(1200, weight_kg * 25)

def target_calories(weight_kg: float, bmi_cat: str):
    maintenance = estimate_maintenance_calories(weight_kg)
    if bmi_cat == "Underweight":
        return maintenance + 500
    if bmi_cat == "Normal":
        return maintenance
    if bmi_cat == "Overweight":
        return max(1200, maintenance - 400)
    return max(1200, maintenance - 600)

BASE_MEALS = {
    "Breakfast": ["Oatmeal + banana", "Scrambled eggs + toast", "Smoothie + protein", "Pancakes + berries", "Boiled eggs + avocado"],
    "Lunch": ["Grilled chicken + veggies", "Beef stir-fry + rice", "Tuna salad + greens", "Rice & beans", "Turkey sandwich"],
    "Dinner": ["Salmon + brown rice", "Grilled fish + salad", "Steak + vegetables", "Pasta + chicken", "Vegetable soup + bread"],
    "Snack": ["Nuts", "Yogurt", "Apple", "Carrots & hummus", "Granola"]
}

def make_weekly_meal_plan(target_cal: float):
    # distribution: breakfast 25%, lunch 30%, dinner 30%, snack 15%
    dist = {"Breakfast": 0.25, "Lunch": 0.30, "Dinner": 0.30, "Snack": 0.15}
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {}
    for i,day in enumerate(days):
        day_meals = {}
        # pick meal by rotating BASE_MEALS lists for variety
        for meal_type, choices in BASE_MEALS.items():
            choice = choices[i % len(choices)]
            cal = int(round(target_cal * dist[meal_type]))
            # small note to adjust portion by target (we'll show cal)
            day_meals[meal_type] = {"item": choice, "time": meal_default_time(meal_type), "cal": cal}
        plan[day] = day_meals
    return plan

def meal_default_time(meal_type):
    times = {"Breakfast":"08:00", "Lunch":"13:00", "Dinner":"19:00", "Snack":"16:00"}
    return times.get(meal_type, "12:00")

def make_weekly_exercise_plan(bmi_cat: str, weight_kg: float):
    # Create weekly exercise plan adapted to BMI category + weight scaling
    # Scale factor: heavier users might want slightly lower-impact longer durations if overweight/obese
    factor = 1.0
    if bmi_cat == "Underweight": factor = 0.9
    elif bmi_cat == "Normal": factor = 1.0
    elif bmi_cat == "Overweight": factor = 1.15
    else: factor = 1.2  # Obese: longer/lower-intensity sessions

    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    plan = {}
    for d in days:
        if bmi_cat == "Underweight":
            # focus on strength + light cardio
            plan[d] = [
                {"time":"07:00","activity":"Light cardio (15 min walk)"},
                {"time":"07:20","activity":"Strength (bodyweight/resistance – 30 min)"}
            ]
        elif bmi_cat == "Normal":
            plan[d] = [
                {"time":"06:30","activity":"Cardio (30 min run/ride)"},
                {"time":"07:10","activity":"Strength (30 min)"} if d in ["Monday","Wednesday","Friday"] else {"time":"07:10","activity":"Mobility / Stretching (15 min)"}
            ]
        elif bmi_cat == "Overweight":
            if d in ["Monday","Wednesday","Friday"]:
                plan[d] = [
                    {"time":"06:00","activity":f"Moderate cardio ({int(30*factor)} min)"},
                    {"time":"06:40","activity":"Strength (20-25 min)"}
                ]
            else:
                plan[d] = [
                    {"time":"07:00","activity":f"Brisk walk ({int(35*factor)} min)"},
                    {"time":"07:40","activity":"Core & mobility (15 min)"}
                ]
        else: # Obese
            if d in ["Monday","Wednesday","Friday"]:
                plan[d] = [
                    {"time":"06:00","activity":f"Low-impact cardio ({int(35*factor)} min)"},
                    {"time":"06:45","activity":"Resistance + mobility (20 min)"}
                ]
            else:
                plan[d] = [
                    {"time":"07:00","activity":f"Walking or pool session ({int(40*factor)} min)"},
                    {"time":"07:50","activity":"Gentle stretching (15 min)"}
                ]
    return plan

# -------------------------
# UI helpers
# -------------------------
def inject_css():
    st.markdown("""
    <style>
    .title {font-weight:800; font-size:28px; text-align:center; margin-bottom:8px;}
    .card {background:linear-gradient(135deg,#667eea,#764ba2); padding:12px; border-radius:10px; color:white}
    .result {background:linear-gradient(135deg,#11998e,#38ef7d); padding:10px; border-radius:8px; color:white}
    </style>
    """, unsafe_allow_html=True)

def apply_background(bg_image):
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded = base64.b64encode(bg_image.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.18), rgba(0,0,0,0.18)), url("data:{mime_type};base64,{encoded}");
            background-size: cover;
            background-position: center;
        }}
        </style>
        """, unsafe_allow_html=True)

# -------------------------
# App layout & auth flow
# -------------------------
inject_css()
st.title("⚖️ Personalized Health, Meal & Exercise Planner")

if "user" not in st.session_state:
    st.session_state.user = None

# AUTH
if not st.session_state.user:
    auth_tabs = st.tabs(["Login","Sign Up"])
    with auth_tabs[0]:
        st.subheader("Login")
        login_email = st.text_input("Email", key="login_email")
        login_pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            u = authenticate(login_email.strip().lower(), login_pw)
            if u:
                st.session_state.user = u
                st.success("Logged in — welcome back!")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")
    with auth_tabs[1]:
        st.subheader("Create an account (7-day free trial)")
        signup_email = st.text_input("Email", key="signup_email")
        signup_pw = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Sign Up"):
            ok, err = create_user(signup_email.strip().lower(), signup_pw)
            if ok:
                st.session_state.user = get_user_by_email(signup_email.strip().lower())
                st.success("Account created — you are signed in!")
                st.experimental_rerun()
            else:
                st.error(err)
    st.info("Tip: After sign up you'll be logged in automatically.")
    st.stop()

# LOGGED-IN UI
user = st.session_state.user
st.sidebar.markdown(f"**User:** {user[1]}")
st.sidebar.write(f"Plan: {user[3] or 'Free Trial'}")
if st.sidebar.button("Log out"):
    st.session_state.user = None
    st.experimental_rerun()

# Background customization
st.markdown("### 🎨 Customize (optional)")
bg = st.file_uploader("Upload background (jpg, png)", type=["jpg","jpeg","png"])
apply_background(bg)

# Inputs: unit, weight, height in ft+in
st.markdown("### 🔢 Your measurements")
col1, col2, col3 = st.columns([1.2,1,1])
with col1:
    unit_sel = st.selectbox("Weight unit", ["Kilograms (kg)","Pounds (lbs)"], index=0)
with col2:
    weight_input = st.number_input("Weight", min_value=0.1, max_value=999.9, format="%.1f", value=70.0)
with col3:
    # height feet and inches
    feet = st.number_input("Feet", min_value=1, max_value=8, value=5)
    inches = st.number_input("Inches", min_value=0, max_value=11, value=7)

# convert to kg and meters
weight_kg = weight_input if unit_sel.startswith("Kilograms") else lbs_to_kg(weight_input)
height_m = (feet * 12 + inches) * 0.0254

# compute BMI & category
bmi = None
bmi_text = ""
if height_m > 0:
    bmi = bmi_from(weight_kg, height_m)
    cat, emoji = bmi_category(bmi)
    bmi_text = f"{emoji} BMI: {bmi:.1f} — {cat}"

# Show summary card
st.markdown("---")
st.markdown("<div class='card'><strong>Personal Summary</strong></div>", unsafe_allow_html=True)
colA, colB, colC = st.columns(3)
with colA:
    st.metric("Weight (kg)", f"{weight_kg:.1f}")
with colB:
    st.metric("Height (m)", f"{height_m:.2f}")
with colC:
    st.metric("BMI", f"{bmi:.1f}" if bmi else "—")
if bmi:
    st.write(bmi_text)

# Calculate caloric targets and generate plans
maintenance = estimate_maintenance_calories(weight_kg)
target = target_calories(weight_kg, cat)
st.markdown("---")
st.markdown("<div class='result'><strong>Estimated daily calories</strong></div>", unsafe_allow_html=True)
st.write(f"- Maintenance estimate: **{int(maintenance)} kcal/day** (rule-of-thumb)")
st.write(f"- Recommended target (based on BMI): **{int(target)} kcal/day**")

# Buttons to generate weekly plans
if st.button("Generate weekly Meal & Exercise Plan"):
    weekly_meals = make_weekly_meal_plan(target)
    weekly_ex = make_weekly_exercise_plan(cat, weight_kg)
    st.session_state.generated_plan = {"created": datetime.now().isoformat(),
                                       "weight_kg": weight_kg, "height_m": height_m, "bmi": bmi,
                                       "bmi_category": cat, "daily_target_cal": int(target),
                                       "meals": weekly_meals, "exercise": weekly_ex}
    st.success("Weekly plan generated — scroll down to view it.")

if "generated_plan" in st.session_state:
    gp = st.session_state.generated_plan
    st.markdown("## 📅 Your Weekly Meal Plan (personalized)")
    for day, meals in gp["meals"].items():
        with st.expander(f"{day} — approx {sum(m['cal'] for m in meals.values())} kcal"):
            for meal_name, meal_info in meals.items():
                st.write(f"- **{meal_name} ({meal_info['time']})**: {meal_info['item']} — approx **{meal_info['cal']} kcal**")

    st.markdown("---")
    st.markdown("## 🏋️ Weekly Exercise Plan (personalized)")
    for day, activities in gp["exercise"].items():
        with st.expander(day):
            for a in activities:
                st.write(f"- {a['time']} — {a['activity']}")

    st.markdown("---")
    # Save / Download
    col1, col2 = st.columns(2)
    with col1:
        plan_name = st.text_input("Plan name (for saving)", value=f"My plan {datetime.now().date()}")
        if st.button("Save plan to my account"):
            save_plan_db(user[0], plan_name, gp)
            st.success("Saved to your account.")
    with col2:
        st.download_button("Download plan (JSON)", data=json.dumps(gp, indent=2), file_name="weekly_plan.json", mime="application/json")

# Show previously saved plans
st.markdown("---")
st.markdown("### 💾 Previously saved plans")
saved = list_saved_plans(user[0])
if saved:
    for pid, name, created in saved:
        cols = st.columns([3,1,1])
        cols[0].write(f"**{name}** — {created}")
        if cols[1].button("Load", key=f"load_{pid}"):
            sp = load_saved_plan(pid)
            st.session_state.generated_plan = sp
            st.success("Loaded plan into the generator view.")
            st.experimental_rerun()
        if cols[2].button("Delete", key=f"del_{pid}"):
            c.execute("DELETE FROM saved_plans WHERE id=?", (pid,))
            conn.commit()
            st.experimental_rerun()
else:
    st.write("No saved plans yet. Generate a plan and save it!")

# Footer
st.markdown("---")
st.caption("This planner estimates calories and suggests meals & workouts for demo/personal use. For medical advice, consult a professional.")
