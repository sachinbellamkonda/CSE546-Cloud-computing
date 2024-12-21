import boto3
import configparser
import os

# Read AWS credentials
aws_credentials_path = os.path.expanduser("~/.aws/credentials")
config = configparser.ConfigParser()
config.read(aws_credentials_path)
aws_access_key_id = config.get('default', 'aws_access_key_id')
aws_secret_access_key = config.get('default', 'aws_secret_access_key')

# Create EC2 resource and client
ec2 = boto3.resource('ec2', region_name='us-east-1',
                     aws_access_key_id=aws_access_key_id,
                     aws_secret_access_key=aws_secret_access_key)
ec2_client = boto3.client('ec2', region_name='us-east-1',
                          aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key)

# Define the instance name
instance_name = 'web-instance'

# Check for existing instance
instances = ec2.instances.filter(
    Filters=[
        {'Name': 'tag:Name', 'Values': [instance_name]},
        {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
    ]
)
instances = list(instances)

if instances:
    instance = instances[0]
    print(f"Found instance {instance.id} with state {instance.state['Name']}")
    if instance.state['Name'] == 'running':
        # Disassociate and release Elastic IP
        addresses = ec2_client.describe_addresses(
            Filters=[
                {'Name': 'instance-id', 'Values': [instance.id]}
            ]
        )
        if addresses['Addresses']:
            eip = addresses['Addresses'][0]
            print(f"Disassociating and releasing Elastic IP {eip['PublicIp']}...")
            ec2_client.disassociate_address(AssociationId=eip['AssociationId'])
            ec2_client.release_address(AllocationId=eip['AllocationId'])
        else:
            print("No Elastic IP associated with the instance.")

        # Stop the instance
        print(f"Stopping instance {instance.id}...")
        instance.stop()
        instance.wait_until_stopped()
        print(f"Instance {instance.id} is now stopped.")
    else:
        print("Instance is already stopped.")
else:
    print("No instance named 'web-instance' found.")
