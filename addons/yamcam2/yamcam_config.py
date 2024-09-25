# yamcam_config.py
import yaml
import csv
import logging
import time

# File paths
config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'

###
##################### Set up Logging ################# 

# set logging to INFO and include timestamps
# user can select different logging level via /config/microphones.yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


##################### Get Configuration ################# 

try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

             ######### general settings ######## 
try:
    general_settings = config['general']
except KeyError as e:
    logger.error(f"Missing general settings in the configuration file: {e}")
    raise

log_level = general_settings.get('log_level', 'INFO').upper()
sample_interval = general_settings.get('sample_interval', 15)
group_classes = general_settings.get('group_classes', True)
sample_interval = general_settings.get('sample_interval', 15)
group_classes = general_settings.get('group_classes', True)
sample_duration = general_settings.get('sample_duration', 3)
aggregation_method = general_settings.get('aggregation_method', 'max')
log_level = general_settings.get('log_level', 'INFO').upper()
reporting_threshold = general_settings.get('reporting_threshold', 0.4)
top_k = general_settings.get('top_k', 10)
report_k = general_settings.get('report_k', 3)
noise_threshold = general_settings.get('noise_threshold', 0.1)   # undocumented for now

             ######## cameras = sound sources ######## 
try:
    camera_settings = config['cameras']
except KeyError as e:
    logger.error(f"Missing camera settings in the configuration file: {e}")
    raise

             ######## MQTT settings ########  
try:
    mqtt_settings = config['mqtt']
except KeyError as e:
    logger.error(f"Missing camera settings in the configuration file: {e}")
    raise

mqtt_topic_prefix = config['mqtt']['topic_prefix']
mqtt_host = mqtt_settings['host']
mqtt_port = mqtt_settings['port']
mqtt_topic_prefix = mqtt_settings['topic_prefix']
mqtt_client_id = mqtt_settings['client_id']
mqtt_username = mqtt_settings['user']
mqtt_password = mqtt_settings['password']


##################### Set up YAMNet Model ################# 

             ######## Load YAMNet model using TensorFlow Lite ########  

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
# else --- tpu logic here


    #----- Easy reading for debug logging -----#

def format_input_details(details):
    formatted_details = "Input Details:\n"
    for detail in details:
        formatted_details += "  -\n"
        for key, value in detail.items():
            formatted_details += f"    {key}: {value}\n"
    return formatted_details


             ######## YAMNet Class_names ########  

# build the class_names dictionary from the Yamnet class map csv

class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))
