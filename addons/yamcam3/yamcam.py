#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#

import time
import logging
from yamcam_functions import (
        start_mqtt, analyze_audio, 
        report, rank_sounds, compute_sleep_time
)
import yamcam_config # all setup and config happens here
from yamcam_config import logger

#---- start MQTT session ----#
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

############# Main Loop #############

while True:
    for camera_name, camera_config in camera_settings.items():

        # Analyze audio from RTSP source
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
        scores = analyze_audio(rtsp_url, duration=sample_duration)

        if scores is not None:
            # Sort and rank scores, create json payload
            results = rank_sounds(scores, group_classes, camera_name)

            # Report via MQTT
            report(results, mqtt_client, camera_name)

        else:
            logger.error(f"Failed to analyze audio for {camera_name}")

    # account for sampling and processing time
    sleep_duration = compute_sleep_time(sample_duration, camera_settings)
    time.sleep(sleep_duration)

