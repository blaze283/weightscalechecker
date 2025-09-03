import streamlit as st
import base64
import mimetypes

# Page configuration
st.set_page_config(
    page_title="Weight Converter",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for enhanced styling
def inject_custom_css():
    st.markdown("""
    <style>
    .main-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        color: white;
        text-align: center;
        margin: 20px 0;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .result-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        color: white;
        text-align: center;
        margin: 15px 0;
        font-weight: 600;
    }
    .info-card {
        background: rgba(255,255,255,0.95);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 10px 0;
        border-left: 4px solid #667eea;
    }
    .title-header {
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4, #45b7d1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 30px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .upload-section {
        background: rgba(248,249,250,0.9);
        padding: 20px;
        border-radius: 12px;
        border: 2px dashed #dee2e6;
        margin: 20px 0;
        text-align: center;
    }
    .stSelectbox > div > div {
        background: white;
        border-radius: 8px;
        border: 2px solid #e9ecef;
        font-size: 18px !important;
    }
    .stNumberInput > div > div > input {
        background: white;
        border-radius: 8px;
        border: 2px solid #e9ecef;
        font-size: 18px !important;
        text-align: center;
    }
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animated-result {
        animation: slideIn 0.5s ease-out;
    }
    </style>
    """, unsafe_allow_html=True)

# Enhanced background application
def apply_background(bg_image):
    if bg_image is not None:
        mime_type, _ = mimetypes.guess_type(bg_image.name)
        encoded_image = base64.b64encode(bg_image.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)), 
                             url("data:{mime_type};base64,{encoded_image}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .info-card, .upload-section {{
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
        }}
        </style>
        """, unsafe_allow_html=True)

# Conversion functions
def kg_to_lbs(kg):
    return kg * 2.20462

def lbs_to_kg(lbs):
    return lbs * 0.453592

# BMI category helper
def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight", "🔵"
    elif 18.5 <= bmi < 25:
        return "Normal weight", "🟢"
    elif 25 <= bmi < 30:
        return "Overweight", "🟡"
    else:
        return "Obese", "🔴"

# Main app
def main():
    inject_custom_css()
    
    # Title
    st.markdown('<h1 class="title-header">⚖️ Weight Scale Converter ⚖️</h1>', unsafe_allow_html=True)
    
    # Background image upload
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.markdown("### 🖼️ Customize Your Experience")
    bg_image = st.file_uploader(
        "Upload a background image to personalize your converter",
        type=["jpg", "jpeg", "png"],
        help="Choose a beautiful background image to make the app your own!"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    apply_background(bg_image)
    
    # Input section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("### 📏 Select Unit")
        unit = st.selectbox("", ["Kilograms (kg)", "Pounds (lbs)"], key="unit")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("### 🔢 Enter Weight")
        weight = st.number_input(
            "", 
            min_value=0.1, 
            max_value=999.9, 
            step=0.1, 
            format="%.1f",
            key="weight"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Conversion and results
    if weight > 0:
        st.markdown('<div class="animated-result">', unsafe_allow_html=True)
        
        if "Kilograms" in unit:
            converted_weight = kg_to_lbs(weight)
            st.markdown(f'''
            <div class="result-card">
                <h2>🎯 Conversion Result</h2>
                <h1>{weight:.1f} kg = {converted_weight:.1f} lbs</h1>
            </div>
            ''', unsafe_allow_html=True)
            
            # Additional metrics
            stones = converted_weight / 14
            ounces = converted_weight * 16  # fixed to total ounces
            
            col3, col4, col5 = st.columns(3)
            with col3:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>🪨 Stones</h3>
                    <h2>{stones:.1f}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col4:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>⚖️ Ounces</h3>
                    <h2>{ounces:.0f}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col5:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>📊 Grams</h3>
                    <h2>{weight * 1000:.0f}</h2>
                </div>
                ''', unsafe_allow_html=True)
                
        else:  # Pounds
            converted_weight = lbs_to_kg(weight)
            st.markdown(f'''
            <div class="result-card">
                <h2>🎯 Conversion Result</h2>
                <h1>{weight:.1f} lbs = {converted_weight:.1f} kg</h1>
            </div>
            ''', unsafe_allow_html=True)
            
            # Additional metrics
            stones = weight / 14
            ounces = weight * 16
            
            col3, col4, col5 = st.columns(3)
            with col3:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>🪨 Stones</h3>
                    <h2>{stones:.1f}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col4:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>⚖️ Ounces</h3>
                    <h2>{ounces:.0f}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col5:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>📊 Grams</h3>
                    <h2>{converted_weight * 1000:.0f}</h2>
                </div>
                ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Bonus BMI Calculator
        st.markdown("---")
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("### 🧮 Bonus: Quick BMI Calculator")
        height = st.number_input(
            "Enter your height in meters (optional)", 
            min_value=0.5, 
            max_value=3.0, 
            step=0.01, 
            value=1.70,  # fixed default
            format="%.2f"
        )
        
        if height > 0:
            weight_kg = weight if "Kilograms" in unit else converted_weight
            bmi = weight_kg / (height ** 2)
            category, emoji = get_bmi_category(bmi)
            
            st.markdown(f'''
            <div class="result-card">
                <h3>{emoji} BMI: {bmi:.1f}</h3>
                <p>Category: {category}</p>
            </div>
            ''', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.markdown('''
        <div class="info-card">
            <h3>👆 Enter your weight above to see conversions!</h3>
            <p>This converter supports:</p>
            <ul>
                <li>🔄 Kg ↔ Lbs conversion</li>
                <li>📏 Additional units (stones, ounces, grams)</li>
                <li>🧮 BMI calculation</li>
                <li>🎨 Custom backgrounds</li>
            </ul>
        </div>
        ''', unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown('''
    <div style="text-align: center; color: #666; margin-top: 30px;">
        <p>💪 <strong>Stay healthy and keep tracking!</strong> 💪</p>
        <p><small>Made with ❤️ using Streamlit</small></p>
    </div>
    ''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
