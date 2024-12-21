# controller.py

import boto3
import time
import os

# Initialize AWS services clients
sqs = boto3.client('sqs', region_name='us-east-1')
ec2 = boto3.resource('ec2', region_name='us-east-1')

# Constants for queue and bucket names
ASU_ID = '1231674381'
REGION = 'us-east-1'
request_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-req-queue')['QueueUrl']
response_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-resp-queue')['QueueUrl']
input_bucket = f'{ASU_ID}-in-bucket'
app_tier_ami_id = 'ami-0eff13949d9e2cd6c'

def get_queue_length():
    """Retrieve the number of messages in the request queue."""
    attributes = sqs.get_queue_attributes(
        QueueUrl=request_queue_url,
        AttributeNames=['ApproximateNumberOfMessages']
    )
    return int(attributes['Attributes'].get('ApproximateNumberOfMessages', '0'))

def adjust_app_tier_instances(queue_length):
    """Scale up or down the app tier based on the queue length."""
    # Define scaling thresholds and logic
    desired_instance_count = min(20,queue_length)
    if queue_length==0 and desired_instance_count>0:
        desired_instance_count=0
    current_instances = list(ec2.instances.filter(
        Filters=[
            {'Name': 'tag:AppTier', 'Values': ['true']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ]
    ))
    current_count = len(current_instances)

    if current_count < desired_instance_count:
        # Launch new instances
        instances_needed = desired_instance_count - current_count
        for i in range(instances_needed):
            instance_number = current_count + i + 1
            ec2.create_instances(
                ImageId=app_tier_ami_id,
                MinCount=1,
                MaxCount=1,
                InstanceType='t2.micro',
                KeyName='Sachin_Bellamkonda',
                IamInstanceProfile={'Name': 'AppTierRole'},
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': f'app-tier-instance-{instance_number}'},
                        {'Key': 'AppTier', 'Value': 'true'}
                    ]
                }],
                UserData="""#!/bin/bash
                cd /home/ubuntu/
                source /home/ubuntu/ccp2/bin/activate
                nohup python3 /home/ubuntu/app_tier.py > app_tier.log 2>&1 &
                """
            )
            print(f"Launched app-tier-instance-{instance_number}.")
    elif current_count > desired_instance_count:
        # Terminate excess instances
        instances_to_terminate = [inst.id for inst in current_instances[desired_instance_count:]]
        ec2.instances.filter(InstanceIds=instances_to_terminate).terminate()
        print(f"Terminated {len(instances_to_terminate)} excess App Tier instances.")

def autoscale_app_tier():
    """Background thread function to autoscale the app tier."""
    while True:
        queue_length = get_queue_length()
        adjust_app_tier_instances(queue_length)
        time.sleep(15)

if __name__ == "__main__":
    autoscale_app_tier()
