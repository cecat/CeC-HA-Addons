# Pull the base image
FROM python:3.9-slim

# Log after the base image is pulled
RUN echo "Base image python:3.9-slim downloaded or cached at $(date)"

# Set the working directory
WORKDIR /app

# Insert log message: Start of system dependencies installation
RUN echo "Starting system dependencies installation at $(date)" && \
    apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/* && \
    echo "Finished system dependencies installation at $(date)"

# Insert log message: Start of Python dependencies installation
COPY requirements.txt .
RUN echo "Starting Python dependencies installation at $(date)" && \
    pip install --no-cache-dir -r requirements.txt && \
    echo "Finished Python dependencies installation at $(date)"

# Insert log message: Copying model and class map files
COPY files/yamnet.tflite .
COPY files/yamnet_class_map.csv .
RUN echo "Copied model files at $(date)"

# Insert log message: Copying Python scripts
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .
RUN echo "Copied Python scripts at $(date)"

# Set entrypoint
CMD ["python", "yamcam.py"]

