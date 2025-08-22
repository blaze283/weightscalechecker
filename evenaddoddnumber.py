import streamlit as st
import base64
import mimetypes

# ------------------- PAGE CONFIG -------------------
st.set_page_config(
    page_title="Weight Converter",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ------------------- CUSTOM CSS -------------------
def inject_custom_css():
    st.markdown("""
    <style>
    * {
        font-family: 'Segoe UI', sans-serif;
    }
    .main-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    .metric-card, .result-card, .info-card, .title-header {
        background: rgba(255,255,255,0.85);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        color: black;
    }
    .metric-card {
        text-align: center;
        font-weight: bold;
    }
    .result-card {
        text-align: center;
        font-size: 18px;
        margin: 15px 0;
    }
    .title-header {
        font-size: 2.2rem;
        text-align: center;
        font-weight: bold;
        margin-bottom: 30px;
    }
    .upload-section {
        background: rgba(255,255,255,0.85);
        padding: 20px;
        border-radius: 12px;
        border: 2px dashed #dee2e6;
        margin: 20px 0;
        text-align: center;
    }
    /* Style all number inputs */
    .stNumberInput > div > div > input {
        background: rgba(255,255,255,0.9);
        border-radius: 8px;
        border: 2px solid #ccc;
        font-size: 18px !important;
        text-align: center;
    }
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.9);
        border-radius: 8px;
        border: 2px solid #ccc;
        font-size: 18px !important;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ------------------- BACKGROUND -------------------
def apply_background(bg_image):
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded_image = base64.b64encode(bg_image.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:{mime_type};base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """, unsafe_allow_html=True)

# ------------------- CONVERSIONS -------------------
def kg_to_lbs(kg): return kg * 2.20462
def lbs_to_kg(lbs): return lbs * 0.453592

def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight", "🔵", "background-color: rgba(0, 123, 255, 0.2);"  # Blue
    elif 18.5 <= bmi < 25:
        return "Normal weight", "🟢", "background-color: rgba(40, 167, 69, 0.2);"  # Green
    elif 25 <= bmi < 30:
        return "Overweight", "🟡", "background-color: rgba(255, 193, 7, 0.2);"  # Yellow
    else:
        return "Obese", "🔴", "background-color: rgba(220, 53, 69, 0.2);"  # Red

# ------------------- MAIN APP -------------------
def main():
    inject_custom_css()

    # Title
    st.markdown('<div class="title-header">⚖️ Weight Scale Converter ⚖️</div>', unsafe_allow_html=True)

    # Background uploader
    bg_image = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png"])
    apply_background(bg_image)

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="info-card">📏 Select Unit</div>', unsafe_allow_html=True)
        unit = st.selectbox("", ["Kilograms (kg)", "Pounds (lbs)"], key="unit")

    with col2:
        st.markdown('<div class="info-card">🔢 Enter Weight</div>', unsafe_allow_html=True)
        weight = st.number_input("", min_value=0.1, max_value=999.9, step=0.1, format="%.1f")

    # Results
    if weight > 0:
        if "Kilograms" in unit:
            converted_weight = kg_to_lbs(weight)
            stones = converted_weight / 14
            ounces = converted_weight * 16
            grams = weight * 1000
        else:
            converted_weight = lbs_to_kg(weight)
            stones = weight / 14
            ounces = weight * 16
            grams = converted_weight * 1000

        st.markdown(f'''
        <div class="result-card">
            🎯 Conversion Result:<br><b>{weight:.1f} {unit} = {converted_weight:.1f} {'lbs' if "Kilograms" in unit else 'kg'}</b>
        </div>
        ''', unsafe_allow_html=True)

        col3, col4, col5 = st.columns(3)
        col3.markdown(f'<div class="metric-card">🪨 Stones<br>{stones:.1f}</div>', unsafe_allow_html=True)
        col4.markdown(f'<div class="metric-card">⚖️ Ounces<br>{ounces:.0f}</div>', unsafe_allow_html=True)
        col5.markdown(f'<div class="metric-card">📊 Grams<br>{grams:.0f}</div>', unsafe_allow_html=True)

        # BMI Calculator
        st.markdown('<div class="info-card">🧮 Quick BMI Calculator</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card">📏 Enter Your Height (m)</div>', unsafe_allow_html=True)
        height = st.number_input("", min_value=0.5, max_value=3.0, step=0.01, value=1.70)

        if height > 0:
            weight_kg = weight if "Kilograms" in unit else converted_weight
            bmi = weight_kg / (height ** 2)
            category, emoji, style = get_bmi_category(bmi)
            st.markdown(f'<div class="result-card" style="{style}">{emoji} BMI: {bmi:.1f} ({category})</div>', unsafe_allow_html=True)

    else:
        st.markdown('<div class="info-card">👆 Enter your weight above to see conversions!</div>', unsafe_allow_html=True)

    # Footer
    st.markdown('<div class="info-card" style="text-align:center;">💪 Stay healthy and keep tracking! 💪<br><small>Made with ❤️ using Streamlit</small></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
