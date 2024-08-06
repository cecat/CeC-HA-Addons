# Dockerfile for Home Assistant Addon with YAMNet TPU support

# Use an official Python runtime as a parent image
FROM python:3.9-alpine

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install bash and necessary Python packages
RUN apk update && apk add --no-cache bash \
    && pip install --no-cache-dir paho-mqtt pyyaml tensorflow tflite-runtime

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME World

# Run yamcam-tpu.py when the container launches
CMD ["python", "./yamcam-tpu.py"]

