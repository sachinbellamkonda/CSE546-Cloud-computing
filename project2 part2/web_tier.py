from fastapi import FastAPI, File, UploadFile, HTTPException
from starlette.responses import PlainTextResponse
import boto3
import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import time

app = FastAPI()


# AWS clients initialization
s3 = boto3.client('s3', region_name='us-east-1')
sqs = boto3.client('sqs', region_name='us-east-1')

# AWS resources configuration
ASU_ID = '1231674381'
REGION = 'us-east-1'
request_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-req-queue')['QueueUrl']
response_queue_url = sqs.get_queue_url(QueueName=f'{ASU_ID}-resp-queue')['QueueUrl']
input_bucket = f'{ASU_ID}-in-bucket'

# Shared dictionaries to map result_keys to events and full filenames
pending_results = {}
file_mapping = {}
results = {}
lock = threading.Lock()

# Thread pool executor for handling blocking boto3 calls
executor = ThreadPoolExecutor(max_workers=10)

# Flag to control the polling thread
polling_active = True

# Upload the input file to s3 in-bucket
def upload_to_s3(file_obj, bucket, key):
    try:
        s3.upload_fileobj(file_obj, bucket, key)
        print(f"Uploaded {key} to S3 bucket {bucket}.")
    except Exception as e:
        print(f"Error uploading {key} to S3: {e}")
        raise

# send the message to request sqs queue
def send_sqs_message(message_body):
    try:
        sqs.send_message(QueueUrl=request_queue_url, MessageBody=message_body)
        print(f"Sent message to SQS: {message_body}")
    except Exception as e:
        print(f"Error sending message to SQS: {e}")
        raise

# Function runs in background to poll the messages from response queue and dispatch them
def poll_response_queue():
    global polling_active
    while polling_active:
        try:
            response = sqs.receive_message(
                QueueUrl=response_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20
            )
            messages = response.get('Messages', [])
            for message in messages:
                body = message.get('Body', '')
                receipt_handle = message.get('ReceiptHandle', '')

                # Parse the message assuming format "result_key:classification_result"
                if ':' in body:
                    result_key, classification_result = body.split(':', 1)
                    print(
                        f"Received message: result_key={result_key}, classification_result={classification_result}")

                    with lock:
                        if result_key in pending_results:
                            results[result_key] = classification_result
                            pending_results[result_key].set()
                            print(f"Mapped result to {result_key}")
                        else:
                            print(f"Received result for unknown key: {result_key}")

                else:
                    print(f"Invalid message format: {body}")

                # Delete the message from the queue after processing
                try:
                    sqs.delete_message(
                        QueueUrl=response_queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    print(f"Deleted message from response queue: {body}")
                except Exception as e:
                    print(f"Error deleting message from SQS: {e}")
        except Exception as e:
            print(f"Error polling SQS response queue: {e}")
            time.sleep(5)  # Wait before retrying


# Start the polling thread as a daemon thread
polling_thread = threading.Thread(target=poll_response_queue, daemon=True)
polling_thread.start()


@app.post("/", response_class=PlainTextResponse)
async def receive_and_process_image(inputFile: UploadFile = File(...)):
    if not inputFile:
        print("No file uploaded.")
        raise HTTPException(status_code=400, detail="No file uploaded.")

    full_file_name = inputFile.filename
    filename_no_ext = os.path.splitext(full_file_name)[0]

    print(f"Processing file: {full_file_name}")

    # Upload image to S3 using a thread to prevent blocking
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor, upload_to_s3, inputFile.file, input_bucket, full_file_name
        )
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading to S3: {str(e)}")

    # Send message to SQS with the full filename as a plain string
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor, send_sqs_message, full_file_name
        )
    except Exception as e:
        print(f"Error sending message to SQS: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending message to SQS: {str(e)}")

    # Create an Event to wait for the response
    event = asyncio.Event()

    with lock:
        pending_results[filename_no_ext] = event
        file_mapping[filename_no_ext] = full_file_name  # Map result_key to full filename

    print(f"Waiting for classification result for {full_file_name} (result_key: {filename_no_ext})")

    # Wait indefinitely for the event to be set by the polling thread
    await event.wait()

    # Retrieve the result
    with lock:
        classification_result = results.pop(filename_no_ext, "No result found")
        full_file_name_mapped = file_mapping.pop(filename_no_ext, "unknown_file")
        pending_results.pop(filename_no_ext, None)

    print(f"Returning result for {full_file_name_mapped}: {classification_result}")
    return PlainTextResponse(f"{full_file_name_mapped}:{classification_result}")

# Will be called if the application is abruptly shutdown
@app.on_event("shutdown")
def shutdown_event():
    global polling_active
    polling_active = False
    polling_thread.join()
    print("Shutdown complete. Polling thread stopped.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
