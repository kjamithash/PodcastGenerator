# Main module entry point
import os
from src.podcastGenerator import config
from src.podcastGenerator.components.transcript_generator import generate_transcripts
from src.podcastGenerator.utils.read_text import read_text_from_docx
from src.podcastGenerator.components.audio_generator import convert_text_to_audio
from src.podcastGenerator.components.plot_audio import identify_transition_points
from src.podcastGenerator.components.overlay_audio import overlay_audio_with_timestamps

# Main function to generate and save transcripts and audio files
def main():
    
    # Generate transcripts for each mental model
    # Make sure you have defined the right mental modles in config.py
    transcripts = generate_transcripts(config.MENTAL_MODELS, config.TRANSCRIPTS_OUTPUT_PATH)

    # Convert each transcript to and audio file and save it
    # Loop through .docx files in the transcript directory
    for filename in os.listdir(config.TRANSCRIPTS_OUTPUT_PATH):
        if filename.endswith(".docx"):
            filepath = os.path.join(config.TRANSCRIPTS_OUTPUT_PATH, filename)
            
            # Read text from the .docx file
            transcript_text = read_text_from_docx(filepath)
            
            # Create audio filename and save path
            audio_filename = f"{os.path.splitext(filename)[0]}_audio.mp3"
            audio_filepath = os.path.join(config.AUDIO_OUTPUT_PATH, audio_filename)
            
            # Convert text to audio and save it
            convert_text_to_audio(transcript_text, audio_filepath)
            print(f"Audio generated for {filename} and saved to {audio_filepath}")

    # Find the silence gaps and identify transition music start points for each audio file
    # Loop through all audio files in the specified directory
    for filename in os.listdir(config.AUDIO_OUTPUT_PATH):
        if filename.endswith((".mp3", ".wav")):  # Include only audio files
            audio_filepath = os.path.join(config.AUDIO_OUTPUT_PATH, filename)
            print(f"\nAudio File path: {audio_filepath}")
            # Call the plot function for each audio file and unpack the returned values
            transitions, clicked_points = identify_transition_points(audio_filepath)
            
            # Extract the transition points from the returned dictionary
            transition1_start_1 = transitions.get("transition1_start_1", None)
            transition2_start = transitions.get("transition2_start", None)
            transition1_start_2 = transitions.get("transition1_start_2", None)

            print(f"\nTransition points for {filename}:")
            print(f"transition1_start_1: {transition1_start_1}")
            print(f"transition2_start: {transition2_start}")
            print(f"transition1_start_2: {transition1_start_2}")


            # Call the Overlay audio to overlay transition music at timestamps
            overlay_audio_with_timestamps(
                intro_path=config.intro_path,
                original_path=audio_filepath,
                transition1_path=config.transition1_path,
                transition2_path=config.transition2_path,
                outro_path=config.outro_path,
                intro_start=config.intro_start,
                transition1_start_1=transition1_start_1,
                transition2_start=transition2_start,
                transition1_start_2=transition1_start_2
            )


# Entry point check to allow standalone execution
if __name__ == "__main__":
    main()
