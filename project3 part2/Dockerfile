# Dockerfile
# __copyright__   = "Copyright 2024, VISA Lab"
# __license__     = "MIT"

# syntax=docker/dockerfile:1

# Use an official Python slim image
FROM python:3.8-slim-buster

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libopencv-dev \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable for TORCH_HOME
ENV TORCH_HOME=/app/torch_models

# Create directory for torch models
RUN mkdir -p /app/torch_models

# Copy application code
COPY handler.py .

# Pre-download the models
RUN python -c "from facenet_pytorch import InceptionResnetV1; model = InceptionResnetV1(pretrained='vggface2')"

# Set appropriate permissions on the downloaded model files
RUN chmod -R a+rX /app/torch_models

# Install AWS Lambda Runtime Interface Client
RUN pip install awslambdaric

# Set the entrypoint
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]

# Set the command to your handler
CMD [ "handler.handler" ]
