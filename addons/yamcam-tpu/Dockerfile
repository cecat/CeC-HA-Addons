FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TensorFlow Lite runtime and compatible NumPy version
RUN pip install --no-cache-dir tflite-runtime 'numpy<2.0' paho-mqtt pyyaml

# Copy the local model and class map files from the subdirectory
COPY files/yamnet.tflite .
COPY files/yamnet_class_map.csv .

# Copy the yamcam.py script
COPY yamcam-tpu.py .

# Set entrypoint
CMD ["python", "yamcam-tpu.py"]
