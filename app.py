import streamlit as st
import json
import os
import requests
from urllib.parse import quote
from io import BytesIO
from gtts import gTTS
from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Visual Novel Engine",
    page_icon="📖",
    layout="wide"
)


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")


# ============================================================
# CHECK API KEYS
# ============================================================

if not GEMINI_API_KEY:
    st.error("Gemini API key is missing. Check your .env file.")
    st.stop()

if not POLLINATIONS_API_KEY:
    st.error("Pollinations API key is missing. Check your .env file.")
    st.stop()


# ============================================================
# GEMINI CLIENT
# ============================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


client = get_gemini_client()


# ============================================================
# STORY SETTINGS
# ============================================================

st.sidebar.title("🎬 Story Settings")

genre = st.sidebar.selectbox(
    "Story Genre",
    [
        "Fantasy",
        "Mystery",
        "Science Fiction",
        "Adventure",
        "Horror",
        "Romance"
    ]
)

art_style = st.sidebar.selectbox(
    "Art Style",
    [
        "Cinematic digital art",
        "Anime",
        "Fantasy concept art",
        "Watercolor",
        "Comic book",
        "Dark atmospheric"
    ]
)


# ============================================================
# SESSION STATE
# ============================================================

if "story_history" not in st.session_state:
    st.session_state.story_history = []

if "chat" not in st.session_state:
    system_instruction = f"""
You are the story director of an interactive visual novel.

The story genre is: {genre}
The visual art style is: {art_style}

You MUST return ONLY valid JSON.

The JSON object must contain exactly these three keys:

1. story_text
2. image_prompt
3. options

Rules:

- story_text must contain the next part of the story.
- image_prompt must describe the scene for an image generation API.
- options must be a Python-style list containing exactly 3 different choices.
- Each choice must be a short action the player can take.
- Do not use Markdown.
- Do not use ```json.
- Return valid JSON only.

Example format:

{{
    "story_text": "The hero enters the mysterious forest...",
    "image_prompt": "A cinematic fantasy forest at night...",
    "options": [
        "Enter the forest",
        "Follow the glowing path",
        "Return to the village"
    ]
}}
"""

    st.session_state.chat = client.chats.create(
        model="gemini-3.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.8
        )
    )


# ============================================================
# TITLE
# ============================================================

st.title("📖 Multi-Modal Visual Novel")
st.caption("Gemini + Pollinations + gTTS")


# ============================================================
# JSON PARSER
# ============================================================

def parse_json_response(text):
    """
    Converts Gemini's response into a Python dictionary.
    Handles accidental Markdown code fences.
    """

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("Gemini did not return valid JSON.")

    json_text = text[start:end + 1]

    data = json.loads(json_text)

    required_keys = ["story_text", "image_prompt", "options"]

    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing JSON key: {key}")

    if not isinstance(data["options"], list):
        raise ValueError("options must be a list.")

    return data


# ============================================================
# POLLINATIONS IMAGE GENERATION
# ============================================================

def generate_image(image_prompt):
    """
    Sends the image prompt to Pollinations API.
    """

    encoded_prompt = quote(image_prompt)

    url = (
        f"https://gen.pollinations.ai/image/"
        f"{encoded_prompt}?model=flux"
    )

    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {POLLINATIONS_API_KEY}"
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.content

        # Graceful failure
        st.toast(
            "Image server is busy, skipping visual for this scene."
        )

        return None

    except requests.RequestException:
        st.toast(
            "Image server could not be reached. Continuing the story."
        )

        return None


# ============================================================
# TEXT TO SPEECH
# ============================================================

def generate_audio(story_text):
    """
    Converts story text into MP3 audio using gTTS.
    """

    try:
        audio_buffer = BytesIO()

        tts = gTTS(
            text=story_text,
            lang="en"
        )

        tts.write_to_fp(audio_buffer)

        audio_buffer.seek(0)

        return audio_buffer.read()

    except Exception:
        st.toast(
            "Text-to-speech is temporarily unavailable."
        )

        return None


# ============================================================
# GENERATE STORY
# ============================================================

def generate_story(player_choice=None):

    try:

        if player_choice is None:

            first_prompt = f"""
Start a new {genre} interactive visual novel.

Create the opening scene.

Remember:
- Return ONLY valid JSON.
- Include story_text.
- Include image_prompt.
- Include exactly 3 options.
- The art should match: {art_style}.
"""

            response = st.session_state.chat.send_message(
                first_prompt
            )

        else:

            response = st.session_state.chat.send_message(
                f"The player selected this action: {player_choice}. "
                f"Continue the story based on that choice. "
                f"Return ONLY valid JSON."
            )

        data = parse_json_response(response.text)

        return data

    except Exception as e:

        st.error(
            "The story engine could not generate the next scene."
        )

        st.caption(f"Technical error: {type(e).__name__}")

        return None


# ============================================================
# START BUTTON
# ============================================================

if len(st.session_state.story_history) == 0:

    st.info(
        "Choose your genre and art style from the sidebar, "
        "then start your adventure."
    )

    if st.button(
        "🎬 Start Adventure",
        type="primary",
        use_container_width=True
    ):

        with st.spinner("Creating your opening scene..."):

            data = generate_story()

            if data:

                st.session_state.story_history.append(data)

                # Generate image
                image_bytes = generate_image(
                    data["image_prompt"]
                )

                st.session_state.image_bytes = image_bytes

                # Generate audio
                audio_bytes = generate_audio(
                    data["story_text"]
                )

                st.session_state.audio_bytes = audio_bytes

                st.rerun()


# ============================================================
# DISPLAY CURRENT STORY
# ============================================================

if len(st.session_state.story_history) > 0:

    current_scene = st.session_state.story_history[-1]

    st.subheader("📜 Story")

    st.write(current_scene["story_text"])


    # ========================================================
    # DISPLAY IMAGE
    # ========================================================

    if (
        "image_bytes" in st.session_state
        and st.session_state.image_bytes
    ):

        st.image(
            st.session_state.image_bytes,
            caption="Generated Scene",
            use_container_width=True
        )


    # ========================================================
    # PLAY AUDIO
    # ========================================================

    if (
        "audio_bytes" in st.session_state
        and st.session_state.audio_bytes
    ):

        st.subheader("🔊 Narration")

        st.audio(
            st.session_state.audio_bytes,
            format="audio/mp3"
        )


    # ========================================================
    # PLAYER CHOICES
    # ========================================================

    st.subheader("🎮 What will you do?")

    options = current_scene["options"]

    for index, option in enumerate(options):

        if st.button(
            option,
            key=f"choice_{len(st.session_state.story_history)}_{index}",
            use_container_width=True
        ):

            with st.spinner("The story continues..."):

                data = generate_story(option)

                if data:

                    st.session_state.story_history.append(data)

                    # Generate next image
                    image_bytes = generate_image(
                        data["image_prompt"]
                    )

                    st.session_state.image_bytes = image_bytes

                    # Generate next narration
                    audio_bytes = generate_audio(
                        data["story_text"]
                    )

                    st.session_state.audio_bytes = audio_bytes

                    st.rerun()


# ============================================================
# RESET BUTTON
# ============================================================

if len(st.session_state.story_history) > 0:

    st.divider()

    if st.button("🔄 Restart Story"):

        st.session_state.story_history = []

        if "image_bytes" in st.session_state:
            del st.session_state.image_bytes

        if "audio_bytes" in st.session_state:
            del st.session_state.audio_bytes

        # Re-create Gemini chat
        st.session_state.chat = client.chats.create(
            model="gemini-3.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=f"""
You are the story director of an interactive visual novel.

Genre: {genre}
Art style: {art_style}

Return ONLY valid JSON with exactly these keys:

story_text
image_prompt
options

options must contain exactly 3 choices.

Do not use Markdown.
Do not use code fences.
""",
                temperature=0.8
            )
        )

        st.rerun() 