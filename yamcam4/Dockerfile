FROM python:3.9-slim

WORKDIR /app

# Install system dependencies in steps to isolate any issues
RUN apt-get update && apt-get install -y ffmpeg || cat /var/log/apt/term.log
RUN apt-get install -y libsndfile1 || cat /var/log/apt/term.log
RUN apt-get install -y wget curl || cat /var/log/apt/term.log
RUN apt-get install -y libedgetpu1-std || cat /var/log/apt/term.log

# Clean up
RUN rm -rf /var/lib/apt/lists/*

# Install TensorFlow Lite runtime and compatible NumPy version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 

# Copy the local model and class map files from the subdirectory
COPY files/yamnet.tflite .
COPY files/yamnet_edgetpu.tflite .
COPY files/yamnet_class_map.csv .

# Copy the yamcam.py script and functions
COPY yamcam.py .
COPY yamcam_functions.py .
COPY yamcam_config.py .
COPY camera_audio_stream.py .
COPY yamcam_supervisor.py .

# Set entrypoint
CMD ["python", "yamcam.py"]

