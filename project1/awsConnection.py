# 1 Load the AWS SDK
import boto3
import time
from botocore.exceptions import ClientError




# 2 My Key pair name
KEY_PAIR_NAME = 'Sachin_Bellamkonda'

# 3 Initializing all the AWS clients
ec2_client = boto3.client('ec2')
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Resource names
EC2_INSTANCE_NAME = 'cse546_EC2_Instance_Sachin_Bellamkonda_Project_1'
S3_BUCKET_NAME = 'cse546-s3-bucket-sachin-bellamkonda'
SQS_QUEUE_NAME = 'cse546_SQS_Queue_Sachin_Bellamkonda_Project_1.fifo'

AMI_ID = 'ami-0e86e20dae9224db8'

# Creating the  EC2 Instance
try:
    instance = ec2_client.run_instances(
        ImageId=AMI_ID,
        InstanceType='t2.micro',
        KeyName=KEY_PAIR_NAME,
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': EC2_INSTANCE_NAME}]
        }]
    )
    instance_id = instance['Instances'][0]['InstanceId']
    print("EC2 instance initiated")
except ClientError as e:
    print(f"Error while creating EC2 instance: {e}")

# Creating the S3 Bucket
try:
    region = s3_client.meta.region_name
    if region == 'us-east-1':  #Ignorig the BucketConfiguration of region is us-east-1
        s3_client.create_bucket(
            Bucket=S3_BUCKET_NAME,
            # CreateBucketConfiguration={'LocationConstraint': region}
        )
    else:
        s3_client.create_bucket(
            Bucket=S3_BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
    print("S3 bucket created")
except ClientError as e:
    print(f"Error while creating the S3 bucket: {e}")

# Creating the SQS Queue
try:
    queue = sqs_client.create_queue(
        QueueName=SQS_QUEUE_NAME,
        Attributes={'FifoQueue': 'true', 'ContentBasedDeduplication': 'true'}
    )
    queue_url = queue['QueueUrl']
    print("SQS FIFO queue created")
except ClientError as e:
    print(f"Error while creating SQS queue: {e}")

# 4
print("Request sent to create EC2, SQS, and S3 -- wait for 1 min to let AWS create and run them")
time.sleep(60)

# 5 List all the resources
# List all the EC2 instances
print("\nListing all the EC2 instances:")
instances = ec2_client.describe_instances()
for reservation in instances['Reservations']:
    for inst in reservation['Instances']:
        print(f"Instance ID: {inst['InstanceId']} --> {inst['State']['Name']}")

# List all the S3 buckets
print("\nListing all the S3 buckets:")
buckets = s3_client.list_buckets()
for bucket in buckets['Buckets']:
    print(f"Bucket Name: {bucket['Name']}")

# List all the SQS queues
print("\nListing all the SQS queues:")
queues = sqs_client.list_queues()
if 'QueueUrls' in queues:
    for q_url in queues['QueueUrls']:
        print(f"Queue URL: {q_url}")
else:
    print("No SQS queues found")

# 6 Upload an empty text file to S3
try:
    s3_client.put_object(Bucket=S3_BUCKET_NAME, Key='CSE546test.txt', Body='')
    print("\nEmpty file uploaded to S3 bucket.")
except ClientError as e:
    print(f"Error while uploading file to S3: {e}")

# 7 Send message to SQS queue
try:
    response = sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody='This is a test message',
        MessageGroupId='testGroup',
        MessageAttributes={
            'Name': {
                'DataType': 'String',
                'StringValue': 'test message'
            }
        }
    )
    print("Message sent to SQS queue")
except ClientError as e:
    print(f"Error sending the message to SQS queue: {e}")

# 8 Check how many number of messages in SQS queue
attributes = sqs_client.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=['ApproximateNumberOfMessages']
)
message_count = attributes['Attributes']['ApproximateNumberOfMessages']
print(f"\nNumber of messages in the SQS queue: {message_count}")

# 9 Receive message from SQS queue
try:
    messages = sqs_client.receive_message(
        QueueUrl=queue_url,
        MessageAttributeNames = ['All']
    )
    if 'Messages' in messages:
        message = messages['Messages'][0]
        print(f"\nMessage Name: {message['MessageAttributes']['Name']['StringValue']}")
        print(f"Message Body: {message['Body']}")

        # # Delete the message from the queue
        # sqs_client.delete_message(
        #     QueueUrl=queue_url,
        #     ReceiptHandle=message['ReceiptHandle']
        # )
    else:
        print("No messages received from SQS queue.")
except ClientError as e:
    print(f"Error receiving message from SQS queue: {e}")

# 10 Checking the number of messages in SQS queue again
attributes = sqs_client.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=['ApproximateNumberOfMessages']
)
message_count = attributes['Attributes']['ApproximateNumberOfMessages']
print(f"\nNumber of messages in the SQS queue after retrieval: {message_count}")

# 11 Wait for 10seconds
print("\nWaiting for 10 seconds...")
time.sleep(10)

# 12 Delete all the resources
print("\nDeleting all the resources...")
try:
    # Terminate the EC2 instance
    ec2_client.terminate_instances(InstanceIds=[instance_id])
    print("EC2 instance termination initiated")
except ClientError as e:
    print(f"Error terminating EC2 instance: {e}")

try:
    # Delete the S3 bucket and its contents
    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(S3_BUCKET_NAME)
    bucket.objects.all().delete()
    bucket.delete()
    print("S3 bucket deleted")
except ClientError as e:
    print(f"Error deleting S3 bucket: {e}")

try:
    # Delete the SQS queue
    sqs_client.delete_queue(QueueUrl=queue_url)
    print("SQS queue deleted.")
except ClientError as e:
    print(f"Error deleting SQS queue: {e}")

# 13 wait for 20seconds
print("\nWaiting for 20 seconds...")
time.sleep(20)

# 14 List all the resources again
# List all EC2 instances
print("\nListing all the EC2 instances:")
instances = ec2_client.describe_instances()
for reservation in instances['Reservations']:
    for inst in reservation['Instances']:
        print(f"Instance ID: {inst['InstanceId']} --> {inst['State']['Name']}")

# List all the S3 buckets
print("\nListing all the S3 buckets:")
buckets = s3_client.list_buckets()
for bucket in buckets['Buckets']:
    print(f"Bucket Name: {bucket['Name']}")

# List all the SQS queues
print("\nListing all the SQS queues:")
queues = sqs_client.list_queues()
if 'QueueUrls' in queues:
    for q_url in queues['QueueUrls']:
        print(f"Queue URL: {q_url}")
else:
    print("No SQS queues found")

print("\nAll actions completed.")