#
# YamCam - CeC August 2024
#

import time
import logging
import json
from yamcam_functions import (
        start_mqtt, load_model,
        set_sources, format_input_details, analyze_audio, group_scores, 
        report, set_log_level, rank_sounds
)
import yamcam_config # all setup and config happens here


############# SETUP #############

#---------- SET UP -----------#
# set logging level, fire up MQTT

set_log_level()
mqtt_client = start_mqtt()


#----------- PULL things we need from CONFIG -------------#
#            (see config for definitions)

             ## cameras = sound sources
camera_settings = yamcam_config.camera_settings

             ## general settings
sample_interval = yamcam_config.sample_interval
group_classes = yamcam_config.group_classes
sample_duration = yamcam_config.sample_duration
aggregation_method = yamcam_config.aggregation_method

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

    time.sleep(sample_interval)

