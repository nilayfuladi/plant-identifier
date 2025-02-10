import streamlit as st
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os
import base64
from io import BytesIO
import time
import random
import asyncio

# Load environment variables (including API key)
load_dotenv()

# Configure the Streamlit page
st.set_page_config(page_title="Plant Identifier", page_icon="🌿", layout="wide")

# Define the CSS styles for the application
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
    }
    .stButton>button {
        width: auto;
        min-width: 200px;
        margin: 0 auto;
        display: block;
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem;
        border-radius: 5px;
        font-size: 1rem;
    }
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
        margin-bottom: 1rem;
    }
    .progress-text {
        margin-top: 0.5rem;
        font-weight: bold;
        color: #4CAF50;
    }
    .info-box {
        background-color: #2b2b2b;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .loading-box {
        background-color: #1e1e1e;
        border: 1px solid #4a4a4a;
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
        text-align: center;
        width: 100%;
    }
    .plant-name {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .tab-content {
        padding: 1rem;
        border-radius: 0 0 10px 10px;
    }
    .preview-image {
        border: 2px solid #4CAF50;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 20px;
    }
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
        }
        .info-box, .loading-box {
            padding: 0.75rem;
        }
    }
</style>
""", unsafe_allow_html=True)

def get_fun_loading_messages():
    """
    Return a list of fun, engaging loading messages.
    These messages add humor and personality to the loading process.
    """
    return [
        "Your plants don't need therapy, just proper drainage. But they'll still appreciate you talking to them! 🌿 💭",
        "Science says talking to plants helps them grow. But maybe skip the gossip – these walls have leaves. 🤫 🌱",
        "Did you know plants can get sunburned? Even they need SPF (Shade Protection Factor) sometimes! ☀️ 🌿",
        "Relationship status with my monstera: It's complicated. They asked for indirect light, then called me toxic for moving them away from the window. 💔 🪴",
        "Overwatering is like overthinking – it drowns the potential. Let your plants and thoughts breathe a little. 💧 ✨",
        "Missing your plant's watering schedule is like missing a text from your mom – they'll forgive you, but you'll never hear the end of it. 📱 🌵"
    ]

def initialize_gemini():
    """
    Initialize the Gemini AI model with error handling.
    Ensures secure API key configuration and model initialization.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        st.error("⚠️ Please set your Google API key in the .env file")
        st.stop()
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"⚠️ Error initializing AI model: {str(e)}")
        return None

def prepare_image(image):
    """
    Optimize image for AI processing by resizing and encoding.
    Reduces image size and converts to compatible format.
    """
    try:
        max_size = 300  # Optimal size for faster processing
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.LANCZOS)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=50)  # Reduced quality for smaller file size
        image_bytes = buffered.getvalue()
        
        return {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(image_bytes).decode('utf-8')
        }
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def get_plant_info_prompt():
    """
    Generate a structured prompt for AI to analyze plant images.
    Provides clear instructions for detailed plant information.
    """
    return """
    Analyze the provided plant image and give the following information:
    1. Common Name: Provide the most widely recognized common name for this plant.
    2. Hindi Name: If there's a commonly used Hindi name, provide it. If not, state that there isn't a widely accepted Hindi name.
    3. Seasonal Care Tips: Provide 2-3 specific care tips for each season (Spring, Summer, Monsoon, Winter). 
       If a tip doesn't apply to a particular season, provide a general care tip instead.
    
    Format your response like this:
    Common Name: [Plant's common name]
    Hindi Name: [Hindi name or statement about lack of common Hindi name]
    
    Spring Care:
    • [Tip 1]
    • [Tip 2]
    • [Tip 3]
    
    Summer Care:
    • [Tip 1]
    • [Tip 2]
    • [Tip 3]
    
    Monsoon Care:
    • [Tip 1]
    • [Tip 2]
    • [Tip 3]
    
    Winter Care:
    • [Tip 1]
    • [Tip 2]
    • [Tip 3]
    """

def process_gemini_response(response_text):
    """
    Parse and structure the AI's response into a consistent format.
    Handles variations in AI response and extracts key plant information.
    """
    plant_info = {
        'common_name': 'Unknown',
        'hindi_name': 'Not available',
        'care_instructions': {
            'Spring': [], 'Summer': [], 'Monsoon': [], 'Winter': []
        }
    }

    current_section = None
    for line in response_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith('common name:'):
            plant_info['common_name'] = line.split(':', 1)[1].strip()
        elif any(phrase in line.lower() for phrase in ['hindi name:', 'hindi:', 'in hindi:']):
            hindi_name = line.split(':', 1)[1].strip()
            if hindi_name.lower() not in ['unknown', 'not available', 'n/a', '']:
                plant_info['hindi_name'] = hindi_name
        elif any(line.startswith(f"{season} Care:") for season in plant_info['care_instructions']):
            current_section = line.split(':')[0].strip().split()[0]
        elif current_section and line.startswith('•'):
            plant_info['care_instructions'][current_section].append(line.lstrip('• ').strip())

    return plant_info

def display_plant_info(plant_info):
    """
    Create a visually appealing display of plant identification results.
    Shows common name, Hindi name, and seasonal care tips.
    """
    st.markdown("### 🌱 Plant Identification Results")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="info-box">
                <div class="plant-name">Common Name</div>
                {plant_info['common_name']}
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""
            <div class="info-box">
                <div class="plant-name">Hindi Name</div>
                {plant_info['hindi_name']}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("### 🌿 Seasonal Care Tips")
    tabs = st.tabs(['Spring', 'Summer', 'Monsoon', 'Winter'])
    for tab, season in zip(tabs, ['Spring', 'Summer', 'Monsoon', 'Winter']):
        with tab:
            tips = plant_info['care_instructions'][season]
            if tips:
                st.markdown('<div class="tab-content">', unsafe_allow_html=True)
                for tip in tips:
                    st.markdown(f"• {tip}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="tab-content">No specific care tips available for this season. Adjust care based on your local climate conditions.</div>', unsafe_allow_html=True)

async def process_plant_image(model, image_data, prompt):
    """
    Asynchronously process the plant image using the AI model.
    Allows non-blocking execution of AI analysis.
    """
    response = await model.generate_content_async(
        [prompt, image_data],
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 300,
            "top_p": 0.8,
            "top_k": 40
        }
    )
    return response

def main():
    """
    Main function to orchestrate the Streamlit plant identification application.
    Manages the entire workflow from image upload to plant identification.
    """
    st.markdown("""
    <h1 style='text-align: center;'>🌿 Plant Identifier</h1>
    <p style='text-align: center;'>Upload a plant photo to get identification and care tips!</p>
    """, unsafe_allow_html=True)

    # Initialize fun loading messages
    if 'messages' not in st.session_state:
        st.session_state.messages = get_fun_loading_messages()

    # Initialize Gemini AI model
    model = initialize_gemini()
    if not model:
        st.error("Could not initialize AI model. Please check your configuration.")
        st.stop()

    # Image upload
    uploaded_file = st.file_uploader("Choose a plant image", type=['png', 'jpg', 'jpeg'])

    if uploaded_file:
        image = Image.open(uploaded_file)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown('<div class="preview-image">', unsafe_allow_html=True)
            st.image(image, caption="Uploaded Plant Image", use_container_width=True, width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        if st.button("Identify Plant"):
            # Create containers for loading and progress
            loading_container = st.empty()
            progress_text = st.empty()
            progress_bar = st.progress(0)
            loading_placeholder = st.empty()

            try:
                # Prepare image and show initial loading message
                loading_placeholder.markdown(
                    f'<div class="loading-box">{random.choice(st.session_state.messages)}</div>', 
                    unsafe_allow_html=True
                )
                
                # Function to update progress
                def update_progress(percentage):
                    progress_bar.progress(percentage)
                    progress_text.markdown(
                        f'<div class="progress-text">Progress: {percentage}%</div>', 
                        unsafe_allow_html=True
                    )

                # Image processing
                image_data = prepare_image(image)
                if not image_data:
                    st.error("Image preparation failed")
                    st.stop()
                update_progress(25)

                # Prepare for AI processing
                loading_placeholder.markdown(
                    f'<div class="loading-box">{random.choice(st.session_state.messages)}</div>', 
                    unsafe_allow_html=True
                )
                update_progress(50)

                # Run AI analysis
                with st.spinner("Analyzing plant..."):
                    response = asyncio.run(process_plant_image(model, image_data, get_plant_info_prompt()))

                update_progress(75)

                # Process AI response
                loading_placeholder.markdown(
                    f'<div class="loading-box">{random.choice(st.session_state.messages)}</div>', 
                    unsafe_allow_html=True
                )
                
                if response and response.text:
                    plant_info = process_gemini_response(response.text)
                    if plant_info:
                        update_progress(100)
                        time.sleep(0.5)  # Pause for visual feedback
                        
                        # Clear loading elements
                        loading_container.empty()
                        progress_text.empty()
                        loading_placeholder.empty()
                        progress_bar.empty()
                        
                        # Display plant information
                        display_plant_info(plant_info)
                    else:
                        st.error("Could not interpret plant information")
                else:
                    st.error("No response received from AI")

            except Exception as e:
                st.error(f"Error during plant identification: {str(e)}")

if __name__ == "__main__":
    main()