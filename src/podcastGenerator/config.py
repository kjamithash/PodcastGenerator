# Configuration settings
import os
from pydub import AudioSegment

# Define Mental Models
MENTAL_MODELS = ["War of Attrition", "Winning Hearts and Minds"]

# Configuration for API keys
# Retrieves API keys from environment variables for security and flexibility
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# LLM settings
DEFAULT_MODEL = "claude-3-5-sonnet-latest"  # Example of a model name used in the transcript generation

#TEXT2SPEECH settings
ELEVEN_LABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
VOICE_ID = "UEKYgullGqaF0keqT8Bu"  # Replace with the specific voice ID for Chris Brift

SILENCE_DURATION = 1300  # Duration in milliseconds to detect silence (example)
SILENCE_THRESHOLD = -40  # Threshold in dB to consider as silence (example)
AUDIO_OUTPUT_PATH = "data/raw/audio/generated"
TRANSCRIPTS_OUTPUT_PATH = "data/processed/transcripts"
PROCESSED_AUDIO_OUTPUT_PATH = 'data/processed/audio'

# Define the file paths and timestamps
intro_path = "data/raw/audio/deep-thinking-INTRO.wav"
transition1_path = "data/raw/audio/MUG-TPH-001 - TRANSITI0N 1.wav"
transition2_path = "data/raw/audio/MUG-TPH-001 - TRANSITI0N 2.wav"
outro_path = "data/raw/audio/MUG-TPH-001 - OUTRO.wav"

# Define timestamps (in milliseconds)
intro_start=0
intro_offset=5000
outro_offset=3000
fade_duration=3000

# Base audio amplification gain in dB
AMPLIFY_GAIN = 10
