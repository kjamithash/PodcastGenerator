# Convert silence segments from milliseconds to minutes and seconds
def format_time(milliseconds):
    seconds = milliseconds / 1000
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}m {seconds}s"