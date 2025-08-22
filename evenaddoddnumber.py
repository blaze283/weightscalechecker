import streamlit as st
import base64
import sqlite3
import mimetypes
import datetime
import pandas as pd

# ------------------- CONFIG -------------------
st.set_page_config(page_title="BMI, Diet & Workout App", layout="centered")

# ------------------- DATABASE -------------------
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TEXT,
            weight REAL
        )
    """)
    conn.commit()
    conn.close()

def add_user(username, password):
    try:
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user(username, password):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()
    conn.close()
    return user

def add_progress(username, date, weight):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO progress (username, date, weight) VALUES (?, ?, ?)", (username, date, weight))
    conn.commit()
    conn.close()

def get_progress(username):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT date, weight FROM progress WHERE username=? ORDER BY date", (username,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ------------------- BACKGROUND -------------------
def set_background(uploaded_file):
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    encoded = base64.b64encode(uploaded_file.getvalue()).decode()
    page_bg = f"""
    <style>
    .stApp {{
        background-image: url("data:{mime_type};base64,{encoded}");
        background-size: cover;
    }}
    </style>
    """
    st.markdown(page_bg, unsafe_allow_html=True)

# ------------------- TEXT BACKGROUND CSS -------------------
def apply_text_background():
    st.markdown("""
        <style>
        /* Give all text a background */
        h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stText, .stRadio, .stSelectbox, .stDateInput, .stNumberInput, .stButton, .stDataFrame, .stTable {{
            background-color: rgba(255, 255, 255, 0.8); 
            padding: 6px 10px;
            border-radius: 6px;
        }}
        </style>
    """, unsafe_allow_html=True)

# ------------------- BMI + HEALTH ADVICE -------------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return (
            "Underweight", "🟦", "background-color:#d0e7ff;",
            "🍽️ Eat calorie-dense foods.\n🥛 Drink milk/protein shakes.\n🍗 Add lean meats & eggs.\n🥑 Include avocados & nuts.",
            "🏋️ Strength training.\n🚶 Light walks.\n🤸 Yoga.\n🛑 Avoid excess cardio."
        )
    elif bmi < 25:
        return (
            "Normal weight", "🟩", "background-color:#d6f5d6;",
            "🥗 Balanced diet.\n🍗 Steady protein intake.\n💧 Drink water.\n🏃‍♂️ Daily exercise.",
            "🏃 Jog/cycle.\n🏋️ Mix cardio + strength.\n🧘 Stretch or yoga.\n⚽ Play sports."
        )
    elif bmi < 30:
        return (
            "Overweight", "🟨", "background-color:#fff5cc;",
            "🥦 High-fiber diet.\n🍵 Replace soda with water/tea.\n🍞 Whole grains.\n🚶 Walk daily.",
            "🚶 Walk 30–60 min.\n🚴 Cycle/swim.\n🏋️ Light weights.\n🤸 Stretching."
        )
    else:
        return (
            "Obese", "🟥", "background-color:#ffd6cc;",
            "🥬 Eat veggies & lean protein.\n🍭 Avoid sugary drinks.\n🚴 Be active most days.\n📉 Gradual weight loss.",
            "🚶 Start short walks.\n🧘 Gentle yoga.\n🏊 Swimming.\n🚴 Stationary cycling."
        )

# ------------------- PAGES -------------------
def signup_page():
    st.subheader("Sign Up")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if username and password:
            if add_user(username, password):
                st.success("✅ Account created! Please login.")
                st.session_state.page = "login"
            else:
                st.error("⚠️ Username already exists.")
        else:
            st.warning("⚠️ Enter both fields.")

def login_page():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = get_user(username, password)
        if user:
            st.session_state.user = username
            st.session_state.page = "app"
        else:
            st.error("❌ Invalid username or password.")
    if st.button("Go to Sign Up"):
        st.session_state.page = "signup"

def app_page():
    st.subheader(f"Welcome {st.session_state.user}! 🎉")

    # Background upload
    bg_image = st.file_uploader("Upload a background", type=["png", "jpg", "jpeg"])
    if bg_image:
        set_background(bg_image)

    # Apply text background
    apply_text_background()

    # Weight + Height
    unit = st.radio("Select Weight Unit", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter weight ({unit})", step=0.1)

    st.markdown("📏 Enter Your Height")
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

        st.markdown(
            f'<div style="{style}; padding:10px; border-radius:6px;">{emoji} BMI: {bmi:.1f} ({category})</div>',
            unsafe_allow_html=True
        )

        st.markdown(f"🍽️ **Diet Tips:**\n\n{diet_tips}")
        st.markdown(f"🏋️ **Workout Tips:**\n\n{workout_tips}")

    # Progress Tracker
    st.subheader("📈 Progress Tracker")
    prog_col1, prog_col2 = st.columns(2)
    with prog_col1:
        prog_date = st.date_input("Date", datetime.date.today())
    with prog_col2:
        prog_weight = st.number_input("Weight (kg)", step=0.1)

    if st.button("Add Progress"):
        if prog_weight > 0:
            add_progress(st.session_state.user, str(prog_date), prog_weight)
            st.success("✅ Progress saved!")

    progress = get_progress(st.session_state.user)
    if progress:
        df = pd.DataFrame(progress, columns=["Date", "Weight"])
        df["Date"] = pd.to_datetime(df["Date"])

        # Filtering
        st.markdown("🔍 **Filter Progress by Month/Year**")
        years = df["Date"].dt.year.unique()
        months = list(range(1, 13))

        col1, col2 = st.columns(2)
        with col1:
            year_filter = st.selectbox("Select Year", options=["All"] + list(years))
        with col2:
            month_filter = st.selectbox("Select Month", options=["All"] + months)

        filtered_df = df.copy()
        if year_filter != "All":
            filtered_df = filtered_df[filtered_df["Date"].dt.year == year_filter]
        if month_filter != "All":
            filtered_df = filtered_df[filtered_df["Date"].dt.month == month_filter]

        st.write("📊 Progress History")
        st.table(filtered_df)

        if not filtered_df.empty:
            st.line_chart(filtered_df.set_index("Date")["Weight"])

    if st.button("Logout"):
        st.session_state.clear()
        st.session_state.page = "login"

# ------------------- MAIN -------------------
def main():
    init_db()
    if "page" not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.page == "signup":
        signup_page()
    elif st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "app":
        app_page()

if __name__ == "__main__":
    main()
