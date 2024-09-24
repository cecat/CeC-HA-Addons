#
# YamCam - CeC August 2024
#

import time
import numpy as np
import logging
import csv
import json
from yamcam_functions import (
        set_configuration, log_levels, logger,
        start_mqtt, load_model,
        set_sources, format_input_details, analyze_audio, group_scores, 
        report, set_log_level
)


############# SETUP #############

#----------- PATHS -------------#
config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'

#---------- SET UP -----------#
# read config, set logging level, and fire up MQTT

config = set_configuration(config_path)
set_log_level(config)
mqtt_client = start_mqtt(config)

#----------- LOAD MODEL and CLASSES -------------#
### Load YAMNet model using TensorFlow Lite

load_model(model_path)

# build the class_names dictionary from the Yamnet class map csv

class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))


#----------- PULL things we need from CONFIG -------------#
#            (see config for definitions)

             ## cameras = sound sources
camera_settings = set_sources(config)

             ## general settings
general_settings = config['general']
sample_interval = general_settings.get('sample_interval', 15)
group_classes = general_settings.get('group_classes', True)
reporting_threshold = general_settings.get('reporting_threshold', 0.4)
sample_duration = general_settings.get('sample_duration', 3)
top_k = general_settings.get('top_k', 10)
report_k = general_settings.get('report_k', 3)
aggregation_method = general_settings.get('aggregation_method', 'max')
sample_duration = general_settings.get('sample_duration', 3)
noise_threshold = general_settings.get('noise_threshold', 0.1)   # undocumented for now

             ## MQTT settings
mqtt_topic_prefix = config['mqtt']['topic_prefix']



############# Main Loop #############

while True:
    for camera_name, camera_config in camera_settings.items():

        # Analyze audio from RTSP source
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
        scores = analyze_audio(rtsp_url, duration=sample_duration, method=aggregation_method)

        if scores is not None:
            # Sort and rank scores
            results = rankings(scores, group_classes)

            # Report via MQTT
            report(results, mqtt_client, mqtt_topic_prefix, camera_name)

        else:
            logger.error(f"Failed to analyze audio for {camera_name}")

    time.sleep(sample_interval)

