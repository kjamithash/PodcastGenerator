import os
import librosa
import librosa.display
import matplotlib.pyplot as plt
from pydub import AudioSegment
import numpy as np
from src.podcastGenerator.utils.find_nearest_gap import find_nearest_gap
from src.podcastGenerator import config  # Ensure config is imported

def identify_transition_points(audio_path, rms_threshold=config.RMS_THRESHOLD, gap_duration=config.GAP_DURATION, frame_length=config.FRAME_LENGTH, hop_length=config.HOP_LENGTH):
    # Extract the filename from the audio path (for use in the plot title)
    filename = os.path.basename(audio_path)

    # Ensure the file exists
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"The audio file at {audio_path} does not exist.")
    
    # Check if the file can be read by pydub
    try:
        audio = AudioSegment.from_mp3(audio_path)
        print(f"Loaded audio with {len(audio)} milliseconds duration.")
    except Exception as e:
        raise ValueError(f"Error loading audio with pydub: {e}")
    
    # Load audio with librosa and check for empty file
    y, sr = librosa.load(audio_path, sr=None)
    print(f"Loaded audio with {len(y)} samples and {sr} sample rate.")
    if len(y) == 0:
        raise ValueError(f"Loaded audio has zero samples. Check the audio file: {audio_path}")
    
    # Check for silence in the audio
    if np.sum(np.abs(y)) == 0:
        raise ValueError("The audio file is silent or has zero amplitude.")
    
    # Compute RMS
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    print(f"RMS values: {rms[:10]}...")  # Print first 10 RMS values for inspection
    
    rms_time_axis = librosa.times_like(rms, sr=sr, hop_length=hop_length)

    # Detect silence segments
    silent_segments = []
    current_silence_start = None
    for i, rms_value in enumerate(rms):
        if rms_value < rms_threshold:
            if current_silence_start is None:
                current_silence_start = rms_time_axis[i]
        else:
            if current_silence_start is not None:
                silence_duration = rms_time_axis[i] - current_silence_start
                if silence_duration >= gap_duration:
                    silent_segments.append((current_silence_start, rms_time_axis[i]))
                current_silence_start = None
    
    # Check for trailing silence
    if current_silence_start is not None:
        silence_duration = rms_time_axis[-1] - current_silence_start
        if silence_duration >= gap_duration:
            silent_segments.append((current_silence_start, rms_time_axis[-1]))

    transitions = {
        "transition1_start_1": None,
        "transition2_start": None,
        "transition1_start_2": None
    }

    # Set up the plot
    fig, ax = plt.subplots(figsize=(14, 6))
    librosa.display.waveshow(y, sr=sr, alpha=0.6, color="b", label="Audio Waveform")
    ax.plot(rms_time_axis, rms, color="orange", alpha=0.7, label="RMS Energy")
    ax.set_title(f"Waveform of {filename} with Detected Silence Gaps Highlighted")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude / Energy")

    # Plot silence segments
    for start, end in silent_segments:
        ax.axvspan(start, end, color='red', alpha=0.3, label="Silence Gap" if start == silent_segments[0][0] else "")

       # Highlight existing transition points
    for label, time in transitions.items():
        if time is not None:
            ax.axvline(x=time, color='green', linestyle='--', label=f"{label} at {time:.2f}s")

    # Set up a variable to store clicked transition points
    clicked_points = []
    transition_index = 0  # Start with the first transition point to be overridden
    transition_labels = list(transitions.keys())

    def on_click(event):
        nonlocal transition_index  # Make sure transition_index is updated globally
        
        # Get the x-coordinate of the click (time in seconds)
        if event.inaxes:
            click_time = event.xdata
            if click_time is not None:
                clicked_points.append(click_time)
                # Update the current transition point with the clicked time
                current_label = transition_labels[transition_index]
                transitions[current_label] = click_time

                # Plot a blue dot where clicked
                ax.plot(click_time, 0, 'bo', markersize=10)
                ax.set_title(f"Waveform of {filename} (Clicked Time: {click_time:.2f}s)")

                # Update the label with the new transition point
                ax.axvline(x=click_time, color='green', linestyle='--', label=f"{current_label} at {click_time:.2f}s")
                
                # Move to the next transition point for the next click
                transition_index = (transition_index + 1) % len(transition_labels)

                plt.draw()  # Redraw the plot to show the new click marker
                print(f"Clicked at time: {click_time:.2f} seconds for {current_label}")

    # Connect the mouse click event to the plot
    fig.canvas.mpl_connect('button_press_event', on_click)

    plt.legend(loc="upper right")
    plt.show()

    # Return the transition points (including clicked ones)
    return transitions, clicked_points
