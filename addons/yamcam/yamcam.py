import subprocess
import paho.mqtt.client as mqtt
import time
import yaml
import os
import numpy as np
import io
import logging
import tflite_runtime.interpreter as tflite
import csv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

logger.info("----------------> ")
logger.info("----------------> Add-on Started.")
logger.info("----------------> ")

# Load user config - bail if there are YAML problems
config_path = '/config/microphones.yaml'
if not os.path.exists(config_path):
    logger.error(f"Configuration file {config_path} does not exist.")
    raise FileNotFoundError(f"Configuration file {config_path} does not exist.")

try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

# Extract general parameters
try:
    general_settings = config['general']
    sample_interval = general_settings.get('sample_interval', 15)
    reporting_threshold = general_settings.get('reporting_threshold', 0.4)
    log_level = general_settings.get('log_level', 'INFO').upper()
except KeyError as e:
    logger.error(f"Missing general settings in the configuration file: {e}")
    raise

# Set logging level
log_levels = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# Use the logging level specified in the config file (default to INFO)
if log_level in log_levels:
    logger.setLevel(log_levels[log_level])
    for handler in logger.handlers:
        handler.setLevel(log_levels[log_level])
    logger.info(f"Logging level set to {log_level}")
else:
    logger.warning(f"Invalid log level {log_level} in config file. Using INFO level.")
    logger.setLevel(logging.INFO)

# Load YAMNet class map with groups
class_map_path = '/config/yamnet_class_groups.csv'
if not os.path.exists(class_map_path):
    logger.error(f"Class map file {class_map_path} does not exist.")
    raise FileNotFoundError(f"Class map file {class_map_path} does not exist.")

try:
    class_map = {}
    with open(class_map_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # skip header
        for row in reader:
            index = int(row[0])
            group = row[3]
            class_map[index] = group
except Exception as e:
    logger.error(f"Error reading class map file {class_map_path}: {e}")
    raise

# MQTT configuration and initialization code...

# Load the TFLite model
interpreter = tflite.Interpreter(model_path='/config/yamnet.tflite')
interpreter.allocate_tensors()

# Get input and output tensors
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Main loop
while True:
    for camera_name, camera_config in config['cameras'].items():
        # Fetch audio from camera and process with YAMNet...
        
        # Interpret YAMNet output
        scores = output_data
        if scores is not None:
            top_class_indices = np.argsort(scores[0])[::-1]
            results = []
            for i in top_class_indices:
                score = scores[0][i]
                if score >= reporting_threshold:
                    group = class_map.get(i, 'Unknown')
                    results.append(f"{group} ({score:.2f})")
                if len(results) >= 3:
                    break
            
            sound_types_str = ','.join(results) if results else "(none)"
            
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

