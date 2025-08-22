import streamlit as st
import base64
import sqlite3
import mimetypes

# ------------------- CONFIG -------------------
st.set_page_config(page_title="BMI & Diet App", layout="centered")

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

# ------------------- BMI + DIET -------------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight", "🟦", "background-color:#d0e7ff;", "🍽️ Eat high-calorie nutritious foods. Add protein shakes and 5–6 meals/day."
    elif bmi < 25:
        return "Normal weight", "🟩", "background-color:#d6f5d6;", "🥗 Balanced diet with fruits, veggies, protein. Keep active."
    elif bmi < 30:
        return "Overweight", "🟨", "background-color:#fff5cc;", "🥦 Low-calorie, high-fiber foods. Cut sugar and carbs."
    else:
        return "Obese", "🟥", "background-color:#ffd6cc;", "🥬 Focus on veggies, lean protein, whole grains. Consult a doctor."

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

    # Weight input
    unit = st.radio("Select Weight Unit", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter weight ({unit})", step=0.1)

    # Height input in Feet & Inches
    st.markdown("📏 Enter Your Height")
    col1, col2 = st.columns(2)
    with col1:
        feet = st.number_input("Feet", min_value=1, max_value=8, step=1, value=5)
    with col2:
        inches = st.number_input("Inches", min_value=0, max_value=11, step=1, value=7)

    # Convert height to meters
    height_m = (feet * 12 + inches) * 0.0254

    # BMI Calculation
    if height_m > 0 and weight > 0:
        weight_kg = weight if unit == "Kilograms" else weight * 0.453592
        bmi = weight_kg / (height_m ** 2)
        category, emoji, style, diet_plan = get_bmi_category(bmi)

        st.markdown(
            f'<div class="result-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>',
            unsafe_allow_html=True
        )

        # Show Diet Plan
        st.markdown(f"""
        <div class="info-card" style="text-align:left;">
        🍽️ <b>Suggested Diet Plan:</b><br>
        <pre style="white-space: pre-wrap; font-size:16px;">{diet_plan}</pre>
        </div>
        """, unsafe_allow_html=True)

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
