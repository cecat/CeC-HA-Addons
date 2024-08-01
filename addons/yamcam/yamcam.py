import subprocess
import paho.mqtt.client as mqtt
import time
import yaml
import os
import tensorflow as tf
import numpy as np
import io
import logging

# Set up detailed logging
logging.basicConfig(level=logging.INFO)  # Change to INFO to reduce verbosity
logger = logging.getLogger(__name__)

logger.info("----------------Add-on Started----------------")

# Load user configuration from /config/microphones.yaml
config_path = '/config/microphones.yaml'
if not os.path.exists(config_path):
    logger.error(f"Configuration file {config_path} does not exist. Using default settings.")
    config = {}
else:
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error reading configuration file: {e}. Using default settings.")
        config = {}

# Extract general settings from user config
general_settings = config.get('general', {})
sample_interval = general_settings.get('sample_interval', 15)
reporting_threshold = general_settings.get('reporting_threshold', 0.4)

if not general_settings:
    logger.error("General settings not found in configuration file. Using default values.")
if 'sample_interval' not in general_settings:
    logger.error("Sample interval not found in configuration file. Using default value: 15 seconds.")
if 'reporting_threshold' not in general_settings:
    logger.error("Reporting threshold not found in configuration file. Using default value: 0.4.")

# Extract MQTT settings from user config
mqtt_settings = config.get('mqtt', {})
mqtt_host = mqtt_settings.get('host', 'localhost')
mqtt_port = mqtt_settings.get('port', 1883)
mqtt_topic_prefix = mqtt_settings.get('topic_prefix', 'HA/sensor')
mqtt_client_id = mqtt_settings.get('client_id', 'yamcam')
mqtt_username = mqtt_settings.get('user', 'user')
mqtt_password = mqtt_settings.get('password', 'password')
mqtt_stats_interval = mqtt_settings.get('stats_interval', 60)

if not mqtt_settings:
    logger.error("MQTT settings not found in configuration file. Using default values.")
if 'host' not in mqtt_settings:
    logger.error("MQTT host not found in configuration file. Using default value: 'localhost'.")
if 'port' not in mqtt_settings:
    logger.error("MQTT port not found in configuration file. Using default value: 1883.")
if 'topic_prefix' not in mqtt_settings:
    logger.error("MQTT topic prefix not found in configuration file. Using default value: 'HA/sensor'.")
if 'client_id' not in mqtt_settings:
    logger.error("MQTT client ID not found in configuration file. Using default value: 'yamcam'.")
if 'user' not in mqtt_settings:
    logger.error("MQTT user not found in configuration file. Using default value: 'user'.")
if 'password' not in mqtt_settings:
    logger.error("MQTT password not found in configuration file. Using default value: 'password'.")
if 'stats_interval' not in mqtt_settings:
    logger.error("MQTT stats interval not found in configuration file. Using default value: 60 seconds.")

# Log the MQTT settings being used
logger.info(f"MQTT settings: host={mqtt_host}, port={mqtt_port}, topic_prefix={mqtt_topic_prefix}, client_id={mqtt_client_id}, user={mqtt_username}\n")

# Extract camera settings from user config
camera_settings = config.get('cameras', {})

if not camera_settings:
    logger.error("Camera settings not found in configuration file. No audio sources will be analyzed.")

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
interpreter = tf.lite.Interpreter(model_path='files/yamnet.tflite')
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
        logger.error(f"FFmpeg error: {stderr.decode('utf-8')}. Verify that the RTSP feed {rtsp_url} is correct.")
        return None

    waveform = np.frombuffer(stdout, dtype=np.int16).astype(np.float32) / 32768.0
    
    if waveform.shape[0] != 15600:
        logger.error(f"Unexpected input shape: {waveform.shape}. Expected [15600].")
        return None

    interpreter.set_tensor(input_details[0]['index'], waveform)
    interpreter.invoke()
    scores = interpreter.get_tensor(output_details[0]['index'])[0]
    top_indices = np.argpartition(scores, -5)[-5:]
    top_indices = top_indices[np.argsort(scores[top_indices])][::-1]

    results = []
    for i in top_indices:
        score = scores[i]
        if score >= reporting_threshold:
            class_name = class_names[i]
            results.append((class_name, score))
            logger.info(f"Class: {class_name}, Score: {score}")

    return results

# Main Loop
while True:                             
    for camera_name, camera_config in camera_settings.items():
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
        sound_types = analyze_audio(rtsp_url, duration=10)
             
        if sound_types:
            if mqtt_client.is_connected():
                try:
                    sound_types_str = ', '.join([f"{name}: {score:.2f}" for name, score in sound_types])
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

