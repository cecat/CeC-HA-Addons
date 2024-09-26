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

    global mqtt_client
    mqtt_client = mqtt.Client(client_id=mqtt_client_id)
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    mqtt_client.on_connect = on_connect

    try:
        mqtt_client.connect(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
        logger.debug(f"MQTT client connected successfully to {mqtt_host}:{mqtt_port}.")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    return mqtt_client


def report(results, camera_name):
    global mqtt_client
    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

    if mqtt_client.is_connected():
        try:
            # Build the JSON payload with camera name and results
            payload = {
                'camera_name': camera_name,
                'sound_classes': results
            }
            payload_json = json.dumps(payload)

            logger.debug(f"MQTT: {mqtt_topic_prefix}, {payload_json}")

            # Publish the payload to the appropriate topic
            result = mqtt_client.publish(
                f"{mqtt_topic_prefix}/{camera_name}",
                payload_json
            )
            result.wait_for_publish()

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published to MQTT: {payload_json}")
            else:
                logger.error(f"Failed to publish MQTT message, return code: {result.rc}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")
    else:
        logger.error("MQTT client is not connected. Skipping publish.")


# Analyzing audio waveform and handling scores

def analyze_audio_waveform(waveform, camera_name):
    logger.debug(f"Analyzing waveform for {camera_name}")

    # Check if waveform is a 1D array and has the correct length
    if waveform.ndim != 1:
        logger.error("Waveform must be a 1D array.")
        return None

    if len(waveform) != 15600:
        logger.error(f"Waveform size mismatch for analysis: {len(waveform)} != 15600")
        return None

    # Attempt to set tensor and invoke interpreter, capturing any errors
    try:
        interpreter.set_tensor(input_details[0]['index'], waveform.astype(np.float32))
        interpreter.invoke()
        scores = interpreter.get_tensor(output_details[0]['index'])
        logger.debug(f"Scores shape: {scores.shape}, Scores: {scores}")

        if scores.size == 0:
            logger.error("Scores tensor is empty.")
            return None

        # Rank and group scores, then report the results
        ranked_scores = rank_sounds(scores, yamcam_config.top_k)
        grouped_scores = group_scores(ranked_scores, yamcam_config.group_classes)
        report(camera_name, grouped_scores)

    except Exception as e:
        logger.error(f"Error during interpreter invocation: {e}")
        return None


# Ranking and grouping scores

def rank_sounds(scores, top_k):
    indices = np.argsort(-scores[0])[:top_k]
    ranked = [(class_names[i], scores[0][i]) for i in indices]
    logger.debug(f"Ranked sounds: {ranked}")
    return ranked

def group_scores(ranked_scores, group_classes):
    if group_classes:
        group_scores_dict = {}

        # Organize scores by groups
        for name, score in ranked_scores:
            group = name.split('.')[0]  # Assuming format <group>.<original_class>
            if group not in group_scores_dict:
                group_scores_dict[group] = []
            group_scores_dict[group].append(score)

        # Calculate composite scores for each group
        composite_scores = []
        for group, group_scores in group_scores_dict.items():
            max_score = max(group_scores)  # Take the maximum score in the group
            if max_score < 0.7:  # Add a boost if the score is relatively low
                composite_score = max_score + 0.05 * (len(group_scores) - 1)
            else:
                composite_score = max_score

            # Ensure score is bounded by 0.95
            composite_score = min(composite_score, 0.95)
            composite_scores.append((group, composite_score))

        logger.debug(f"Composite group scores: {composite_scores}")
        return composite_scores
    else:
        return ranked_scores


