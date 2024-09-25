#
# YamCam - CeC August 2024
#

import time
import numpy as np
import logging
import csv
import json
from yamcam_functions import (
        set_configuration, logger,
        start_mqtt, load_model,
        set_sources, format_input_details, analyze_audio, group_scores, 
        report, set_log_level, rank_sounds
)
import yamcam_config


############# SETUP #############

#----------- PATHS -------------#
#config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'

#---------- SET UP -----------#
# read config, set logging level, and fire up MQTT

#config = set_configuration(config_path)
#set_log_level(config)
set_log_level()
#mqtt_client = start_mqtt(config)
mqtt_client = start_mqtt()

#----------- LOAD MODEL and CLASSES -------------#
### Load YAMNet model using TensorFlow Lite

load_model(model_path)

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
            report(results, mqtt_client, mqtt_topic_prefix, camera_name)

        else:
            logger.error(f"Failed to analyze audio for {camera_name}")

    time.sleep(sample_interval)

