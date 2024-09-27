#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#

#
# yamcam3 (streaming) - CeC September 2024
#

import time
import logging
from yamcam_functions import (
        start_mqtt, analyze_audio_waveform,
        report, rank_sounds
)
import yamcam_config  # all setup and config happens here
from yamcam_config import logger
from camera_audio_stream import CameraAudioStream  # Ensure this import is added

#---- Start MQTT session ----#
mqtt_client = start_mqtt()

#----------- PULL things we need from CONFIG -------------#
#            (see config for definitions)
             ## cameras = sound sources
camera_settings = yamcam_config.camera_settings
             ## general settings
group_classes = yamcam_config.group_classes
sample_duration = yamcam_config.sample_duration
             ## MQTT settings
mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

#----------- for streaming -------------------------------#

def analyze_callback(camera_name, waveform):
    scores = analyze_audio_waveform(waveform)
    if scores is not None:
        results = rank_sounds(scores, group_classes, camera_name)
        report(results, mqtt_client, camera_name)
        #DEBUG
        time.sleep (2)   # just for now while debugging
    else:
        logger.error(f"Failed to analyze audio for {camera_name}")

############# Main #############

# Create and start streams for each camera
streams = []
for camera_name, camera_config in camera_settings.items():
    rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
    stream = CameraAudioStream( camera_name, rtsp_url)
    stream.start()
    streams.append(stream)

# Keep the main thread alive
try:
    while True:
        time.sleep(1)  # Sleep to keep the main thread running
except KeyboardInterrupt:
    logger.info("Stopping all audio streams...")
    for stream in streams:
        stream.stop()
    logger.info("All audio streams stopped. Exiting.")

