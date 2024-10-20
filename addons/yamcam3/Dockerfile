FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TensorFlow Lite runtime and compatible NumPy version
COPY requirements.txt .
RUN pip install --no-cache-dir tflite-runtime pycoral 'numpy<2.0' paho-mqtt pyyaml scipy

# Copy the local model and class map files from the subdirectory
COPY files/yamnet.tflite .
COPY files/yamnet_class_map.csv .

# Copy the yamcam.py script and functions
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .

# Set entrypoint
CMD ["python", "yamcam.py"]

