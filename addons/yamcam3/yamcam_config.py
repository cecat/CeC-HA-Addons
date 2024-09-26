#
# yamcam3 - CeC - September 2024
# yamcam_config.py - Configuration and setup for YamCam
#

import yaml
import logging
import csv
import tflite_runtime.interpreter as tflite

# File paths
config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

logger.info("\n-----------> YamCam3 STARTING <-----------  \n")

# Load Configuration
try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

# General settings
general_settings = config.get('general', {})
log_level = general_settings.get('log_level', 'INFO').upper()
top_k = general_settings.get('top_k', 10)
report_k = general_settings.get('report_k', 3)
reporting_threshold = general_settings.get('reporting_threshold', 0.3)
group_classes = general_settings.get('group_classes', True)
noise_threshold = general_settings.get('noise_threshold', 0.1)

# Set Log Level
log_levels = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
logger.setLevel(log_levels.get(log_level, logging.INFO))

# MQTT settings
mqtt_settings = config.get('mqtt', {})
mqtt_host = mqtt_settings.get('host', 'localhost')
mqtt_port = mqtt_settings.get('port', 1883)
mqtt_topic_prefix = mqtt_settings.get('topic_prefix', 'yamcam/sounds')
mqtt_client_id = mqtt_settings.get('client_id', 'yamcam')
mqtt_username = mqtt_settings.get('user', '')
mqtt_password = mqtt_settings.get('password', '')

# Load YAMNet model
logger.debug("Loading YAMNet model")
interpreter = tflite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.debug("YAMNet model loaded.")

# Load class names from class map CSV
class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))

# Camera settings
camera_settings = config.get('cameras', {})

