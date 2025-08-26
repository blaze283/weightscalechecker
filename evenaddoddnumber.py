import streamlit as st
import requests
import time
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="FF Bodybuilding",
    layout="wide",
    page_icon="💪"
)

# ---------------- LOAD API KEYS ----------------
try:
    YOUTUBE_API_KEY = st.secrets["general"]["YOUTUBE_API_KEY"]
except Exception:
    YOUTUBE_API_KEY = None
    st.warning("⚠️ Add your YouTube API key in .streamlit/secrets.toml")

# ---------------- SESSION STATE ----------------
if "page" not in st.session_state:
    st.session_state.page = "Login"
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "progress" not in st.session_state:
    st.session_state.progress = []

# ---------------- THEMES ----------------
LIGHT_THEME = {
    "bg": "#ffffff",
    "text": "#000000",
    "input_bg": "#f0f0f0"
}
DARK_THEME = {
    "bg": "#121212",
    "text": "#ffffff",
    "input_bg": "#333333"
}

def get_theme():
    return DARK_THEME if st.session_state.theme == "dark" else LIGHT_THEME

# ---------------- YOUTUBE VIDEO FETCH ----------------
def get_youtube_videos(query, max_results=5):
    if not YOUTUBE_API_KEY:
        return []
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&q={query}&type=video"
        f"&maxResults={max_results}&key={YOUTUBE_API_KEY}"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return [
            {
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            }
            for item in data["items"]
        ]
    else:
        st.error("❌ Could not fetch videos.")
        return []

# ---------------- BMI FUNCTION ----------------
def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight", "🟦"
    elif bmi < 25:
        return "Normal", "🟩"
    elif bmi < 30:
        return "Overweight", "🟨"
    else:
        return "Obese", "🟥"

# ---------------- LOGIN PAGE ----------------
def login_page():
    theme = get_theme()
    st.markdown(
        f"<div style='background:{theme['bg']};color:{theme['text']};padding:2em;border-radius:12px;'>"
        "<h2>🔑 Login</h2>", unsafe_allow_html=True)

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login"):
        if username and password:
            st.session_state.page = "Home"
        else:
            st.error("Enter username and password")

    if st.button("Sign up"):
        st.session_state.page = "Signup"

# ---------------- SIGNUP PAGE ----------------
def signup_page():
    st.title("📝 Sign Up")
    new_user = st.text_input("Create username")
    new_pass = st.text_input("Create password", type="password")
    if st.button("Register"):
        if new_user and new_pass:
            st.session_state.page = "Home"
            st.success("✅ Account created! Redirecting...")
        else:
            st.error("Please enter valid details")

# ---------------- HOME PAGE ----------------
def home_page():
    theme = get_theme()
    st.markdown(
        f"<div style='background:{theme['bg']};color:{theme['text']};padding:1em;'>"
        "<h1>💪 FF Bodybuilding</h1></div>", unsafe_allow_html=True)

    # Navigation
    choice = st.sidebar.radio("Navigate", ["🏠 Home", "📊 BMI Calculator", "🎥 Workouts", "📈 Progress"])
    st.sidebar.button("🌙 Toggle Theme", on_click=lambda: st.session_state.update(
        theme="dark" if st.session_state.theme == "light" else "light"))

    if choice == "🏠 Home":
        st.subheader("Welcome to your fitness app! 🏋️")
        st.write("Track workouts, calculate BMI, watch training videos, and monitor your progress.")

    elif choice == "📊 BMI Calculator":
        st.subheader("📊 BMI Calculator")
        weight = st.number_input("Enter your weight (kg)", min_value=1.0, step=0.5)
        feet = st.number_input("Height (feet)", min_value=1, max_value=8, step=1)
        inches = st.number_input("Height (inches)", min_value=0, max_value=11, step=1)
        height_m = (feet * 12 + inches) * 0.0254

        if st.button("Calculate BMI"):
            bmi = weight / (height_m ** 2)
            cat, emoji = get_bmi_category(bmi)
            st.success(f"Your BMI: {bmi:.2f} → {cat} {emoji}")
            st.session_state.progress.append({"BMI": bmi, "Category": cat})

    elif choice == "🎥 Workouts":
        st.subheader("🎥 Workout Videos")
        query = st.text_input("Search workouts:", "push up workout")
        if query:
            videos = get_youtube_videos(query)
            for v in videos:
                st.write(f"🎬 {v['title']}")
                st.video(v["url"])

        st.subheader("⏱️ Workout Timer")
        duration = st.number_input("Set timer (seconds)", 10, 300, 30)
        if st.button("Start Timer"):
            for i in range(duration, 0, -1):
                st.write(f"⏱️ {i} seconds left")
                time.sleep(1)
                st.experimental_rerun()

    elif choice == "📈 Progress":
        st.subheader("📈 Progress Tracking")
        if st.session_state.progress:
            df = pd.DataFrame(st.session_state.progress)
            st.dataframe(df)

            plt.plot(df["BMI"], marker="o")
            plt.title("BMI Progress")
            st.pyplot(plt)
        else:
            st.info("No progress yet. Calculate your BMI first.")

# ---------------- APP FLOW ----------------
if st.session_state.page == "Login":
    login_page()
elif st.session_state.page == "Signup":
    signup_page()
else:
    home_page()
