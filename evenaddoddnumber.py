# vitalsync_pro_full.py
# VitalSync Pro - Streamlit full prototype
# Single-file prototype demonstrating:
# - Email register/sign-in (SQLite)
# - Package registration (Free/Premium/Pro)
# - Allergies/dietary restrictions
# - Height/weight -> meal plan generator
# - Photo upload for meal logging (simulated recognition)
# - Barcode/manual food logging
# - Grocery list generation
# - Watch ordering (mock) and watch pairing simulator
# - Persistent timers, orders, and simple gamification (badges)
# - Export weekly report as PDF
#
# NOTE: Replace simulated parts (AI, OAuth, BLE, payments) with real services for production.

import streamlit as st
import sqlite3
import uuid
import time
from datetime import datetime, timedelta, date
import math
import pandas as pd
from PIL import Image
import io

DB_PATH = "vitalsync_pro_full.db"

# -----------------------
# Database helpers
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        package TEXT,
        height_cm REAL,
        weight_kg REAL,
        allergies TEXT,
        points INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        product TEXT,
        price REAL,
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS timers (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        type TEXT,
        label TEXT,
        end_ts REAL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS meals (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        logged_at TEXT,
        items TEXT,
        calories INTEGER,
        method TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS watch_sim (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        paired INTEGER,
        last_sync TEXT,
        mock_hr INTEGER,
        mock_spo2 INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS family (
        id TEXT PRIMARY KEY,
        owner_id TEXT,
        member_name TEXT,
        height_cm REAL,
        weight_kg REAL,
        allergies TEXT
    )
    """)
    conn.commit()
    conn.close()

def run_query(query, args=(), fetch=False):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute(query, args)
    data = None
    if fetch:
        data = c.fetchall()
    conn.commit()
    conn.close()
    return data

# -----------------------
# Utilities
# -----------------------
def bmi(weight_kg, height_cm):
    try:
        h_m = height_cm / 100.0
        return weight_kg / (h_m * h_m)
    except:
        return None

def generate_meal_plan(height_cm, weight_kg, allergies, goal='maintain', activity='Moderate'):
    b = bmi(weight_kg, height_cm)
    if b is None:
        return None
    # crude base metabolic estimate
    base = 2000
    if b < 18.5:
        base = 2200
    elif b < 25:
        base = 2000
    elif b < 30:
        base = 1800
    else:
        base = 1600

    if goal == 'lose':
        base -= 300
    elif goal == 'gain':
        base += 300

    # activity multiplier
    mult = {'Sedentary': 1.0, 'Light':1.1, 'Moderate':1.25, 'Active':1.4}.get(activity,1.25)
    cal = int(base * mult)

    protein_g = int(0.25 * cal / 4)
    fats_g = int(0.25 * cal / 9)
    carbs_g = int(0.5 * cal / 4)

    meal_templates = [
        {'name':'Breakfast','items':['Oatmeal','Banana','Eggs','Yogurt']},
        {'name':'Lunch','items':['Grilled Chicken','Brown Rice','Steamed Vegetables','Salad']},
        {'name':'Dinner','items':['Baked Fish','Quinoa','Roasted Veggies','Green Salad']}
    ]

    allergy_keys = [a.strip().lower() for a in (allergies or "").split(',') if a.strip()]
    result_meals = []
    for m in meal_templates:
        items = []
        for it in m['items']:
            low = it.lower()
            bad = any(a in low for a in allergy_keys)
            if not bad:
                items.append(it)
        if not items:
            items = ['(No suitable items — check allergies)']
        result_meals.append({'name': m['name'], 'items': items})
    return {'calories':cal, 'protein_g': protein_g, 'fats_g': fats_g, 'carbs_g': carbs_g, 'meals': result_meals}

def simulate_food_recognition(image_bytes):
    # Simulated recognizer: try to heuristically identify food by filename-like bytes or ask user.
    # In production, replace with TensorFlow/PyTorch model or cloud Vision API.
    # Here we return a sample candidate list and estimated calories.
    candidates = [
        ('Rice & Beans', 550),
        ('Jollof Rice', 600),
        ('Fried Plantain', 300),
        ('Grilled Fish', 280),
        ('Salad', 150)
    ]
    # naive: return first two as guesses
    return candidates[:2]

def add_user(name,email,password):
    user_id = str(uuid.uuid4())
    run_query("INSERT INTO users (id,name,email,password,package,points) VALUES (?,?,?,?,?,?)",
              (user_id,name,email,password,'Free',0))
    return user_id

def get_user_by_email(email):
    res = run_query("SELECT id,name,email,password,package,height_cm,weight_kg,allergies,points FROM users WHERE email=?",(email,),fetch=True)
    return res[0] if res else None

def save_user_profile(user_id, name=None, package=None, height_cm=None, weight_kg=None, allergies=None):
    # update only provided
    cur = get_user(user_id)
    if not cur:
        return
    if name:
        run_query("UPDATE users SET name=? WHERE id=?",(name,user_id))
    if package:
        run_query("UPDATE users SET package=? WHERE id=?",(package,user_id))
    if height_cm is not None:
        run_query("UPDATE users SET height_cm=? WHERE id=?",(height_cm,user_id))
    if weight_kg is not None:
        run_query("UPDATE users SET weight_kg=? WHERE id=?",(weight_kg,user_id))
    if allergies is not None:
        run_query("UPDATE users SET allergies=? WHERE id=?",(allergies,user_id))

def get_user(user_id):
    res = run_query("SELECT id,name,email,package,height_cm,weight_kg,allergies,points FROM users WHERE id=?",(user_id,),fetch=True)
    return res[0] if res else None

def add_order(user_id, product, price):
    oid = str(uuid.uuid4())
    run_query("INSERT INTO orders (id,user_id,product,price,created_at) VALUES (?,?,?,?,?)",
              (oid,user_id,product,price,datetime.utcnow().isoformat()))
    return oid

def add_timer(user_id, ttype, label, seconds):
    tid = str(uuid.uuid4())
    end_ts = time.time() + seconds
    run_query("INSERT INTO timers (id,user_id,type,label,end_ts) VALUES (?,?,?,?,?)",
              (tid,user_id,ttype,label,end_ts))
    return tid

def get_timers(user_id):
    return run_query("SELECT id,type,label,end_ts FROM timers WHERE user_id=?",(user_id,),fetch=True)

def remove_timer(tid):
    run_query("DELETE FROM timers WHERE id=?",(tid,))

def log_meal(user_id, items, calories, method='manual'):
    mid = str(uuid.uuid4())
    run_query("INSERT INTO meals (id,user_id,logged_at,items,calories,method) VALUES (?,?,?,?,?,?)",
              (mid,user_id,datetime.utcnow().isoformat(),','.join(items),calories,method))
    # reward points for logging
    run_query("UPDATE users SET points = points + ? WHERE id=?",(10,user_id))
    return mid

def get_meals(user_id, days=7):
    cutoff = datetime.utcnow() - timedelta(days=days)
    return run_query("SELECT id,logged_at,items,calories,method FROM meals WHERE user_id=? AND logged_at>=? ORDER BY logged_at DESC",
                     (user_id,cutoff.isoformat()),fetch=True)

def init_watch_for_user(user_id):
    existing = run_query("SELECT id FROM watch_sim WHERE user_id=?",(user_id,),fetch=True)
    if existing:
        return
    wid = str(uuid.uuid4())
    run_query("INSERT INTO watch_sim (id,user_id,paired,last_sync,mock_hr,mock_spo2) VALUES (?,?,?,?,?,?)",
              (wid,user_id,0,None,70,98))

def pair_watch(user_id):
    init_watch_for_user(user_id)
    run_query("UPDATE watch_sim SET paired=1,last_sync=? WHERE user_id=?",(datetime.utcnow().isoformat(),user_id))

def unpair_watch(user_id):
    run_query("UPDATE watch_sim SET paired=0 WHERE user_id=?",(user_id,))

def get_watch(user_id):
    res = run_query("SELECT id,user_id,paired,last_sync,mock_hr,mock_spo2 FROM watch_sim WHERE user_id=?",(user_id,),fetch=True)
    return res[0] if res else None

def simulate_watch_sync(user_id):
    # update mock vitals and last_sync
    hr = 60 + int(40 * math.sin(time.time()/30))  # silly changing number
    spo2 = 96 + int(2*math.cos(time.time()/45))
    run_query("UPDATE watch_sim SET mock_hr=?, mock_spo2=?, last_sync=? WHERE user_id=?",
              (hr, spo2, datetime.utcnow().isoformat(), user_id))
    return {'hr':hr,'spo2':spo2,'last_sync':datetime.utcnow().isoformat()}

# -----------------------
# PDF export helper
# -----------------------
def export_report_pdf(user_id):
    u = get_user(user_id)
    meals = get_meals(user_id, days=30)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200,10, txt=f"VitalSync Pro - Report for {u[1]}", ln=True, align='C')
    pdf.ln(4)
    pdf.cell(200,10, txt=f"Generated: {datetime.utcnow().isoformat()}", ln=True)
    pdf.ln(6)
    pdf.cell(200,8, txt=f"Package: {u[3]}  |  Points: {u[7]}", ln=True)
    pdf.ln(6)
    pdf.cell(0,8, txt="Recent Meals (30 days):", ln=True)
    pdf.ln(2)
    for m in meals:
        logged_at = m[1]
        items = m[2]
        calories = m[3]
        pdf.multi_cell(0,8, txt=f"- {logged_at}: {items} ({calories} kcal)")
    # return PDF bytes
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# -----------------------
# App UI
# -----------------------
st.set_page_config(page_title="VitalSync Pro — Full Prototype", layout="wide")
init_db()

if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

st.title("VitalSync Pro — Full Prototype")

# ---- Authentication (simple email/password) ----
with st.expander("Sign in / Register"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sign in (email)")
        email_in = st.text_input("Email", key="signin_email")
        pw_in = st.text_input("Password", type="password", key="signin_pw")
        if st.button("Sign in"):
            user = get_user_by_email(email_in)
            if user and user[3] == pw_in:
                st.session_state['user_id'] = user[0]
                st.success(f"Signed in as {user[1]} ({user[2]})")
            else:
                st.error("Invalid credentials")
    with col2:
        st.subheader("Register")
        name_r = st.text_input("Name", key="reg_name")
        email_r = st.text_input("Email", key="reg_email")
        pw_r = st.text_input("Password", type="password", key="reg_pw")
        if st.button("Register"):
            if get_user_by_email(email_r):
                st.error("User already exists")
            else:
                uid = add_user(name_r, email_r, pw_r)
                st.session_state['user_id'] = uid
                st.success("Registered and signed in")

    st.markdown("---")
    st.info("OAuth providers (Google / Apple / Amazon / Facebook) are simulated in this prototype. Replace with Firebase Auth or another OAuth provider for production.")

if not st.session_state['user_id']:
    st.info("Please register or sign in above to continue.")
    st.stop()

user = get_user(st.session_state['user_id'])
user_id = user[0]

# Ensure watch_sim row exists
init_watch_for_user(user_id)

# Sidebar: profile, package, order watch
with st.sidebar:
    st.header("Profile & Package")
    st.write("Name:", user[1])
    st.write("Email:", user[2])
    name_edit = st.text_input("Edit name", value=user[1])
    package_choice = st.selectbox("Choose package", ['Free','Premium','Pro'], index=['Free','Premium','Pro'].index(user[3]))
    if st.button("Save Profile"):
        save_user_profile(user_id, name=name_edit, package=package_choice)
        st.experimental_rerun()
    st.markdown("---")
    st.subheader("Order VitalSync Watch")
    watch_catalog = {'VitalSync Band':49.99, 'VitalSync Watch Pro':129.99}
    watch_sel = st.selectbox("Select watch", list(watch_catalog.keys()))
    qty = st.number_input("Qty", min_value=1, value=1)
    if st.button("Place Order"):
        oid = add_order(user_id, f"{watch_sel} x{qty}", watch_catalog[watch_sel]*qty)
        st.success(f"Mock order placed. Order ID: {oid}")
    st.markdown("---")
    st.subheader("Watch Pairing Simulator")
    watch = get_watch(user_id)
    paired = bool(watch[2])
    st.write("Paired:", paired)
    if not paired:
        if st.button("Pair Watch (simulate)"):
            pair_watch(user_id)
            st.experimental_rerun()
    else:
        if st.button("Unpair Watch (simulate)"):
            unpair_watch(user_id)
            st.experimental_rerun()
        if st.button("Sync Watch (simulate)"):
            sync = simulate_watch_sync(user_id)
            st.success(f"Watch synced: HR={sync['hr']} bpm, SpO2={sync['spo2']}%")
    st.markdown("---")
    st.subheader("Export")
    if st.button("Download 30-day PDF report"):
        pdf_buf = export_report_pdf(user_id)
        st.download_button("Download PDF", data=pdf_buf, file_name="vitalsync_report.pdf", mime="application/pdf")

# Main layout
col1, col2 = st.columns([2,1])
with col1:
    st.header("Dashboard")
    st.metric("Package", user[3])
    st.metric("Points", user[7] or 0)
    # Show last synced vitals if paired
    watch = get_watch(user_id)
    if watch and watch[2]:
        st.subheader("Watch - Latest Vitals (simulated)")
        st.write("Last sync:", watch[3])
        st.write("Heart rate (mock):", watch[4], "bpm")
        st.write("SpO2 (mock):", watch[5], "%")
    else:
        st.info("No watch paired. Pair a watch in the sidebar.")

    st.markdown("---")
    st.subheader("Health Inputs & Meal Plan")
    with st.form("profile_form"):
        h = st.number_input("Height (cm)", min_value=50.0, max_value=250.0, value=user[4] or 170.0, key="h")
        w = st.number_input("Weight (kg)", min_value=20.0, max_value=400.0, value=user[5] or 70.0, key="w")
        age = st.number_input("Age", min_value=5, max_value=120, value=30, key="age")
        activity = st.selectbox("Activity Level", ['Sedentary','Light','Moderate','Active'], index=2)
        goal = st.selectbox("Goal", ['maintain','lose','gain'], index=0)
        allergies = st.text_input("Allergies (comma separated)", value=user[6] or "")
        submitted = st.form_submit_button("Save & Generate Meal Plan")
        if submitted:
            save_user_profile(user_id, height_cm=float(h), weight_kg=float(w), allergies=allergies)
            st.success("Saved profile.")

    if user[4] and user[5]:
        plan = generate_meal_plan(user[4], user[5], user[6] or "", goal=goal, activity=activity)
        if plan:
            st.subheader("Personalized Meal Plan (sample)")
            st.write(f"Estimated daily calories: {plan['calories']} kcal — Protein: {plan['protein_g']}g — Carbs: {plan['carbs_g']}g — Fats: {plan['fats_g']}g")
            for m in plan['meals']:
                st.markdown(f"**{m['name']}**")
                for it in m['items']:
                    st.write("- " + it)
    else:
        st.info("Enter height and weight to get a meal plan.")

    st.markdown("---")
    st.subheader("Auto Meal Log (Photo / Barcode / Manual)")
    st.write("You can upload a photo (simulated recognition), scan a barcode (manual input), or type the meal.")
    tab1,tab2,tab3 = st.tabs(["Photo", "Barcode/Packaged", "Manual"])
    with tab1:
        st.write("Upload a photo; a simulated recognizer will suggest items (replace with real AI later).")
        uploaded = st.file_uploader("Upload meal photo", type=["png","jpg","jpeg"])
        if uploaded:
            img = Image.open(uploaded)
            st.image(img, caption="Uploaded meal photo", use_column_width=True)
            # Simulate recognition
            candidates = simulate_food_recognition(uploaded.read())
            st.write("AI candidates (simulated):")
            for i,(name, kcal) in enumerate(candidates):
                st.write(f"{i+1}. {name} — approx {kcal} kcal")
            chosen = st.multiselect("Choose items that match this meal", [c[0] for c in candidates])
            override = st.text_input("Or type items manually (comma separated)")
            if st.button("Log meal from photo"):
                items = chosen if chosen else ([x.strip() for x in override.split(',') if x.strip()] or ["Unknown meal"])
                cal = sum([c[1] for c in candidates if c[0] in items]) or 300
                mid = log_meal(user_id, items, cal, method='photo')
                st.success(f"Meal logged (id {mid}). Calories: {cal}")

    with tab2:
        st.write("Scan barcode or enter packaged food info.")
        barcode = st.text_input("Barcode (type) / product name")
        est_cal = st.number_input("Estimated calories", min_value=0, value=300)
        if st.button("Log packaged meal"):
            items = [barcode or "Packaged Food"]
            mid = log_meal(user_id, items, est_cal, method='barcode')
            st.success(f"Packaged meal logged (id {mid}). Calories: {est_cal}")

    with tab3:
        txt = st.text_area("Type what you ate (comma separated)", placeholder="e.g., Rice, Beans, Chicken")
        cal = st.number_input("Estimated calories", min_value=0, value=400, key="manual_cal")
        if st.button("Log manual meal"):
            items = [x.strip() for x in txt.split(",") if x.strip()]
            if not items:
                st.error("Type at least one item")
            else:
                mid = log_meal(user_id, items, cal, method='manual')
                st.success(f"Meal logged (id {mid}). Calories: {cal}")

    st.markdown("---")
    st.subheader("Workout Timer (runs while page is open)")
    if 'workout_end' not in st.session_state:
        st.session_state['workout_end'] = None
    w_minutes = st.number_input("Workout minutes", min_value=1, max_value=180, value=20, key="wm")
    if st.button("Start Workout Timer"):
        st.session_state['workout_end'] = time.time() + w_minutes*60
    if st.session_state['workout_end']:
        rem = int(st.session_state['workout_end'] - time.time())
        if rem > 0:
            st.info(f"Workout time remaining: {timedelta(seconds=rem)}")
        else:
            st.success("Workout complete!")
            st.session_state['workout_end'] = None

with col2:
    st.header("Active Timers & Quick Actions")
    timers = get_timers(user_id)
    if not timers:
        st.write("No active timers.")
    else:
        for t in timers:
            tid, ttype, label, end_ts = t
            rem = int(end_ts - time.time())
            if rem > 0:
                st.write(f"[{ttype}] {label} — remaining: {timedelta(seconds=rem)}")
                if st.button(f"Cancel {label}", key='c_'+tid):
                    remove_timer(tid)
                    st.experimental_rerun()
            else:
                st.warning(f"[{ttype}] {label} — READY (click to remove)")
                if st.button(f"Remove {label}", key='r_'+tid):
                    remove_timer(tid)
                    st.experimental_rerun()

    st.markdown("---")
    st.subheader("Start a Timer")
    ttype = st.selectbox("Type", ['Meal','Hydration','Medication','Workout'])
    tlabel = st.text_input("Label", value=f"{ttype} reminder")
    minutes = st.number_input("Minutes from now", min_value=1, value=60)
    if st.button("Start Timer (create)"):
        add_timer(user_id, ttype, tlabel, int(minutes*60))
        st.success("Timer started.")

    st.markdown("---")
    st.subheader("Recent Meals")
    recent = get_meals(user_id, days=14)
    if not recent:
        st.write("No meals logged yet.")
    else:
        for m in recent:
            st.write(f"- {m[1]} | {m[2]} | {m[3]} kcal | {m[4]}")

    st.markdown("---")
    st.subheader("Family Accounts")
    st.write("Add a family member profile for kids/others.")
    fn = st.text_input("Member name")
    fh = st.number_input("Height (cm)", min_value=50.0, max_value=250.0, value=120.0, key="fh")
    fw = st.number_input("Weight (kg)", min_value=5.0, max_value=200.0, value=30.0, key="fw")
    fall = st.text_input("Allergies (comma separated)", key="fall")
    if st.button("Add family member"):
        fid = str(uuid.uuid4())
        run_query("INSERT INTO family (id,owner_id,member_name,height_cm,weight_kg,allergies) VALUES (?,?,?,?,?,?)",
                  (fid,user_id,fn,fh,fw,fall))
        st.success("Family member added")

    st.markdown("---")
    st.subheader("Gamification / Badges")
    st.write("Points: ", user[7] or 0)
    # simple badge: log >=7 meals -> 'Consistent Logger'
    meals_7d = get_meals(user_id, days=7)
    if len(meals_7d) >= 7:
        st.success("Badge unlocked: Consistent Logger 🎖️")
    if (user[7] or 0) >= 100:
        st.success("Badge unlocked: Health Pro 🏆")

# Footer / notes
st.markdown("---")
st.caption("This prototype simulates AI food recognition, OAuth, BLE and payments. Replace simulation stubs with production services: TensorFlow or cloud Vision for food recognition; Firebase Auth for OAuth; BLE libraries and mobile app for real watch pairing; Stripe/Flutterwave/Shopify for payments and orders.")


