ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache ffmpeg python3 py3-pip

# Create a virtual environment and install Python packages
RUN python3 -m venv /venv
RUN /venv/bin/pip install --upgrade pip
RUN /venv/bin/pip install --upgrade paho-mqtt PyYAML

# Copy data for add-on
COPY run.sh /
COPY get_audio_volume.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

