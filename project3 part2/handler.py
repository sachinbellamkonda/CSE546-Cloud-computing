# handler.py
# __copyright__   = "Copyright 2024, VISA Lab"
# __license__     = "MIT"

import os
import boto3
import cv2
from PIL import Image, ImageDraw, ImageFont
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch

# Initialize MTCNN and ResNet models outside the handler for efficiency
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20)
resnet = InceptionResnetV1(pretrained='vggface2').eval()

def face_recognition_function(key_path):
    # Face extraction
    img = cv2.imread(key_path, cv2.IMREAD_COLOR)
    boxes, _ = mtcnn.detect(img)

    # Face recognition
    key = os.path.splitext(os.path.basename(key_path))[0].split(".")[0]
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    face, prob = mtcnn(img, return_prob=True, save_path=None)
    saved_data = torch.load('/tmp/data.pt')  # loading data.pt file
    if face != None:
        emb = resnet(face.unsqueeze(0)).detach()  # detech is to make required gradient false
        embedding_list = saved_data[0]  # getting embedding data
        name_list = saved_data[1]  # getting list of names
        dist_list = []  # list of matched distances, minimum distance is used to identify the person
        for idx, emb_db in enumerate(embedding_list):
            dist = torch.dist(emb, emb_db).item()
            dist_list.append(dist)
        idx_min = dist_list.index(min(dist_list))

        # Save the result name in a file
        with open("/tmp/" + key + ".txt", 'w+') as f:
            f.write(name_list[idx_min])
        return name_list[idx_min]
    else:
        print(f"No face is detected")
    return

s3_client = boto3.client('s3')

def handler(event, context):
    print("Face recognition Lambda function started.")

    # Extract parameters from the event
    try:
        bucket_name = event['bucket_name']
        image_file_name = event['image_file_name']
    except KeyError as e:
        print(f"Missing key in event data: {e}")
        return

    # Define local paths
    local_image_path = '/tmp/' + image_file_name
    data_pt_local_path = '/tmp/data.pt'
    output_bucket = bucket_name.replace('-stage-1', '-output')
    output_file_name = os.path.splitext(image_file_name)[0] + '.txt'

    # Download the image from S3 to /tmp directory
    try:
        s3_client.download_file(bucket_name, image_file_name, local_image_path)
        print(f"Downloaded {image_file_name} from {bucket_name} to {local_image_path}")
    except Exception as e:
        print(f"Failed to download {image_file_name} from {bucket_name}: {e}")
        return

    # Download data.pt from S3
    data_pt_bucket = '1231674381-ccp3'
    data_pt_key = 'data.pt'  
    try:
        s3_client.download_file(data_pt_bucket, data_pt_key, data_pt_local_path)
        print(f"Downloaded data.pt from {data_pt_bucket} to {data_pt_local_path}")
    except Exception as e:
        print(f"Failed to download data.pt: {e}")
        return

    # Perform face recognition
    try:
        recognized_name = face_recognition_function(local_image_path)
        if recognized_name:
            # Save the recognized name to a text file
            output_file_path = '/tmp/' + output_file_name
            with open(output_file_path, 'w+') as f:
                f.write(recognized_name)
            print(f"Recognized name: {recognized_name}")

            # Upload the result to the output bucket
            s3_client.upload_file(output_file_path, output_bucket, output_file_name)
            print(f"Uploaded result to {output_bucket}/{output_file_name}")
        else:
            print("No face detected or recognition failed.")
    except Exception as e:
        print(f"Face recognition failed: {e}")
        return

    # Cleanup temporary files
    try:
        os.remove(local_image_path)
        os.remove(data_pt_local_path)
        os.remove(output_file_path)
        print("Cleaned up temporary files.")
    except Exception as e:
        print(f"Cleanup failed: {e}")


