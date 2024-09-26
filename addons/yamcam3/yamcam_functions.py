#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# yamcam_functions - Functions for yamcam2
# 

import numpy as np
import logging
import paho.mqtt.client as mqtt
import yamcam_config

logger = yamcam_config.logger
interpreter = yamcam_config.interpreter
input_details = yamcam_config.input_details
output_details = yamcam_config.output_details
class_names = yamcam_config.class_names
mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

# MQTT Client Setup
mqtt_client = None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.debug("Connected to MQTT Broker successfully.")
    else:
        logger.error(f"Failed to connect to MQTT Broker with return code {rc}")

def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(client_id=yamcam_config.mqtt_client_id)
    mqtt_client.username_pw_set(yamcam_config.mqtt_username, yamcam_config.mqtt_password)
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(yamcam_config.mqtt_host, yamcam_config.mqtt_port, 60)
    mqtt_client.loop_start()

def report(camera_name, message):
    global mqtt_client
    if mqtt_client:
        topic = f"{mqtt_topic_prefix}/{camera_name}"
        mqtt_client.publish(topic, message)
        logger.debug(f"Published message to {topic}: {message}")

# Analyzing audio waveform and handling scores
def analyze_audio_waveform(camera_name, raw_audio):
    try:
        waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
        waveform = np.squeeze(waveform)
        logger.debug(f"Waveform length: {len(waveform)}, Segment shape: {waveform.shape}")

        if len(waveform) == 15600:
            interpreter.set_tensor(input_details[0]['index'], waveform.astype(np.float32))
            interpreter.invoke()
            scores = interpreter.get_tensor(output_details[0]['index'])
            logger.debug(f"Scores shape: {scores.shape}, Scores: {scores}")

            ranked_scores = rank_sounds(scores, yamcam_config.top_k)
            grouped_scores = group_scores(ranked_scores, yamcam_config.group_classes)
            report(camera_name, grouped_scores)

        else:
            logger.error(f"Waveform size mismatch for analysis: {len(waveform)} != 15600")
    except Exception as e:
        logger.error(f"Error during waveform analysis for {camera_name}: {e}")

# Ranking and grouping scores
def rank_sounds(scores, top_k):
    indices = np.argsort(-scores[0])[:top_k]
    ranked = [(class_names[i], scores[0][i]) for i in indices]
    logger.debug(f"Ranked sounds: {ranked}")
    return ranked

def group_scores(ranked_scores, group_classes):
    if group_classes:
        grouped = {}
        for name, score in ranked_scores:
            group = name.split('.')[0]  # Assuming format <group>.<original_class>
            grouped[group] = grouped.get(group, 0) + score
        logger.debug(f"Grouped scores: {grouped}")
        return grouped
    else:
        return ranked_scores

