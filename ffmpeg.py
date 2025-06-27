import subprocess
import argparse
import json
import sys
import shlex # To safely quote command-line arguments

def get_duration(filepath):
    """Gets the duration of an audio file using ffprobe."""
    command = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        filepath
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        duration = float(metadata['format']['duration'])
        return duration
    except FileNotFoundError:
        print(f"Error: ffprobe not found. Please ensure FFmpeg/FFprobe is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe on {filepath}: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing ffprobe output for {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def create_slideshow(image_paths, audio_paths, output_path, font_file, text_content):
    """
    Creates a video slideshow from images and audio, synchronizing image
    duration to audio duration, combining audio, and adding centered text.
    """
    num_files = len(image_paths)

    if num_files != len(audio_paths):
        print("Error: The number of image files and audio files must be the same.", file=sys.stderr)
        sys.exit(1)

    if num_files == 0:
        print("Error: No input files provided.", file=sys.stderr)
        sys.exit(1)

    # --- 1. Get audio durations ---
    print("Getting audio durations using ffprobe...")
    audio_durations = []
    for i, audio_path in enumerate(audio_paths):
        print(f"  Processing audio file {i + 1}/{num_files}: {audio_path}")
        duration = get_duration(audio_path)
        audio_durations.append(duration)
    print("Audio durations obtained.")

    # --- 2. Build FFmpeg command ---
    ffmpeg_command = ['ffmpeg']

    # Add image inputs with loop and duration
    for i, img_path in enumerate(image_paths):
        ffmpeg_command.extend(['-loop', '1', '-t', str(audio_durations[i]), '-i', img_path])

    # Add audio inputs
    for audio_path in audio_paths:
        ffmpeg_command.extend(['-i', audio_path])

    # --- Build complex filter graph ---
    # Input indices: 0 to num_files-1 are images (video streams [I:v]), num_files to 2*num_files-1 are audio (audio streams [A:a])
    # Example for 3 files: Images [0:v][1:v][2:v], Audio [3:a][4:a][5:a]

    video_concat_inputs = ''.join([f'[{i}:v]' for i in range(num_files)])
    audio_concat_inputs = ''.join([f'[{num_files + i}:a]' for i in range(num_files)])

    # Escape special characters in text and font path for FFmpeg filter string
    # Using shlex.quote to safely quote paths, and then escaping special characters for drawtext
    escaped_font_file = shlex.quote(font_file).replace('\\', '\\\\').replace("'", "\\'")
    escaped_text_content = text_content.replace("'", "\\'").replace(':', '\\:').replace('[', '\\[').replace(']', '\\]').replace(',', '\\,')


    filter_complex = (
        f"{video_concat_inputs}concat=n={num_files}:v=1:a=0[v_slideshow]; "  # Concatenate video streams
        f"{audio_concat_inputs}concat=n={num_files}:v=0:a=1[a_combined]; "    # Concatenate audio streams
        f"[v_slideshow]drawtext=text='{escaped_text_content}':fontfile='{escaped_font_file}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2[v_text]; " # Add text to video stream
        f"[v_text][a_combined] விகித=shortest=1" # Merge video with text and audio
    )

    ffmpeg_command.extend(['-filter_complex', filter_complex])

    # Add output options
    ffmpeg_command.extend([
        '-c:v', 'libx264',      # Video codec
        '-preset', 'medium',   # Encoding preset
        '-crf', '23',           # Quality level (lower is better)
        '-c:a', 'aac',          # Audio codec
        '-b:a', '128k',         # Audio bitrate
        '-shortest',           # Finish when the shortest input stream ends
        '-y',                   # Overwrite output file without asking
        output_path             # Output file path
    ])

    # --- 3. Execute FFmpeg command ---
    print("\nExecuting FFmpeg command...")
    print(" ".join([shlex.quote(arg) for arg in ffmpeg_command])) # Print quoted command for debugging

    try:
        # Use subprocess.run with a stream for better output handling if needed,
        # but for simplicity, let's just run and check for errors first.
        process = subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
        print("\nFFmpeg process finished successfully.")
        print(f"Output saved to: {output_path}")
        # print("\nFFmpeg stdout:\n", process.stdout) # Uncomment for verbose FFmpeg output
        # print("\nFFmpeg stderr:\n", process.stderr) # Uncomment for verbose FFmpeg output

    except FileNotFoundError:
        print(f"Error: ffmpeg not found. Please ensure FFmpeg/FFprobe is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running FFmpeg command: {e}", file=sys.stderr)
        print(f"FFmpeg stdout:\n{e.stdout}", file=sys.stderr)
        print(f"FFmpeg stderr:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a video slideshow with audio and centered text using FFmpeg.')
    parser.add_argument('-i', '--images', nargs='+', required=True, help='List of input image file paths.')
    parser.add_argument('-a', '--audio', nargs='+', required=True, help='List of input audio file paths corresponding to images.')
    parser.add_argument('-o', '--output', required=True, help='Output video file path.')
    parser.add_argument('-f', '--font', required=True, help='Path to a TrueType Font (.ttf) file for the text overlay.')
    parser.add_argument('-t', '--text', default='Centered Text', help='Text content to add to the center of the video.')

    args = parser.parse_args()

    create_slideshow(args.images, args.audio, args.output, args.font, args.text)