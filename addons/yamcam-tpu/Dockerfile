# Dockerfile for Home Assistant Addon with YAMNet TPU support

# Use an official Python runtime as a parent image
FROM python:3.9-alpine

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Log the current environment and install Python dependencies specified in requirements.txt
RUN echo "Current Environment:" && env \
    && echo "Installing bash" \
    && apk add --no-cache bash \
    && echo "Installing Python dependencies" \
    && pip install --no-cache-dir -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME World

# Run yamcam-tpu.py when the container launches
CMD ["python", "./yamcam-tpu.py"]

