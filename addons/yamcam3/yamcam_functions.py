#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# yamcam_functions.py - Functions for yamcam3
# 

import time
import subprocess
import paho.mqtt.client as mqtt
import yaml
import os
import numpy as np
import io
import logging
import json
import yamcam_config
from yamcam_config import interpreter, input_details, output_details, logger

logger = yamcam_config.logger

#
# for heavy debug early on; relevant code commented out for the moment
#
saveWave_path = '/config/waveform.npy'
saveWave_dir = os.path.dirname(saveWave_path)


############# COMMUNICATIONS ##############

def on_connect(client, userdata, flags, rc, properties=None):
    #if rc == 0:
    #    logger.debug("Connected to MQTT broker")
    #else:
    if rc != 0:
        logger.error("Failed to connect to MQTT broker. Check MQTT settings.")

    #----- START ME UP -----#

def start_mqtt():
    mqtt_host = yamcam_config.mqtt_host
    mqtt_port = yamcam_config.mqtt_port
    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix
    mqtt_client_id = yamcam_config.mqtt_client_id
    mqtt_username = yamcam_config.mqtt_username
    mqtt_password = yamcam_config.mqtt_password
        
    logger.debug(
        f"MQTT Settings:\n"
        f"   Host: {mqtt_host} ; Port: {mqtt_port}\n"
        f"   Topic Prefix: {mqtt_topic_prefix} ; Client ID: {mqtt_client_id} ; User: {mqtt_username}."
    )

    mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    mqtt_client.on_connect = on_connect

    try:
        mqtt_client.connect(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
        logger.info(f"MQTT client connected to {mqtt_host}:{mqtt_port}.")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    return mqtt_client  


    #----- REPORT via MQTT -----#

def report(results, mqtt_client, camera_name):

    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

    if mqtt_client.is_connected():
        try:
            formatted_results = [{'class': r['class'], 'score': float(f"{r['score']:.2f}")} for r in results]

            payload = {
                'camera_name': camera_name,
                'sound_classes': formatted_results
            }

            payload_json = json.dumps(payload)

            logger.info(f"{camera_name}: {mqtt_topic_prefix}, {payload_json}")

            result = mqtt_client.publish(
                f"{mqtt_topic_prefix}",
                payload_json
            )
            # Comment out for debugging
             result.wait_for_publish()
            
             if result.rc == mqtt.MQTT_ERR_SUCCESS:
                 logger.info(f"\n{payload_json}")
             else:
                 logger.error(f"Failed to publish MQTT message for sound types, return code: {result.rc}")
        except Exception as e:
            logger.error(f"{camera_name}: Failed to publish MQTT message: {e}")
    else:
        logger.error("MQTT client is not connected. Skipping publish.")

    # debug
    #logger.info(f"{camera_name}: debugging; just return, don't publish")


############# SOUND FUNCTIONS ##############

############# ANALYZE AUDIO STREAM ##############

# Segment settings for analyze_audio_waveform function

#segment_length = input_details[0]['shape'][0]  # YAMNet requirements
#overlap        = 0.5  # 50% overlap between segments
#step_size      = int(segment_length * overlap)  # Step size for sliding window

#def analyze_audio_waveform(waveform, camera_name):
def analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details):

    try:
        # Ensure waveform is a 1D array of float32 values between -1 and 1
        waveform = np.squeeze(waveform).astype(np.float32)
        if waveform.ndim != 1:
            logger.error(f"{camera_name}: Waveform must be a 1D array.")
            return None

        # Invoke the model
        try:
            # Set input tensor and invoke interpreter
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()

            # Get output scores; convert to a copy to avoid holding internal references
            scores = np.copy(interpreter.get_tensor(output_details[0]['index']))  

            if scores.size == 0:
                logger.error(f"{camera_name}: No scores available to analyze.")
                return None

        except Exception as e:
            logger.error(f"{camera_name}: Error during interpreter invocation: {e}")
            return None

        return scores

    except Exception as e:
        logger.error(f"{camera_name}: Error during waveform analysis: {e}")
        return None



############# COMPUTE SCORES ##############

##### Tease out the Sounds #####
def rank_sounds(scores, use_groups, camera_name):
    # Get config settings
    reporting_threshold = yamcam_config.reporting_threshold
    top_k = yamcam_config.top_k
    noise_threshold = yamcam_config.noise_threshold
    class_names = yamcam_config.class_names

    # Log shape of scores array for debugging
    #logger.debug(f"{camera_name}: Shape of scores array: {scores.shape}")

    # Step 1: Filter out scores below noise_threshold, keeping index for name mapping
    filtered_scores = [
        (i, score) for i, score in enumerate(scores[0]) if score >= noise_threshold
    ]
    #logger.debug(f"{camera_name}: {len(filtered_scores)} classes above noise_threshold.")

    # If no scores are above noise threshold, return early
    if not filtered_scores:
        return [{'class': '(none)', 'score': 0.0}]

    # Step 2: Group classes based on their grouping (before the first period '.')
    group_scores_dict = group_scores_by_prefix(filtered_scores, class_names)

    # Step 3: Calculate composite scores for each group
    composite_scores = calculate_composite_scores(group_scores_dict)

    # Step 4: Sort composite scores in descending order
    sorted_composite_scores = sorted(composite_scores, key=lambda x: x[1], reverse=True)

    # Step 5: Filter top_k groups and prepare results
    results = []
    for group, score in sorted_composite_scores[:top_k]:
        if score >= reporting_threshold:
            results.append({'class': group, 'score': float(round(score, 2))})

    # If no results meet the reporting threshold, return (none)
    if not results:
        results = [{'class': '(none)', 'score': 0.0}]

    return results


def group_scores_by_prefix(filtered_scores, class_names):
    """
    Group scores by their prefix (e.g., 'music.*'), and keep track of the individual class scores.
    """
    group_scores_dict = {}

    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]  # Get the group prefix before the first period '.'

        if group not in group_scores_dict:
            group_scores_dict[group] = []

        group_scores_dict[group].append(score)

    return group_scores_dict


def calculate_composite_scores(group_scores_dict):
    """
    Calculate composite scores for each group based on the specified rules:
    - If max score in group is > 0.7, use it.
    - Otherwise, max score + 0.05 * number of classes in the group (up to a max of 0.95).
    """
    composite_scores = []

    for group, scores in group_scores_dict.items():
        max_score = max(scores)
        if max_score > 0.7:
            composite_score = max_score
        else:
            composite_score = min(max_score + 0.05 * len(scores), 0.95)

        composite_scores.append((group, composite_score))

    return composite_scores

