from pydub import AudioSegment
import os

def overlay_audio_with_timestamps(
    intro_path, original_path, transition1_path, transition2_path, outro_path,
    intro_start, transition1_start_1, transition2_start, transition1_start_2
):
    """
    Overlays multiple audio clips at specified timestamps on an original audio file.
    """

    # Load the audio files
    intro = AudioSegment.from_file(intro_path)
    original = AudioSegment.from_file(original_path)
    transition1 = AudioSegment.from_file(transition1_path)
    transition2 = AudioSegment.from_file(transition2_path)
    outro = AudioSegment.from_file(outro_path)

    # Step 0: Amplify the original audio
    amplified_original = original.apply_gain(10.0)  # Amplification level set to 10 dB

    fade_duration = 5000  # Duration of fade in/out in milliseconds (3 seconds)
    intro = intro.fade_out(fade_duration)

    # Step 1: Start with the intro audio and set up base_audio
    base_audio = intro

    # Step 2: Extend base_audio with silence to match amplified_original length plus 5-second offset
    amplified_original_length = len(amplified_original) + 5000  # Adding 5 seconds
    if amplified_original_length > len(base_audio):
        silence_padding = AudioSegment.silent(duration=amplified_original_length - len(base_audio))
        base_audio += silence_padding  # Add silence to the end of base_audio

    # Step 3: Overlay the amplified original audio, starting 5 seconds after the intro starts
    overlay_start = intro_start + 5000
    base_audio = base_audio.overlay(amplified_original, position=overlay_start)

    # Step 4: Overlay transition1 at specified position
    base_audio = base_audio.overlay(transition1, position=5000+transition1_start_1*1000)

    # Step 5: Overlay transition2 at specified position
    base_audio = base_audio.overlay(transition2, position=5000+transition2_start*1000)

    # Step 6: Overlay transition1 again at another specified position
    base_audio = base_audio.overlay(transition1, position=5000+transition1_start_2*1000)

    # Step 7: Extend the base_audio to match the length of the amplified_original plus outro duration
    outro = outro.fade_in(fade_duration)
    outro = outro.fade_out(fade_duration)

    outro_position = len(base_audio) - len(outro) + 3000
    if outro_position + len(outro) > len(base_audio):
        additional_silence = AudioSegment.silent(duration=(outro_position + len(outro)) - len(base_audio))
        base_audio += additional_silence

    base_audio = base_audio.overlay(outro, position=outro_position)

    # Save the final audio with the filename suffixed by '_podgen_output'
    base_filename = os.path.splitext(os.path.basename(original_path))[0]  # Get the base filename without extension
    output_filename = f"{base_filename}_podgen_output.mp3"
    base_audio.export(output_filename, format="mp3")
    print(f"Final audio saved as '{output_filename}'")

