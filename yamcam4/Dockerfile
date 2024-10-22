FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    curl

# Use the new method for adding the Coral Edge TPU key and repository
RUN mkdir -p /usr/share/keyrings && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | tee /usr/share/keyrings/coral-edgetpu-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/coral-edgetpu-archive-keyring.gpg] https://packages.cloud.google.com/apt coral-edgetpu-stable main" | tee /etc/apt/sources.list.d/coral-edgetpu.list

# Update and install the Edge TPU runtime
RUN apt-get update && apt-get install -y libedgetpu1-std

# Clean up
RUN rm -rf /var/lib/apt/lists/*

# Set the library path for Edge TPU
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/lib

# Install TensorFlow Lite runtime and compatible NumPy version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the local model and class map files
COPY files/yamnet.tflite .
COPY files/yamnet_edgetpu.tflite .
COPY files/yamnet_class_map.csv .

# Copy the Python scripts
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .

# Set entrypoint
CMD ["python", "yamcam.py"]

