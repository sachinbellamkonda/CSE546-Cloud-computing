import subprocess
import os
import boto3
import json
import urllib.parse


def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    lambda_client = boto3.client('lambda')

    # Extract bucket name and object key
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
    video_name, video_ext = os.path.splitext(video_filename)

    # Define local paths
    local_video_path = '/tmp/' + video_filename
    output_frame_filename = video_name + '.jpg'
    output_frame_path = '/tmp/' + output_frame_filename

    ffmpeg_path = '/opt/bin/ffmpeg'

    # Download the video from S3 to /tmp directory
    try:
        s3_client.download_file(source_bucket, object_key, local_video_path)
        print(f"Downloaded {object_key} from {source_bucket} to {local_video_path}")
    except Exception as e:
        print(f"Failed to download {object_key} from {source_bucket}: {e}")
        return

    # Extract one frame using ffmpeg
    try:
        cmd = [ffmpeg_path, '-i', local_video_path, '-vframes', '1', output_frame_path]
        subprocess.check_call(cmd)
        print(f"Extracted frame to {output_frame_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg execution: {e}")
        return
    except Exception as e:
        print(f"Unexpected error during frame extraction: {e}")
        return

    # Upload the frame to the destination bucket
    try:
        s3_client.upload_file(output_frame_path, destination_bucket, output_frame_filename)
        print(f"Uploaded {output_frame_filename} to {destination_bucket}")
    except Exception as e:
        print(f"Failed to upload frame to {destination_bucket}: {e}")
        return

    # Invoke the face-recognition function
    try:
        payload = {
            "bucket_name": destination_bucket,
            "image_file_name": output_frame_filename
        }
        response = lambda_client.invoke(
            FunctionName='face-recognition',
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        print(f"Invoked face-recognition function with payload: {payload}")
    except Exception as e:
        print(f"Failed to invoke face-recognition function: {e}")
        return

    # Cleanup temporary files
    try:
        os.remove(local_video_path)
        os.remove(output_frame_path)
        print("Cleaned up temporary files.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
        return
