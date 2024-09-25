#
# Functions for YamCam add-on
# 
# CeC - September 2024

import subprocess
import paho.mqtt.client as mqtt
import yaml
import tflite_runtime.interpreter as tflite
import os
import numpy as np
import io
import logging
import json
import yamcam_config
import time

# Module-level variables
interpreter = None
input_details = None
output_details = None

#
# Basic Setup
#
saveWave_path = '/config/waveform.npy'
saveWave_dir = os.path.dirname(saveWave_path)


############# SETUP #############

# set logging to INFO and include timestamps
# config file lets user select different logging level

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


############# CONFIGURE ##############

def set_configuration(config_path):

    #----- LOAD DICTIONARY -----#
    if not os.path.exists(config_path):
        logger.error(f"Configuration file {config_path} does not exist.")
        raise FileNotFoundError(f"Configuration file {config_path} does not exist.")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Error reading YAML file {config_path}: {e}")
        raise
    return config

    #----- SET LOG LEVEL FROM CONFIG -----#

def set_log_level():
    # Map log level from string to logging constant
    log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = yamcam_config.log_level
    if log_level in log_levels:
        logger.setLevel(log_levels[log_level])
        for handler in logger.handlers:
            handler.setLevel(log_levels[log_level])
        logger.info(f"Logging level: {log_level}")
    else:
        logger.warning(f"Invalid log level {log_level} in config file. Use DEBUG, INFO, WARNING, ERROR, or CRITICAL. Defaulting to INFO.")
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)
    return


    #----- SOUND SOURCES -----#

def set_sources(config):
    try:
        camera_settings = config['cameras']
    except KeyError as e:
        logger.error(f"Missing camera settings in the configuration file: {e}")
        raise
    return camera_settings


############# COMMUNICATIONS ##############

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.debug("Connected to MQTT broker")
    else:
        logger.error("Failed to connect to MQTT broker. Check MQTT settings.")

    #----- START ME UP -----#

def start_mqtt():
    #mqtt_settings = config['mqtt']
    #mqtt_host = mqtt_settings['host']
    #mqtt_port = mqtt_settings['port']
    #mqtt_topic_prefix = mqtt_settings['topic_prefix']
    #mqtt_client_id = mqtt_settings['client_id']
    #mqtt_username = mqtt_settings['user']
    #mqtt_password = mqtt_settings['password']
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
        logger.debug("MQTT client connected successfully to {mqtt_host}:{mqtt_port}.")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    return mqtt_client  


    #----- REPORT via MQTT -----#

#def report(results, mqtt_client, mqtt_topic_prefix, camera_name):
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
                logger.info(f"{camera_name}: {payload_json}")
            else:      
                logger.error(f"Failed to publish MQTT message for sound types, return code: {result.rc}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")
    else:                
        logger.error("MQTT client is not connected. Skipping publish.")


##### SOUND and MODEL FUNCTIONS #####

    #----- LOAD INFERENCE MODEL -----#

def load_model(model_path):
    global interpreter, input_details, output_details
    # for tpu - check to see if we are using a Coral TPU
    # if no tpu
    logger.debug("Loading YAMNet model")
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    logger.debug("YAMNet model loaded. Input details: ")
    logger.debug(format_input_details(input_details))
    # tpu logic here


    #----- Easy reading for debug logging -----#

def format_input_details(details):
    formatted_details = "Input Details:\n"
    for detail in details:  
        formatted_details += "  -\n"
        for key, value in detail.items():
            formatted_details += f"    {key}: {value}\n"
    return formatted_details
                            

############# ANALYZE AUDIO ##############

def analyze_audio(rtsp_url, duration=5):
    # tuning
    retries = 3
    max_retries = 10
    retry_delay = 2
    method = yamcam_config.aggregation_method

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
            step_size = int(segment_length * 0.5)  # 50% overlap

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
            # config var 'aggregation_method' ('method' here)
            # is either max (default), mean, or sum

            if method == 'mean':
                combined_scores = np.mean(all_scores, axis=0)
            elif method == 'max':
                combined_scores = np.max(all_scores, axis=0)
            elif method == 'sum':
                combined_scores = np.sum(all_scores, axis=0)
            else:
                raise ValueError(f"Unknown aggregation method: {method}")

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
        else:
            return results


##### GROUP Composite Scores #####

    #     -  cap scores at 0.95 
    #     -  don't apply bonus if max score in group >=0.7

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

