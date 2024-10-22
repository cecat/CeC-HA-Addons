FROM python:3.9-slim

WORKDIR /app

# Install system dependencies and USB utilities
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    curl \
    usbutils \
    && rm -rf /var/lib/apt/lists/*

# Manually download and install the libedgetpu package for x86_64 (amd64)
RUN wget https://packages.cloud.google.com/apt/pool/edgetpu/libedgetpu1-std_15.0-2_amd64.deb -O /tmp/libedgetpu1-std.deb \
    && dpkg -i /tmp/libedgetpu1-std.deb && rm /tmp/libedgetpu1-std.deb

# Copy the local model and Edge TPU library
COPY files/yamnet.tflite .
COPY files/yamnet_edgetpu.tflite .
COPY files/yamnet_class_map.csv .
COPY files/libedgetpu.so.1.0 /usr/lib/libedgetpu.so.1.0
RUN ln -s /usr/lib/libedgetpu.so.1.0 /usr/lib/libedgetpu.so.1

# Install TensorFlow Lite runtime and compatible NumPy version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code files
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .

# Set entrypoint
CMD ["python", "yamcam.py"]

