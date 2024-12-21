from fastapi import FastAPI, File, UploadFile, HTTPException
from starlette.responses import PlainTextResponse
import boto3
import asyncio
import os
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
import time

app = FastAPI()

# Configure Logging
logging.basicConfig(
    filename='web_tier.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

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


def upload_to_s3(file_obj, bucket, key):
    """
    Function to upload a file to S3.
    """
    try:
        s3.upload_fileobj(file_obj, bucket, key)
        logging.info(f"Uploaded {key} to S3 bucket {bucket}.")
    except Exception as e:
        logging.error(f"Error uploading {key} to S3: {e}")
        raise


def send_sqs_message(message_body):
    """
    Function to send a message to SQS.
    """
    try:
        sqs.send_message(QueueUrl=request_queue_url, MessageBody=message_body)
        logging.info(f"Sent message to SQS: {message_body}")
    except Exception as e:
        logging.error(f"Error sending message to SQS: {e}")
        raise


def poll_response_queue():
    """
    Background thread to poll the response SQS queue and dispatch results.
    """
    global polling_active
    while polling_active:
        try:
            response = sqs.receive_message(
                QueueUrl=response_queue_url,
                MaxNumberOfMessages=10,  # Adjust as needed
                WaitTimeSeconds=20         # Long polling
            )
            messages = response.get('Messages', [])
            for message in messages:
                body = message.get('Body', '')
                receipt_handle = message.get('ReceiptHandle', '')

                # Parse the message assuming format "result_key:classification_result"
                if ':' in body:
                    result_key, classification_result = body.split(':', 1)
                    logging.info(
                        f"Received message: result_key={result_key}, classification_result={classification_result}")

                    with lock:
                        if result_key in pending_results:
                            results[result_key] = classification_result
                            pending_results[result_key].set()
                            logging.info(f"Mapped result to {result_key}")
                        else:
                            logging.warning(f"Received result for unknown key: {result_key}")

                else:
                    logging.warning(f"Invalid message format: {body}")

                # Delete the message from the queue after processing
                try:
                    sqs.delete_message(
                        QueueUrl=response_queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    logging.info(f"Deleted message from response queue: {body}")
                except Exception as e:
                    logging.error(f"Error deleting message from SQS: {e}")
        except Exception as e:
            logging.error(f"Error polling SQS response queue: {e}")
            time.sleep(5)  # Wait before retrying in case of error


# Start the polling thread as a daemon thread
polling_thread = threading.Thread(target=poll_response_queue, daemon=True)
polling_thread.start()


@app.post("/", response_class=PlainTextResponse)
async def receive_and_process_image(inputFile: UploadFile = File(...)):
    if not inputFile:
        logging.warning("No file uploaded.")
        raise HTTPException(status_code=400, detail="No file uploaded.")

    full_file_name = inputFile.filename  # e.g., image1.jpg
    filename_no_ext = os.path.splitext(full_file_name)[0]  # e.g., image1

    logging.info(f"Processing file: {full_file_name}")

    # Upload image to S3 using a thread to prevent blocking
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor, upload_to_s3, inputFile.file, input_bucket, full_file_name
        )
    except Exception as e:
        logging.error(f"Error uploading to S3: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading to S3: {str(e)}")

    # Send message to SQS with the full filename as a plain string
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor, send_sqs_message, full_file_name
        )
    except Exception as e:
        logging.error(f"Error sending message to SQS: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending message to SQS: {str(e)}")

    # Create an Event to wait for the response
    event = asyncio.Event()

    with lock:
        pending_results[filename_no_ext] = event
        file_mapping[filename_no_ext] = full_file_name  # Map result_key to full filename

    logging.info(f"Waiting for classification result for {full_file_name} (result_key: {filename_no_ext})")

    # Wait indefinitely for the event to be set by the polling thread
    await event.wait()

    # Retrieve the result
    with lock:
        classification_result = results.pop(filename_no_ext, "No result found")
        full_file_name_mapped = file_mapping.pop(filename_no_ext, "unknown_file")
        pending_results.pop(filename_no_ext, None)

    logging.info(f"Returning result for {full_file_name_mapped}: {classification_result}")
    return PlainTextResponse(f"{full_file_name_mapped}:{classification_result}")


@app.on_event("shutdown")
def shutdown_event():
    """
    Handle application shutdown by stopping the polling thread.
    """
    global polling_active
    polling_active = False
    polling_thread.join()
    logging.info("Shutdown complete. Polling thread stopped.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
