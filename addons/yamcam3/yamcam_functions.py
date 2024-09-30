#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# yamcam_functions - Functions for yamcam3
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
            payload = {
                'camera_name': camera_name,
                'sound_classes': results
            }
            payload_json = json.dumps(payload)

            logger.debug(f"{camera_name}: {mqtt_topic_prefix}, {payload_json}")

            result = mqtt_client.publish(
                f"{mqtt_topic_prefix}",
                payload_json
            )
            # Comment out for debugging
            # result.wait_for_publish()
            #
            # if result.rc == mqtt.MQTT_ERR_SUCCESS:
            #     logger.info(f"\n{payload_json}")
            # else:
            #     logger.error(f"Failed to publish MQTT message for sound types, return code: {result.rc}")
        except Exception as e:
            logger.error(f"{camera_name}: Failed to publish MQTT message: {e}")
    else:
        logger.error("MQTT client is not connected. Skipping publish.")

    # debug
    logger.debug(f"{camera_name}: debugging; just return, don't publish")


############# SOUND FUNCTIONS ##############

############# ANALYZE AUDIO STREAM ##############

# Segment settings for analyze_audio_waveform function

#segment_length = input_details[0]['shape'][0]  # YAMNet requirements
#overlap        = 0.5  # 50% overlap between segments
#step_size      = int(segment_length * overlap)  # Step size for sliding window

def analyze_audio_waveform(waveform):
    try:
        # Ensure waveform is a 1D array of float32 values between -1 and 1
        waveform = np.squeeze(waveform).astype(np.float32)
        if waveform.ndim != 1:
            logger.error(f"{self.camera_name}: Waveform must be a 1D array.")
            return None

        # Invoke the model
        try:
            # Set input tensor and invoke interpreter
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()

            # Get output scores; convert to a copy to avoid holding internal references
            scores = np.copy(interpreter.get_tensor(output_details[0]['index']))  

            if scores.size == 0:
                logger.error(f"{self.camera_name}: No scores available to analyze.")
                return None

        except Exception as e:
            logger.error(f"{self.camera_name}: Error during interpreter invocation: {e}")
            return None

        return scores

    except Exception as e:
        logger.error(f"{self.camera_name}: Error during waveform analysis: {e}")
        return None



############# COMPUTE SCORES ##############

##### Tease out the Sounds #####

    #     -  cap scores at 0.95 
    #     -  don't apply bonus if max score in group >=0.7

def rank_sounds(scores, use_groups, camera_name):
    ## get config settings
    reporting_threshold = yamcam_config.reporting_threshold
    top_k = yamcam_config.top_k
    report_k = yamcam_config.report_k
    noise_threshold = yamcam_config.noise_threshold
    class_names = yamcam_config.class_names

    # Count the number of classes with non-zero scores
    non_zero_scores_count = np.count_nonzero(scores[0] > 0)
    logger.debug(f"{camera_name}: Number of classes w scores !0: {non_zero_scores_count}")

  
    # Log the scores for the top class names
    # Pair each score with its corresponding class index
    class_score_pairs = [(i, scores[0][i].flatten()[0]) for i in range(len(scores[0]))]

    # Sort the pairs by score in descending order
    sorted_class_score_pairs = sorted(class_score_pairs, key=lambda x: x[1], reverse=True)

    # Now, filter the top_k class indices that have scores above noise_threshold
    top_class_indices = [
        i for i, score in sorted_class_score_pairs[:top_k] 
        if score >= noise_threshold
    ]

    logger.debug(f"{camera_name}: {len(top_class_indices)} classes > {noise_threshold}.")

    # Log the scores for the top_k classes
    for i in top_class_indices[:top_k]:
        logger.debug(f"{camera_name}: {class_names[i]} {scores[0][i]:.2f}")

    # Calculate composite group scores
    composite_scores = group_scores(top_class_indices, class_names, [scores])
    for group, score in composite_scores:
        logger.debug(f"{camera_name}: {group} {score:.2f}")

    # Sort in descending order
    composite_scores_sorted = sorted(composite_scores, key=lambda x: x[1], reverse=True)

    # Filter and format the top class names with their scores
    results = []
    if use_groups:
        for group, score in composite_scores_sorted:
            if score >= reporting_threshold:
                score_python_float = float(score)
                rounded_score = round(score_python_float, 2)
                results.append({'class': group, 'score': rounded_score})
            if len(results) >= report_k:
                break
    else:
        for i in top_class_indices:
            score = scores[0][i]
            if score >= reporting_threshold:
                score_python_float = float(score)
                rounded_score = round(score_python_float, 2)
                results.append({'class': class_names[i], 'score': rounded_score})
            if len(results) >= report_k:
                break

    if not results:
        results = [{'class': '(none)', 'score': 0.0}]

    return results



##### GROUP Composite Scores #####
    # -  cap scores at 0.95 
    # -  don't apply bonus if max score in group >=0.7

def group_scores(top_class_indices, class_names, scores):
    group_scores_dict = {}

    for i in top_class_indices[:10]:
        class_name = class_names[i]
        score = scores[0][i]
        group = class_name.split('.')[0]

        if group not in group_scores_dict:
            group_scores_dict[group] = []
        group_scores_dict[group].append(score)

    composite_scores = []
    for group, group_scores in group_scores_dict.items():
        max_score = max(group_scores)
        if max_score < 0.7:
            composite_score = max_score + 0.05 * len(group_scores)
        else:
            composite_score = max_score

        composite_score = min(composite_score, 0.95)
        composite_scores.append((group, composite_score))

    return composite_scores

