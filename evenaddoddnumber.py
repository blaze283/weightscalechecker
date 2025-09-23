import streamlit as st
import sqlite3
import time
from datetime import datetime, timedelta
import math
import uuid

# -----------------------
# VitalSync Pro - Streamlit Prototype
# Single-file prototype demonstrating:
# - Simple "OAuth" simulated sign-in (placeholders)
# - Package registration (Free/Premium/Pro)
# - Add allergies/dietary restrictions
# - Input height/weight -> generate meal plan
# - Order smartwatch (mock order stored)
# - Timers for meal, hydration, medication, and workouts
# - Simple SQLite persistence
# NOTE: This is a prototype. Real OAuth, payments, and wearable integrations
# require production-ready implementations and credentials.
# -----------------------

DB_PATH = "vitalsync_pro.db"

# -----------------------
# Database helpers
# -----------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            package TEXT,
            height_cm REAL,
            weight_kg REAL,
            allergies TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            product TEXT,
            price REAL,
            created_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS timers (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            label TEXT,
            end_ts REAL
        )
        """
    )
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def save_user(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "REPLACE INTO users (id, name, email, package, height_cm, weight_kg, allergies) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user['id'], user['name'], user['email'], user['package'], user.get('height_cm'), user.get('weight_kg'), ','.join(user.get('allergies', [])))
    )
    conn.commit()
    conn.close()


def add_order(user_id, product, price):
    oid = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO orders (id, user_id, product, price, created_at) VALUES (?, ?, ?, ?, ?)",
              (oid, user_id, product, price, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return oid


def add_timer(user_id, ttype, label, seconds):
    tid = str(uuid.uuid4())
    end_ts = time.time() + seconds
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO timers (id, user_id, type, label, end_ts) VALUES (?, ?, ?, ?, ?)",
              (tid, user_id, ttype, label, end_ts))
    conn.commit()
    conn.close()
    return tid


def get_timers(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, type, label, end_ts FROM timers WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def remove_timer(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM timers WHERE id=?", (tid,))
    conn.commit()
    conn.close()

# -----------------------
# Utility functions
# -----------------------

def bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None
    h_m = height_cm / 100.0
    return weight_kg / (h_m * h_m)


def generate_meal_plan(height_cm, weight_kg, allergies, goal='maintain'):
    # Very simple calorie estimate (Mifflin-St Jeor would be more accurate)
    b = bmi(weight_kg, height_cm)
    if b is None:
        return None
    # base calorie by BMI roughness
    if b < 18.5:
        cal = 2200
    elif b < 25:
        cal = 2000
    elif b < 30:
        cal = 1800
    else:
        cal = 1600

    if goal == 'lose':
        cal -= 300
    elif goal == 'gain':
        cal += 300

    # Simple macro split
    protein_g = int(0.25 * cal / 4)
    fats_g = int(0.25 * cal / 9)
    carbs_g = int(0.5 * cal / 4)

    # Create a 3-meal sample plan, filter out allergies
    meal_templates = [
        {
            'name': 'Breakfast',
            'items': ['Oatmeal', 'Banana', 'Eggs', 'Yogurt']
        },
        {
            'name': 'Lunch',
            'items': ['Grilled Chicken', 'Brown Rice', 'Steamed Vegetables', 'Salad']
        },
        {
            'name': 'Dinner',
            'items': ['Baked Fish', 'Quinoa', 'Roasted Veggies', 'Green Salad']
        }
    ]

    # allergy filter: if an allergy keyword appears in item, remove that item
    filtered = []
    allergy_keys = [a.strip().lower() for a in (allergies or []) if a.strip()]
    for meal in meal_templates:
        items = []
        for it in meal['items']:
            low = it.lower()
            bad = False
            for a in allergy_keys:
                if a in low or a in it.lower():
                    bad = True
                    break
            if not bad:
                items.append(it)
        if not items:
            items = ['(No suitable item - check allergies)']
        filtered.append({'name': meal['name'], 'items': items})

    return {
        'calories': cal,
        'protein_g': protein_g,
        'fats_g': fats_g,
        'carbs_g': carbs_g,
        'meals': filtered
    }

# -----------------------
# Streamlit UI
# -----------------------

st.set_page_config(page_title='VitalSync Pro (Prototype)', layout='wide')
init_db()

if 'user' not in st.session_state:
    st.session_state['user'] = None

st.title('VitalSync Pro — Health App Prototype')

# -----------------------
# Authentication (simulated for prototype)
# -----------------------
with st.expander('Sign in / Register'):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader('Sign in (simulated)')
        email = st.text_input('Email', key='email')
        name = st.text_input('Name', key='name')
        if st.button('Register / Sign in'):
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
            user = get_user(uid)
            if user is None:
                # create default
                st.session_state.user = {
                    'id': uid,
                    'name': name or 'User',
                    'email': email,
                    'package': 'Free',
                    'height_cm': None,
                    'weight_kg': None,
                    'allergies': []
                }
                save_user(st.session_state.user)
            else:
                # load from DB
                st.session_state.user = {
                    'id': user[0],
                    'name': user[1],
                    'email': user[2],
                    'package': user[3] or 'Free',
                    'height_cm': user[4],
                    'weight_kg': user[5],
                    'allergies': (user[6].split(',') if user[6] else [])
                }
            st.success('Signed in as ' + st.session_state.user['email'])
    with col2:
        st.subheader('OAuth Providers (simulated)')
        st.write('Real OAuth requires app credentials; this prototype simulates sign-in.')
        if st.button('Sign in with Google'):
            email = 'user_google@example.com'
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
            st.session_state.user = {'id': uid, 'name': 'Google User', 'email': email, 'package': 'Free', 'height_cm': None, 'weight_kg': None, 'allergies': []}
            save_user(st.session_state.user)
            st.success('Signed in with Google: ' + email)
        if st.button('Sign in with Apple'):
            email = 'user_apple@example.com'
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
            st.session_state.user = {'id': uid, 'name': 'Apple User', 'email': email, 'package': 'Free', 'height_cm': None, 'weight_kg': None, 'allergies': []}
            save_user(st.session_state.user)
            st.success('Signed in with Apple: ' + email)

if not st.session_state.user:
    st.info('Please sign in or register in the box above to continue.')
    st.stop()

user = st.session_state.user

# -----------------------
# Sidebar - Profile & Package
# -----------------------
with st.sidebar:
    st.header('Profile')
    st.write('Name:', user['name'])
    st.write('Email:', user['email'])
    package = st.selectbox('Choose package', ['Free', 'Premium', 'Pro'], index=['Free', 'Premium', 'Pro'].index(user.get('package', 'Free')))
    if st.button('Save Package'):
        user['package'] = package
        save_user(user)
        st.success('Package saved: ' + package)

    st.markdown('---')
    st.subheader('Order Watch')
    watch_items = {
        'VitalSync Band v1': 49.99,
        'VitalSync Watch Pro': 129.99
    }
    choice = st.selectbox('Choose watch', list(watch_items.keys()))
    qty = st.number_input('Quantity', min_value=1, value=1)
    if st.button('Order Watch'):
        price = watch_items[choice] * qty
        oid = add_order(user['id'], f"{choice} x{qty}", price)
        st.success(f'Order placed (mock). Order ID: {oid} — ${price:.2f}.')

    st.markdown('---')
    st.subheader('Timers')
    ttype = st.selectbox('Timer type', ['Meal', 'Hydration', 'Medication', 'Workout'])
    tlabel = st.text_input('Label', value=f'{ttype} reminder')
    minutes = st.number_input('Minutes from now', min_value=1, value=60)
    if st.button('Start Timer'):
        tid = add_timer(user['id'], ttype, tlabel, minutes * 60)
        st.success('Timer started. ID: ' + tid)

# -----------------------
# Main - Dashboard and settings
# -----------------------
st.header('Dashboard')
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader('Health Inputs')
    with st.form('health_form'):
        height = st.number_input('Height (cm)', min_value=50.0, max_value=300.0, value=user.get('height_cm') or 170.0)
        weight = st.number_input('Weight (kg)', min_value=20.0, max_value=500.0, value=user.get('weight_kg') or 70.0)
        age = st.number_input('Age', min_value=5, max_value=120, value=30)
        activity = st.selectbox('Activity Level', ['Sedentary', 'Light', 'Moderate', 'Active'])
        goal = st.selectbox('Goal', ['maintain', 'lose', 'gain'])
        allergies_input = st.text_input('Allergies / Dietary restrictions (comma separated)', value=','.join(user.get('allergies', [])))
        submitted = st.form_submit_button('Save & Generate Meal Plan')
        if submitted:
            user['height_cm'] = float(height)
            user['weight_kg'] = float(weight)
            user['allergies'] = [a.strip() for a in allergies_input.split(',') if a.strip()]
            save_user(user)
            st.success('Profile saved. Generating meal plan...')

    # Meal plan display
    if user.get('height_cm') and user.get('weight_kg'):
        plan = generate_meal_plan(user['height_cm'], user['weight_kg'], user.get('allergies', []), goal=goal)
        if plan:
            st.subheader('Personalized Meal Plan (Sample)')
            st.write(f"Estimated daily calories: {plan['calories']} kcal — Protein: {plan['protein_g']}g — Carbs: {plan['carbs_g']}g — Fats: {plan['fats_g']}g")
            for m in plan['meals']:
                st.markdown(f"**{m['name']}**")
                for it in m['items']:
                    st.write('- ' + it)
    else:
        st.info('Enter height and weight to get a personalized meal plan.')

    st.markdown('---')
    st.subheader('Workout Timer (Embedded)')
    st.write('Simple workout timer that counts down (runs while the page is open).')
    if 'workout_end' not in st.session_state:
        st.session_state['workout_end'] = None
    w_minutes = st.number_input('Workout minutes', min_value=1, max_value=180, value=20)
    if st.button('Start Workout Timer (page must remain open)'):
        st.session_state['workout_end'] = time.time() + w_minutes * 60
    if st.session_state['workout_end']:
        rem = int(st.session_state['workout_end'] - time.time())
        if rem > 0:
            st.info(f'Workout time remaining: {timedelta(seconds=rem)}')
        else:
            st.success('Workout complete!')
            st.session_state['workout_end'] = None

with col2:
    st.subheader('Active Timers')
    timers = get_timers(user['id'])
    if not timers:
        st.write('No active timers.')
    else:
        for t in timers:
            tid, ttype, label, end_ts = t
            rem = int(end_ts - time.time())
            if rem > 0:
                st.write(f"[{ttype}] {label} — remaining: {timedelta(seconds=rem)}")
                if st.button(f'Cancel {label}', key='cancel_'+tid):
                    remove_timer(tid)
                    st.experimental_rerun()
            else:
                st.warning(f'[{ttype}] {label} — READY (click to remove)')
                if st.button(f'Remove {label}', key='remove_'+tid):
                    remove_timer(tid)
                    st.experimental_rerun()

    st.markdown('---')
    st.subheader('Orders')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, product, price, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC', (user['id'],))
    orders = c.fetchall()
    conn.close()
    if not orders:
        st.write('No orders yet.')
    else:
        for o in orders:
            st.write(f'Order {o[0]} — {o[1]} — ${o[2]:.2f} — {o[3]}')

st.markdown('---')
st.caption('This prototype is for demonstration. Implement real OAuth, payment gateways, and wearable SDKs for production.')
