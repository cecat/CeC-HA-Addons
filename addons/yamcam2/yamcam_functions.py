#
# yamcam_functions - Functions for yamcam2
# 
# CeC - September 2024

import subprocess
import paho.mqtt.client as mqtt
import yaml
import os
import numpy as np
import io
import logging
import json
import yamcam_config
from yamcam_config import interpreter, input_details, output_details, logger, aggregation_method, sample_interval

logger = yamcam_config.logger

#
# for heavy debug early on; relevant code commented out for the moment
#
saveWave_path = '/config/waveform.npy'
saveWave_dir = os.path.dirname(saveWave_path)


############# COMMUNICATIONS ##############

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.debug("Connected to MQTT broker")
    else:
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
        f"   Host: {mqtt_host} ;  Port: {mqtt_port}\n"
        f"   Topic Prefix: {mqtt_topic_prefix}\n"
        f"   Client ID: {mqtt_client_id}\n"
        f"   User: {mqtt_username}\n"
    )

    mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    mqtt_client.on_connect = on_connect

    try:
        mqtt_client.connect(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
        logger.debug(f"MQTT client connected successfully to {mqtt_host}:{mqtt_port}.")
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

            logger.debug(f"MQTT: {mqtt_topic_prefix}, {payload_json}")

            result = mqtt_client.publish(
                f"{mqtt_topic_prefix}",
                payload_json
            )
            result.wait_for_publish()
                                                                               
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"\n{payload_json}")
            else:      
                logger.error(f"Failed to publish MQTT message for sound types, return code: {result.rc}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")
    else:                
        logger.error("MQTT client is not connected. Skipping publish.")


############# SOUND FUNCTIONS ##############


############# ANALYZE AUDIO ##############

def analyze_audio(rtsp_url, duration=5):
    # fine-tuning parameters
    retries = 3
    max_retries = 10
    retry_delay = 2
    overlap = 0.5

    for attempt in range(retries):
        try:
            command = [
                'ffmpeg',
                '-y',
                '-rtsp_transport', 'tcp',  # Use TCP for RTSP transport
                '-i', rtsp_url,
                '-t', str(duration),
                '-map', '0:a:0',  # Select only the first audio stream (ignore video)
                '-f', 'wav',
                '-acodec', 'pcm_s16le',
                '-ar', '16000',  # Resample to 16 kHz
                '-ac', '1',
                'pipe:1'
            ]
            # log the exact command we are executing
            logger.debug(f"Execute: {command}")

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg failed with error code: {process.returncode}, stderr: {stderr.decode()}")
                raise Exception("FFmpeg failed")

            # Process the audio data using YAMNet or other analysis tools

            with io.BytesIO(stdout) as f:
                waveform = np.frombuffer(f.read(), dtype=np.int16) / 32768.0

            # Ensure waveform has the correct shape
            waveform = np.squeeze(waveform)

            # Process the full waveform in segments
            segment_length = input_details[0]['shape'][0]  # For example, 15600 samples
            step_size = int(segment_length * overlap)  # segment overlap

            all_scores = []
            for start in range(0, len(waveform) - segment_length + 1, step_size):
                segment = waveform[start:start + segment_length]
                segment = segment.astype(np.float32)

                interpreter.set_tensor(input_details[0]['index'], segment)
                interpreter.invoke()
                scores = interpreter.get_tensor(output_details[0]['index'])
                all_scores.append(scores)

            # Check if all_scores is empty before attempting to combine
            if len(all_scores) == 0:
                logger.error("No scores available for analysis. Skipping this round.")
                return None

            # Combine the scores from all segments
            # Stack all_scores into a 2D array of shape (num_segments, num_classes)
            all_scores = np.vstack(all_scores)  # Shape: (num_segments, num_classes)

            # Aggregate the scores across segments
            # config var 'aggregation_method'
            # is either max (default), mean, or sum

            if aggregation_method == 'mean':
                combined_scores = np.mean(all_scores, axis=0)
            elif aggregation_method == 'max':
                combined_scores = np.max(all_scores, axis=0)
            elif aggregation_method == 'sum':
                combined_scores = np.sum(all_scores, axis=0)
            else:
                raise ValueError(f"Unknown aggregation method: {aggregation_method}")

            return combined_scores

        except Exception as e:
            logger.error(f"Error running FFmpeg: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Implement exponential backoff
            else:
                raise  # Re-raise the exception after exhausting retries

    return None  # Return None if all attempts fail


############# COMPUTE SCORES ##############

##### Tease out the Sounds #####

    #     -  cap scores at 0.95 
    #     -  don't apply bonus if max score in group >=0.7

def rank_sounds (scores, group_classes, camera_name):

             ## get config settings
    reporting_threshold = yamcam_config.reporting_threshold
    top_k = yamcam_config.top_k
    report_k = yamcam_config.report_k
    noise_threshold = yamcam_config.noise_threshold
    class_names = yamcam_config.class_names

                # Log the scores for the top class names
    top_class_indices = np.argsort(scores)[::-1]
    top_class_indices = [i for i in top_class_indices[:top_k] if scores[i] >= noise_threshold]

    for i in top_class_indices[:top_k]:  # Log only top_k scores
        logger.debug(f"{camera_name}:{class_names[i]} {scores[i]:.2f}")

            # Calculate composite group scores
        composite_scores = group_scores(top_class_indices, class_names, [scores])
        for group, score in composite_scores:
            logger.debug(f"{camera_name}:{group} {score:.2f}")

            # Sort in descending order
        composite_scores_sorted = sorted(composite_scores, key=lambda x: x[1], reverse=True)

            # Filter and format the top class names with their scores
        results = []
        if group_classes:
            for group, score in composite_scores_sorted:
                if score >= reporting_threshold:
                    score_python_float = float(score)
                    rounded_score = round(score_python_float, 2)
                    results.append({'class': group, 'score': rounded_score})
                if len(results) >= report_k:
                    break
        else:
            for i in top_class_indices:
                score = scores[i]
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


############# COMPUTE DELAY ##############
    # -  account for sampling and processing time 
    #    (otherwise our actual interval is sampling/processing time + sample_interval
    # -  minimum zero (as many sources and/or long sample_duration could be >sample_interval)

def compute_sleep_time (sample_duration, camera_settings):

    number_of_sources = len(camera_settings)
    processing_time_per_source = 2  # Adjust as needed
    total_time_spent = number_of_sources * (sample_duration + processing_time_per_source)
    logger.debug(f"sampling/processing time is {total_time_spent}, while sample_interval is {sample_interval}")
    sleep_duration = sample_interval - total_time_spent
    sleep_duration = max(sleep_duration, 0)  # Ensure sleep_duration is not negative
    
    return sleep_duration

