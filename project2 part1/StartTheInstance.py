import boto3
import configparser
import os

# Read AWS  from .aws/Credentials folder
aws_credentials_path = os.path.expanduser("~/.aws/credentials")
config = configparser.ConfigParser()
config.read(aws_credentials_path)
aws_access_key_id = config.get('default','aws_access_key_id')
aws_secret_access_key = config.get('default','aws_secret_access_key')

# Create EC2 resource and client
ec2 = boto3.resource('ec2', region_name='us-east-1',
                     aws_access_key_id=aws_access_key_id,
                     aws_secret_access_key=aws_secret_access_key)
ec2_client = boto3.client('ec2', region_name='us-east-1',
                          aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key)

# Define the AMI ID and instance name
ami_id = "ami-0866a3c8686eaeeba"
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
    if instance.state['Name'] == 'stopped':
        print("Starting the instance...")
        instance.start()
        instance.wait_until_running()
        instance.reload()
    else:
        print("Instance is already running.")

    # Check for Elastic IP
    addresses = ec2_client.describe_addresses(
        Filters=[
            {'Name': 'instance-id', 'Values': [instance.id]}
        ]
    )

    if addresses['Addresses']:
        eip = addresses['Addresses'][0]
        public_ip = eip['PublicIp']
        print(f"Elastic IP {public_ip} is associated with instance {instance.id}")
    else:
        print("Allocating and associating a new Elastic IP...")
        eip = ec2_client.allocate_address(Domain='vpc')
        ec2_client.associate_address(InstanceId=instance.id,
                                     AllocationId=eip['AllocationId'])
        public_ip = eip['PublicIp']
        print(f"Elastic IP {public_ip} associated with instance {instance.id}")
else:
    print("No existing instance found. Launching a new one...")
    instances = ec2.create_instances(
        ImageId=ami_id,
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        KeyName = 'Sachin_Bellamkonda',
        TagSpecifications=[{'ResourceType': 'instance',
                            'Tags': [{'Key': 'Name', 'Value': instance_name}]}])
    instance = instances[0]
    instance.wait_until_running()
    instance.reload()
    print(f"Launched new instance {instance.id}.")

    # Allocate and associate Elastic IP
    print("Allocating and associating a new Elastic IP...")
    eip = ec2_client.allocate_address(Domain='vpc')
    ec2_client.associate_address(InstanceId=instance.id,
                                 AllocationId=eip['AllocationId'])
    public_ip = eip['PublicIp']
    print(f"Elastic IP {public_ip} associated with instance {instance.id}")

print(f"Instance {instance.id} is running. Public IP: {public_ip}")

# Save the public IP to a file for easy access
with open('public_ip.txt', 'w') as f:
    f.write(public_ip)
