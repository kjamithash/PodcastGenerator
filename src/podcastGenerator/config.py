# Configuration settings
import os
from pydub import AudioSegment

# Configuration for API keys
# Retrieves API keys from environment variables for security and flexibility
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Additional settings or constants
DEFAULT_MODEL = "claude-3-5-sonnet-latest"  # Example of a model name used in the transcript generation

ELEVEN_LABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
VOICE_ID = "UEKYgullGqaF0keqT8Bu"  # Replace with the specific voice ID for Chris Brift

SILENCE_DURATION = 1300  # Duration in milliseconds to detect silence (example)
SILENCE_THRESHOLD = -40  # Threshold in dB to consider as silence (example)
AUDIO_OUTPUT_PATH = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/MentalModels/Insta post automation/Episodes/CW46"
TRANSCRIPTS_OUTPUT_PATH = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/processed/transcripts"

# Define the file paths and timestamps
intro_path = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/raw/audio/deep-thinking-INTRO.wav"
original_path = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/raw/audio/episodes/Quarantine.mp3"
transition1_path = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/raw/audio/MUG-TPH-001 - TRANSITI0N 1.wav"
transition2_path = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/raw/audio/MUG-TPH-001 - TRANSITI0N 2.wav"
outro_path = "/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/workspace/podcast_generator/podcastGenerator/data/raw/audio/MUG-TPH-001 - OUTRO.wav"

# Define timestamps (in milliseconds)
intro_start=0
