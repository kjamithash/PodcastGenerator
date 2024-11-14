import requests
from src.podcastGenerator.config import ELEVEN_LABS_API_KEY
from src.podcastGenerator import config

# Function to convert text to audio using the Eleven Labs API
def convert_text_to_audio(text, filename):
    """
    Converts text to audio using the Eleven Labs API and saves the audio to a specified filename.
    
    Parameters:
    - text (str): The text content to convert to audio.
    - filename (str): The path and filename where the generated audio will be saved.
    """
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_LABS_API_KEY
    }
    payload = {
        "text": text,
        "voice_settings": {
            "stability": config.STABILITY,
            "similarity_boost": config.SIMILARITY_BOOST,
            "style_exaggeration": config.STYLE_EXXAGGERATION
        }
    }

    # Send request to Eleven Labs API
    response = requests.post(f"{config.ELEVEN_LABS_API_URL}/{config.VOICE_ID}", headers=headers, json=payload)
    
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"Audio saved to {filename}")
    else:
        print(f"Failed to generate audio: {response.status_code}, {response.text}")
