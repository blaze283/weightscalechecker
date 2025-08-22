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
        return "Underweight", "🟦"
    elif bmi < 25:
        return "Normal weight", "🟩"
    elif bmi < 30:
        return "Overweight", "🟨"
    else:
        return "Obese", "🟥"

def get_diet_plan(category):
    plans = {
        "Underweight": "🍽️ Eat high-calorie nutritious foods. Add protein shakes and 5–6 meals/day.",
        "Normal weight": "🥗 Balanced diet with fruits, veggies, protein. Keep active.",
        "Overweight": "🥦 Low-calorie, high-fiber foods. Cut sugar and carbs.",
        "Obese": "🥬 Focus on veggies, lean protein, whole grains. Consult a doctor."
    }
    return plans.get(category, "⚠️ No plan available.")

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

    bg_image = st.file_uploader("Upload a background", type=["png", "jpg", "jpeg"])
    if bg_image:
        set_background(bg_image)

    unit = st.radio("Select Unit", ["Kilograms", "Pounds"])
    weight = st.number_input(f"Enter weight ({unit})", step=0.1)
    height = st.number_input("Enter height (m)", step=0.01)

    if height > 0 and weight > 0:
        if unit == "Pounds":
            weight *= 0.453592
        bmi = weight / (height ** 2)
        category, emoji = get_bmi_category(bmi)
        st.success(f"{emoji} BMI: {bmi:.1f} ({category})")
        st.info(get_diet_plan(category))

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


