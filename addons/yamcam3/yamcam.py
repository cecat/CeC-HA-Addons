#
# yamcam.py - CeC September 2024
#
#
# yamcam3 (streaming) - CeC September 2024
#

import time
import logging
from yamcam_functions import (
        start_mqtt, analyze_audio_waveform,
        report, rank_sounds, set_mqtt_client, update_sound_window
)
import yamcam_config  # all setup and config happens here
from yamcam_config import logger
from camera_audio_stream import CameraAudioStream  # Ensure this import is added

#----- Initialize MQTT client ---#
mqtt_client = start_mqtt()
set_mqtt_client(mqtt_client)

#---- Start MQTT session ----#
mqtt_client = start_mqtt()

#----------- PULL things we need from CONFIG -------------#
#            (see config for definitions)
             ## cameras = sound sources
camera_settings = yamcam_config.camera_settings
             ## general settings
use_groups = yamcam_config.use_groups
             ## MQTT settings
mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

#----------- Hub for sound stream analysis within each thread -----------#

def analyze_callback(camera_name, waveform, interpreter, input_details, output_details):
    scores = analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details)

    if scores is not None:
        results = rank_sounds(scores, use_groups, camera_name)
        detected_sounds = [result['class'] for result in results if result['class'] in yamcam_config.sounds_to_track]
        update_sound_window(camera_name, detected_sounds)
    else:
        logger.error(f"FAILED to analyze audio: {camera_name}")


############# Main #############

# Create and start streams for each camera

streams = []
for camera_name, camera_config in camera_settings.items():
    rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
    logger.debug(f"Creating CameraAudioStream: {camera_name}: {rtsp_url}")
    stream = CameraAudioStream( camera_name, rtsp_url, analyze_callback)
    stream.start()
    streams.append(stream)

# Keep the main thread alive
try:
    while True:
        time.sleep(1)  # Sleep to keep the main thread running
except KeyboardInterrupt:
    logger.info("******------> STOPPING ALL audio streams...")
    for stream in streams:
        stream.stop()
    logger.info("All audio streams stopped. Exiting.")

