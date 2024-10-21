FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    curl

# Add Coral Edge TPU repository
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list

# Install Edge TPU runtime
RUN apt-get update && apt-get install -y libedgetpu1-std

# Clean up
RUN rm -rf /var/lib/apt/lists/*

# Install TensorFlow Lite runtime and compatible NumPy version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 

# Copy the local model and class map files
COPY files/yamnet.tflite .
COPY files/yamnet_edgetpu.tflite .
COPY files/yamnet_class_map.csv .

# Copy the script and function files
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .

# Set entrypoint
CMD ["python", "yamcam.py"]

