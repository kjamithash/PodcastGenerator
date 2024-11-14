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
MODEL = "claude-3-5-sonnet-latest",
TEMPERATURE = 0.7
MAX_RETRIES = 3
TIMEOUT = 300  # 5 minute timeout
TRANSCRIPT_BREAK_DURATION = "1.3s"

#TEXT2SPEECH settings
ELEVEN_LABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
VOICE_ID = "UEKYgullGqaF0keqT8Bu"  # Replace with the specific voice ID for Chris Brift
STABILITY = 0.6
SIMILARITY_BOOST = 0.7
STYLE_EXXAGGERATION = 5

# Settings to identify silence gaps in audio
SILENCE_DURATION = 1300  # Duration in milliseconds to detect silence (example)
SILENCE_THRESHOLD = -40  # Threshold in dB to consider as silence (example)
RMS_THRESHOLD = 0.015 
GAP_DURATION = 1.35 
FRAME_LENGTH = 1024 
HOP_LENGTH = 512

# Pre-defined paths for audio and transcript generation
AUDIO_OUTPUT_PATH = "data/raw/audio/generated"
TRANSCRIPTS_OUTPUT_PATH = "data/processed/transcripts"
PROCESSED_AUDIO_OUTPUT_PATH = 'data/processed/audio'

# Define the file paths for overlay audio
intro_path = "data/raw/audio/deep-thinking-INTRO.wav"
transition1_path = "data/raw/audio/MUG-TPH-001 - TRANSITI0N 1.wav"
transition2_path = "data/raw/audio/MUG-TPH-001 - TRANSITI0N 2.wav"
outro_path = "data/raw/audio/MUG-TPH-001 - OUTRO.wav"

# Define timestamps for overlay audio (in milliseconds)
intro_start=0
intro_offset=5000
outro_offset=3000
fade_duration=3000
sec2ms=1000

# Base audio amplification gain in dB
AMPLIFY_GAIN = 10
