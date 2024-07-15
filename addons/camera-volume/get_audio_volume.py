import subprocess
import paho.mqtt.client as mqtt
import time
import yaml
import os

# Set up basic logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load user configuration from /config/cameravolume.yaml

config_path = '/config/cameravolume.yaml'
if not os.path.exists(config_path):
    logger.error(f"Configuration file {config_path} does not exist.")
    raise FileNotFoundError(f"Configuration file {config_path} does not exist.")

with open(config_path) as f:
    config = yaml.safe_load(f)

# Extract MQTT settings from user config

mqtt_settings = config.get('mqtt', {})
mqtt_host = mqtt_settings.get('host')
mqtt_port = mqtt_settings.get('port')
mqtt_topic_prefix = mqtt_settings.get('topic_prefix')
mqtt_client_id = mqtt_settings.get('client_id')
mqtt_username = mqtt_settings.get('user')
mqtt_password = mqtt_settings.get('password')
mqtt_stats_interval = mqtt_settings.get('stats_interval', 60)

# Extract camera settings from user config

camera_settings = config.get('cameras', {})

def get_audio_volume(rtsp_url, duration=5):
    # ... (rest of the function remains unchanged)

# MQTT connection setup

mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
mqtt_client.username_pw_set(mqtt_username, mqtt_password)

mqtt_client.on_connect = lambda client, userdata, flags, rc: logger.info("Connected to MQTT broker") if rc == 0 else logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

try:
    mqtt_client.connect(mqtt_host, mqtt_port, 60)
    mqtt_client.loop_start()
except Exception as e:
    logger.error(f"Failed to connect to MQTT broker: {e}")


sample_interval = 10  # Sample every 10 seconds

# Main Loop

while True:
    for camera_name, camera_config in camera_settings.items():
        mean_samples = []
        max_samples = []
        for _ in range(mqtt_stats_interval // sample_interval):
            mean_volume, max_volume = get_audio_volume(camera_config['ffmpeg']['path'], duration=sample_interval)
            if mean_volume is not None:
                mean_samples.append(mean_volume)
            if max_volume is not None:
                max_samples.append(max_volume)
            time.sleep(sample_interval)

        if mean_samples and max_samples:
            average_mean_volume = sum(mean_samples) / len(mean_samples)
            average_max_volume = sum(max_samples) / len(max_samples)

            if mqtt_client.is_connected():
                try:
                    result = mqtt_client.publish(
                        f"{mqtt_topic_prefix}/{camera_name}_audio_volume_mean",
                        f"{average_mean_volume:.2f}"
                    )
                    result.wait_for_publish()

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(f"Published mean volume for {camera_name}: {average_mean_volume:.2f}")
                    else:
                        logger.error(f"Failed to publish MQTT message for mean volume, return code: {result.rc}")

                    result = mqtt_client.publish(
                        f"{mqtt_topic_prefix}/{camera_name}_audio_volume_max",
                        f"{average_max_volume:.2f}"
                    )
                    result.wait_for_publish()

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(f"Published max volume for {camera_name}: {average_max_volume:.2f}")
                    else:
                        logger.error(f"Failed to publish MQTT message for max volume, return code: {result.rc}")
                except Exception as e:
                    logger.error(f"Failed to publish MQTT message: {e}")
            else:
                logger.error("MQTT client is not connected. Skipping publish.")
