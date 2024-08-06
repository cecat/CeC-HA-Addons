FROM python:3.9-alpine

WORKDIR /app

# Install system dependencies using apk
RUN apk update && apk add --no-cache \
    ffmpeg \
    libsndfile \
    wget \
    gnupg \
    curl \
    bash

# Add the Edge TPU repository and install the libedgetpu1-std package
RUN echo "@edge http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
    && apk update \
    && apk add --no-cache libedgetpu1-std@edge

# Install TensorFlow Lite runtime and compatible NumPy version
RUN pip install --no-cache-dir tflite-runtime 'numpy<2.0' paho-mqtt pyyaml

# Copy the local model and class map files from the subdirectory
COPY files/yamnet.tflite .
COPY files/yamnet_class_map.csv .

# Copy the yamcam-tpu.py script
COPY yamcam-tpu.py .

# Set entrypoint
CMD ["python", "yamcam-tpu.py"]

