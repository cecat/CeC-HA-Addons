FROM python:3.9-slim

WORKDIR /usr/src/app

COPY . .

# Install dependencies using apt
RUN apt-get update && apt-get install -y \
    gnupg \
    curl \
    bash \
    && echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | tee /etc/apt/sources.list.d/coral-edgetpu.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
    && apt-get update \
    && apt-get install -y libedgetpu1-std \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Install TensorFlow Lite runtime with TPU support
RUN pip install tflite-runtime

EXPOSE 80

ENV NAME World

CMD ["python", "./yamcam-tpu.py"]

