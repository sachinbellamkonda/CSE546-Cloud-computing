import boto3
import os
import time
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1

# AWS Configuration
ASU_ID = '1231674381'
REGION = 'us-east-1'

# Initialize AWS clients
sqs = boto3.client('sqs', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# SQS queue URLs
request_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-req-queue')['QueueUrl']
response_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-resp-queue')['QueueUrl']

# S3 bucket names
input_bucket_name = f'{ASU_ID}-in-bucket'
output_bucket_name = f'{ASU_ID}-out-bucket'

mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20)  # For face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval()       # For embedding extraction

def face_match(img_path, data_path):
    # Get embedding matrix of the given image
    img = Image.open(img_path)
    face, prob = mtcnn(img, return_prob=True)  # Returns cropped face and probability
    emb = resnet(face.unsqueeze(0)).detach()  # Get embedding
    saved_data = torch.load('data.pt')  # loading data.pt file
    embedding_list = saved_data[0]  # getting embedding data
    name_list = saved_data[1]  # getting list of names
    dist_list = []  # list of matched distances, minimum distance is used to identify the person

    for idx, emb_db in enumerate(embedding_list):
        dist = torch.dist(emb, emb_db).item()
        dist_list.append(dist)

    idx_min = dist_list.index(min(dist_list))
    return (name_list[idx_min], min(dist_list))

def main():
    data_path = '/home/ubuntu/data.pt'   # Path to your embedding data file

    # Ensure the data file exists
    if not os.path.exists(data_path):
        print(f"Embedding data file {data_path} not found.")
        return

    while True:
        # Receive messages from SQS request queue
        response = sqs.receive_message(
            QueueUrl=request_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5
        )

        if 'Messages' in response:
            for message in response['Messages']:
                receipt_handle = message['ReceiptHandle']
                image_key = message['Body']  # This is the image filename, e.g., 'test_00.jpg'

                print(f"Received message with image key: {image_key}")

                # Download image from S3 input bucket
                local_image_path = f'/tmp/{image_key}'
                s3.download_file(input_bucket_name, image_key, local_image_path)
                print(f"Downloaded image {image_key} from S3 bucket {input_bucket_name}")

                # Perform face recognition
                try:
                    name, distance = face_match(local_image_path, data_path)
                    classification_result = name
                    print(f"Face recognition result: {classification_result}")
                except Exception as e:
                    classification_result = "Error in processing"
                    print(f"Error in face recognition: {e}")

                # Upload result to S3 output bucket
                result_key = os.path.splitext(image_key)[0]  # Remove file extension
                s3.put_object(
                    Bucket=output_bucket_name,
                    Key=result_key,
                    Body=classification_result
                )
                print(f"Uploaded classification result to S3 bucket {output_bucket_name} with key {result_key}")

                # Send message to SQS response queue
                response_message = f"{result_key}:{classification_result}"
                sqs.send_message(
                    QueueUrl=response_queue_url,
                    MessageBody=response_message
                )
                print(f"Sent response message: {response_message} to queue {response_queue_url}")

                # Delete processed message from request queue
                sqs.delete_message(
                    QueueUrl=request_queue_url,
                    ReceiptHandle=receipt_handle
                )
                print(f"Deleted message from request queue")

                # Clean up local files
                os.remove(local_image_path)
                print(f"Removed local image file {local_image_path}")
        else:
            # No messages; wait before polling again
            time.sleep(1)

if __name__ == "__main__":
    main()