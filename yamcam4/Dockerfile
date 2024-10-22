FROM python:3.9-slim

WORKDIR /app

# Install system dependencies and Edge TPU runtime
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    curl \
    usbutils \
    && rm -rf /var/lib/apt/lists/*

# Add the Coral Debian package repository and install the Edge TPU runtime
RUN echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | tee /etc/apt/sources.list.d/coral-edgetpu.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
    && apt-get update \
    && apt-get install -y libedgetpu1-std \
    && rm -rf /var/lib/apt/lists/*

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

