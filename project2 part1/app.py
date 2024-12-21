from flask import Flask, request, Response
import pandas as pd
import os

app = Flask(__name__)

# Load the classification data into memory when the app starts
try:
    classification_df = pd.read_csv('faceDataset.csv')
    classification_dict = dict(zip(classification_df['Image'], classification_df['Results']))
except Exception as e:
    print(f"Failed to load the classification data: {str(e)}")

@app.route('/', methods=['POST'])
def face_recognition():
    if 'inputFile' not in request.files:
        return Response("No file attched in the request", status=400)

    fileUploaded = request.files['inputFile']
    if fileUploaded.filename == '':
        return Response("No file is selected", status=400)

    if fileUploaded:
        uploadedFilename = os.path.splitext(fileUploaded.filename)[0]
        prediction = classification_dict.get(uploadedFilename, 'Unknown')
        response_text = f"{uploadedFilename}:{prediction}"
        return Response(response_text, mimetype='text/plain')
    else:
        return Response("File processing failed", status=500)

if __name__ == '__main__':
    # Run the app on all interfaces, allowing external access, port 8000
    app.run(host='0.0.0.0', port=8000, debug=True)
