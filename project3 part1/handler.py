import subprocess
import os
import boto3
import json
import urllib.parse


def split_video_into_exactly_10_frames(video_path, output_dir, num_frames=10):

    #Get video duration using ffprobe
    cmd_duration = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', video_path
    ]
    result = subprocess.run(cmd_duration, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise ValueError("Could not determine video duration. Ensure the video file is valid.")

    if duration <= 0:
        raise ValueError("Invalid video duration.")

    # Calculate FPS to extract exactly `num_frames`
    fps = num_frames / duration

    # Step 3: Build ffmpeg command
    ffmpeg_command = [
        'ffmpeg', '-i', video_path,
        '-vf', f'fps={fps}',
        '-start_number', '0',
        '-vframes', str(num_frames),
        f'{output_dir}/output-%02d.jpg',
        '-y'  # Overwrite output files without asking
    ]

    # Run ffmpeg command
    try:
        subprocess.check_call(ffmpeg_command)
        print(f"Video successfully split into {num_frames} frames.")
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg execution: {e}")
        raise


def handler(event, context):

    s3_client = boto3.client('s3')

    # Extract bucket name and object key from the event
    try:
        source_bucket = event['Records'][0]['s3']['bucket']['name']
        object_key = urllib.parse.unquote_plus(
            event['Records'][0]['s3']['object']['key'], encoding='utf-8'
        )
    except KeyError as e:
        print(f"Missing key in event data: {e}")
        return

    # Define the destination bucket
    destination_bucket = source_bucket.replace('-input', '-stage-1')

    # Extract the video filename without extension
    video_filename = os.path.basename(object_key)
    video_name, _ = os.path.splitext(video_filename)

    # Define local paths
    local_video_path = f'/tmp/{video_filename}'
    output_dir = f'/tmp/{video_name}'

    # Download the video from S3 to /tmp directory
    try:
        s3_client.download_file(source_bucket, object_key, local_video_path)
        print(f"Downloaded {object_key} from {source_bucket} to {local_video_path}")
    except Exception as e:
        print(f"Failed to download {object_key} from {source_bucket}: {e}")
        return

    # Create the output directory
    os.makedirs(output_dir, exist_ok=True)

    # Split the video into exactly 10 frames
    try:
        split_video_into_exactly_10_frames(local_video_path, output_dir, num_frames=10)
    except Exception as e:
        print(f"Video splitting failed: {e}")
        return

    # Upload frames to the destination bucket
    try:
        for frame_file in os.listdir(output_dir):
            if frame_file.endswith('.jpg'):
                local_frame_path = os.path.join(output_dir, frame_file)
                s3_key = f'{video_name}/{frame_file}'
                s3_client.upload_file(local_frame_path, destination_bucket, s3_key)
                print(f"Uploaded {s3_key} to {destination_bucket}")
    except Exception as e:
        print(f"Failed to upload frames to {destination_bucket}: {e}")
        return

    # Cleanup temporary files
    try:
        os.remove(local_video_path)
        for frame_file in os.listdir(output_dir):
            os.remove(os.path.join(output_dir, frame_file))
        os.rmdir(output_dir)
        print("Cleaned up temporary files.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
