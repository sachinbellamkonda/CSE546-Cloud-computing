
# Project 1

This is the python code for Creation and Deletion of AWS IaaS services.

# Installations required

Install the AWS CLI for the device from the official aws cli website. Link attached below.

https://aws.amazon.com/cli/

we will install AWS python SDK(boto3) for this Project. Use the below command to install the boto3.

pip install boto3


# Running the Project

After downloading the AWS CLI please configure your aws using the below command

aws configure

it will ask for your credentials(enter your key details) and format(json).

now you have setup your aws.

Before running the project change your keyName to your own AWS instance key name in the awsConection.py python program.

You can run my code using the command line after navigating into the project directory.

python awsConection.py

The program will output all the actions it has done to make the connection and resources it generated while doing it.

You can also check the same reflected in your aws console.

