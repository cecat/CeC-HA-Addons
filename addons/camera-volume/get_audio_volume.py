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


# Build the ffmpeg command(s) and parse its output

def get_audio_volume(rtsp_url, duration=5):
    command = [
        'ffmpeg',
        '-use_wallclock_as_timestamps', '1',
        '-i', rtsp_url,
        '-vn',
        '-af', 'volumedetect',
        '-t', str(duration),
        '-f', 'null',
        '/dev/null'
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr_output = result.stderr

    mean_volume = None
    max_volume = None

    for line in stderr_output.split('\n'):
        if 'mean_volume' in line:
            try:
                mean_volume = float(line.split()[-2])
            except ValueError:
                logger.error("Error parsing mean_volume")
        if 'max_volume' in line:
            try:
                max_volume = float(line.split()[-2])
            except ValueError:
                logger.error("Error parsing max_volume")

    return mean_volume, max_volume


# MQTT connection setup

mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
mqtt_client.username_pw_set(mqtt_username, mqtt_password)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error("Failed to connect to MQTT broker")

mqtt_client.on_connect = on_connect

try:
    mqtt_client.connect(mqtt_host, mqtt_port, 60)
    mqtt_client.loop_start()
except Exception as e:
    logger.error(f"Failed to connect to MQTT broker: {e}")

# Sample interval could be set in config but I think 10s is a reasonable start, as
# each sample is 5s duration so we are monitoring 50% of the time (ok maybe       
# that is more than we need,  so I'll move these values in a                
# future version to the user config file but for now trying to keep things simple).
                                                                                           
sample_interval = 10  # Sample every 10 seconds       

# Main Loop

while True:
    for camera_name, camera_config in camera_settings.items():
        mean_samples = []
        max_samples = []
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path'] 
        for _ in range(mqtt_stats_interval // sample_interval):
            mean_volume, max_volume = get_audio_volume(rtsp_url, duration=sample_interval)

            if mean_volume is not None:
                mean_samples.append(mean_volume)
            if max_volume is not None:
                max_samples.append(max_volume)
            time.sleep(sample_interval)

	# we average the mean and max volume samples over the sample_interval reporting period,
        # then we report to HASS via mqtt

        if mean_samples and max_samples:
            average_mean_volume = sum(mean_samples) / len(mean_samples)
            average_max_volume = sum(max_samples) / len(max_samples)

            if mqtt_client.is_connected():
                try:
                    result = mqtt_client.publish(
                        "{}/{}_audio_volume_mean".format(mqtt_topic_prefix, camera_name),
                        "{:.2f}".format(average_mean_volume)
                    )
                    result.wait_for_publish()

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(f"Published mean volume for {camera_name}: {average_mean_volume:.2f}")
                    else:
                        logger.error(f"Failed to publish MQTT message for mean volume, return code: {result.rc}")

                    result = mqtt_client.publish(
                        "{}/{}_audio_volume_max".format(mqtt_topic_prefix, camera_name),
                        "{:.2f}".format(average_max_volume)
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

