import subprocess
import paho.mqtt.client as mqtt
import time
import yaml
import os
import tflite_runtime.interpreter as tflite
import numpy as np
import io
import logging

# Set up detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("----------------Add-on Started----------------")

# Load user configuration from /config/microphones.yaml
config_path = '/config/microphones.yaml'
default_sample_interval = 30
default_reporting_threshold = 0.5

if not os.path.exists(config_path):
    logger.error(f"Configuration file {config_path} does not exist. Using default settings.")
    config = {}
else:
    with open(config_path) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            logger.error(f"Error in configuration file: {exc}")
            config = {}

# Extract general settings from user config
general_settings = config.get('general', {})
sample_interval = general_settings.get('sample_interval', default_sample_interval)
reporting_threshold = general_settings.get('reporting_threshold', default_reporting_threshold)

# Log the general settings being used
logger.info(f"General settings: sample_interval={sample_interval}, reporting_threshold={reporting_threshold}")

# Extract MQTT settings from user config
mqtt_settings = config.get('mqtt', {})
mqtt_host = mqtt_settings.get('host')
mqtt_port = mqtt_settings.get('port')
mqtt_topic_prefix = mqtt_settings.get('topic_prefix')
mqtt_client_id = mqtt_settings.get('client_id')
mqtt_username = mqtt_settings.get('user')
mqtt_password = mqtt_settings.get('password')
mqtt_stats_interval = mqtt_settings.get('stats_interval', 60)

# Log the MQTT settings being used
logger.info(f"MQTT settings: host={mqtt_host}, port={mqtt_port}, topic_prefix={mqtt_topic_prefix}, client_id={mqtt_client_id}, user={mqtt_username}\n")

# Extract camera settings from user config
camera_settings = config.get('cameras', {})

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

# Load YAMNet model
logger.info("Load YAMNet")
interpreter = tflite.Interpreter(model_path='files/yamnet.tflite')
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.info(f"Input details: {input_details}")

# Function to analyze audio using YAMNet
def analyze_audio(rtsp_url, duration=10):
    command = [
        'ffmpeg',
        '-y',
        '-i', rtsp_url,
        '-t', str(duration),
        '-f', 'wav',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        'pipe:1'
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {stderr.decode('utf-8')}")
        logger.error(f"Verify that the RTSP feed ({rtsp_url}) is correct.")
        return None

    with io.BytesIO(stdout) as f:
        waveform = np.frombuffer(f.read(), dtype=np.int16) / 32768.0

    if waveform.shape[0] != input_details[0]['shape'][0]:
        logger.error(f"Unexpected input shape: {waveform.shape}. Expected shape: {input_details[0]['shape']}")
        return None

    interpreter.set_tensor(input_details[0]['index'], waveform.reshape(1, -1).astype(np.float32))
    interpreter.invoke()
    scores = interpreter.get_tensor(output_details[0]['index'])[0]

    top_classes = np.argsort(scores)[::-1]
    results = [(class_names[i], scores[i]) for i in top_classes if scores[i] >= reporting_threshold]
    
    for class_name, score in results:
        logger.info(f"Camera: {rtsp_url.split('@')[-1].split(':')[0]}, Class: {class_name}, Score: {score}")

    return results

# Load class names
class_names = []
with open('files/yamnet_class_map.csv', 'r') as f:
    for line in f.readlines()[1:]:
        class_names.append(line.strip().split(',')[-1])

# Main Loop
while True:
    for camera_name, camera_config in camera_settings.items():
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
        sound_types = analyze_audio(rtsp_url, duration=10)

        if sound_types is not None:
            if mqtt_client.is_connected():
                try:
                    sound_types_str = ','.join([f"{name}:{score:.2f}" for name, score in sound_types])
                    result = mqtt_client.publish(
                        f"{mqtt_topic_prefix}/{camera_name}_sound_types",
                        sound_types_str
                    )
                    result.wait_for_publish()

                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logger.info(f"Published sound types for {camera_name}: {sound_types_str}")
                    else:
                        logger.error(f"Failed to publish MQTT message for sound types, return code: {result.rc}")
                except Exception as e:
                    logger.error(f"Failed to publish MQTT message: {e}")
            else:
                logger.error("MQTT client is not connected. Skipping publish.")
        else:
            logger.error(f"Failed to analyze audio for {camera_name}")
    time.sleep(sample_interval)

