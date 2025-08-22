import streamlit as st
import base64
import sqlite3

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
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

def get_user(username, password):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()
    conn.close()
    return user

# ------------------- BACKGROUND -------------------
def set_background(encoded_image):
    page_bg = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{encoded_image}");
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
        "Normal weight": "🥗 Maintain a balanced diet (fruits, veggies, protein). Exercise regularly.",
        "Overweight": "🥦 Eat low-calorie, high-fiber foods. Cut sugar and carbs. Stay active.",
        "Obese": "🥬 Focus on veggies, lean protein, whole grains. Avoid junk food and consult a doctor."
    }
    return plans.get(category, "⚠️ No plan available.")

# ------------------- PAGES -------------------
def signup_page():
    st.subheader("Sign Up")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if username and password:
            try:
                add_user(username, password)
                st.success("✅ Account created! Please login.")
                st.session_state.page = "login"
            except:
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

def app_page():
    st.subheader(f"Welcome {st.session_state.user}! 🎉")
    st.write("Upload a background if you like:")
    bg_image = st.file_uploader("Choose image", type=["png", "jpg", "jpeg"])
    if bg_image:
        encoded_image = base64.b64encode(bg_image.getvalue()).decode()
        set_background(encoded_image)

    unit = st.radio("Select Unit", ["Kilograms", "Pounds"], horizontal=True)
    weight = st.number_input(f"Enter weight ({unit})", step=0.1)
    height = st.number_input("Enter height (m)", step=0.01)

    if height > 0 and weight > 0:
        if unit == "Pounds":
            weight = weight * 0.453592  # convert lbs to kg
        bmi = weight / (height ** 2)
        category, emoji = get_bmi_category(bmi)

        st.success(f"{emoji} BMI: {bmi:.1f} ({category})")
        st.info(get_diet_plan(category))

    if st.button("Logout"):
        st.session_state.clear()
        st.session_state.page = "login"

# ------------------- MAIN -------------------
def main():
    st.set_page_config(page_title="BMI & Diet App", layout="centered")
    init_db()

    if "page" not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.page == "signup":
        signup_page()
    elif st.session_state.page == "login":
        login_page()
        if st.button("Go to Sign Up"):
            st.session_state.page = "signup"
    elif st.session_state.page == "app":
        app_page()

if __name__ == "__main__":
    main()
