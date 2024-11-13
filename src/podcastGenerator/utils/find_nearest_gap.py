# Helper function to find the nearest silent gap within tolerance
def find_nearest_gap(silent_segments, target_time, tolerance=7):
    for start, end in silent_segments:
        if abs(start - target_time) <= tolerance:
            return start, end
    return None, None