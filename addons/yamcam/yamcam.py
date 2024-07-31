import subprocess
import paho.mqtt.client as mqtt
import time
import yaml
import os
import numpy as np
import io
import logging
import tflite_runtime.interpreter as tflite

# Set up detailed logging
logging.basicConfig(level=logging.INFO)  # Change to INFO to reduce verbosity
logger = logging.getLogger(__name__)

logger.info("----------------Add-on Started.----------------")

# Load user configuration from /config/microphones.yaml
config_path = '/config/microphones.yaml'
if not os.path.exists(config_path):
    logger.error(f"Configuration file {config_path} does not exist.")
    raise FileNotFoundError(f"Configuration file {config_path} does not exist.")

with open(config_path) as f:
    config = yaml.safe_load(f)

# Extract general parameters from user config
general_settings = config.get('general', {})
sample_interval = general_settings.get('sample_interval', 15)
reporting_threshold = general_settings.get('reporting_threshold', 0.4)

# Extract MQTT settings from user config
mqtt_settings = config.get('mqtt', {})
mqtt_host = mqtt_settings.get('host')
mqtt_port = mqtt_settings.get('port')
mqtt_topic_prefix = mqtt_settings.get('topic_prefix')
mqtt_client_id = mqtt_settings.get('client_id')
mqtt_username = mqtt_settings.get('user')
mqtt_password = mqtt_settings.get('password')
mqtt_stats_interval = mqtt_settings.get('stats_interval', 30)

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

# Load YAMNet model using TensorFlow Lite
logger.info("Load YAMNet")
interpreter = tflite.Interpreter(model_path="yamnet.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.info(f"Input details: {input_details}")
class_names = [name.strip('"') for name in np.loadtxt('yamnet_class_map.csv', delimiter=',', dtype=str, skiprows=1, usecols=2)]

# Function to analyze audio using YAMNet
def analyze_audio(rtsp_url, duration=10, retries=3):
    for attempt in range(retries):
        command = [
            'ffmpeg',
            '-y',
            '-i', rtsp_url,
            '-t', str(duration),
            '-f', 'wav',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',  # Resample to 16 kHz
            '-ac', '1',
            'pipe:1'
        ]
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            with io.BytesIO(stdout) as f:
                waveform = np.frombuffer(f.read(), dtype=np.int16) / 32768.0

            # Normalize the volume
            waveform = waveform / np.max(np.abs(waveform))

            # Ensure the waveform is reshaped to match the expected input shape
            expected_length = input_details[0]['shape'][0]
            if waveform.shape[0] > expected_length:
                waveform = waveform[:expected_length]
            elif waveform.shape[0] < expected_length:
                padding = np.zeros(expected_length - waveform.shape[0], dtype=np.float32)
                waveform = np.concatenate((waveform, padding))

            waveform = waveform.astype(np.float32)
            
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()
            scores = interpreter.get_tensor(output_details[0]['index'])
            
            return scores
        
        logger.error(f"FFmpeg error (attempt {attempt + 1}/{retries}): {stderr.decode('utf-8')}")
        if "No route to host" in stderr.decode('utf-8'):
            logger.error(f"Verify that the RTSP feed '{rtsp_url}' is correct.")
        time.sleep(5)  # Wait a bit before retrying

    return None  # Return None if all attempts fail

# Main Loop
while True:                             
    for camera_name, camera_config in camera_settings.items():
        rtsp_url = camera_config['ffmpeg']['inputs'][0]['path']
        scores = analyze_audio(rtsp_url, duration=10)
             
        if scores is not None:
            # Log the scores for the top class names
            top_class_indices = np.argsort(scores[0])[::-1]
            for i in top_class_indices[:10]:  # Log top 10 scores for better insight
                logger.info(f"Camera: {camera_name}, Class: {class_names[i]}, Score: {scores[0][i]}")

            # Filter and format the top class names with their scores
            results = []
            for i in top_class_indices:
                score = scores[0][i]
                if score >= reporting_threshold:  # Use reporting_threshold from config
                    results.append(f"{class_names[i]} ({score:.2f})")
                if len(results) >= 3:
                    break

            sound_types_str = ','.join(results)

            if mqtt_client.is_connected():
                try:
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

