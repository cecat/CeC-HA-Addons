#
# yamcam3 - CeC - September 2024
# yamcam_config.py # config and setup for yamcam
#

import yaml
import csv
import logging
import tflite_runtime.interpreter as tflite


# File paths

config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'

##################### Set up Logging ################# 

# set logging to INFO and include timestamps
# user can select different logging level via /config/microphones.yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

logger.info("\n-----------> YamCam3 STARTING <-----------  \n")

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

log_level            = general_settings.get('log_level', 'INFO').upper()
noise_threshold      = general_settings.get('noise_threshold', 0.1)   
default_min_score    = general_settings.get('default_min_score', 0.5)
top_k                = general_settings.get('top_k', 10)
ffmpeg_debug         = general_settings.get('ffmpeg_debug', False)

if not (0.0 <= default_min_score <= 1.0):
    logger.warning(f"Invalid default_min_score '{defult_min_score}'"
                    "Should be between 0.0 and 1.0. Defaulting to 0.5."
    )
    default_min_score = 0.5

if not (0.0 <= noise_threshold <= 1.0):
    logger.warning(f"Invalid noise_threshold '{noise_threshold}'"
                    "Should be between 0.0 and 1.0. Defaulting to 0.1."
    )
    noise_threshold = 0.1
        
             ######## Sound Event Detection Settings ######## 
try:
    events_settings = config['events']
except KeyError:
    logger.debug("Missing events settings in the configuration file. Using default values.")
    events_settings = {
        'window_detect': 5,  # Default value
        'persistence': 3,    # Default value
        'decay': 15          # Default value
    }

window_detect = events_settings.get('window_detect', 5)
persistence = events_settings.get('persistence', 3)
decay = events_settings.get('decay', 15)

             ######## Sounds to Track and Filters/thresholds######## 
try:
    sounds = config['sounds']
except KeyError:
    logger.debug("Missing sounds settings in the configuration file. Using default values.")

sounds_to_track = sounds.get('track', [])
sounds_filters = sounds.get('filters', {})
# Validate min_score values
for group, settings in sounds_filters.items():
    min_score = settings.get('min_score')
    if not (0.0 <= min_score <= 1.0):
        logger.warning(f"Invalid min_score '{min_score}' for group '{group}'."
                        "Should be between 0.0 and 1.0. Defaulting to default_min_score."
        )
        settings['min_score'] = default_min_score 


             ######## cameras = sound sources ######## 
try:
    camera_settings  = config['cameras']
except KeyError as e:
    logger.error(f"Missing camera settings in the configuration file: {e}")
    raise


             ######## MQTT settings ########  
try:
    mqtt_settings = config['mqtt']
except KeyError as e:
    logger.error(f"Missing mqtt settings in the configuration file: {e}")
    raise

mqtt_host            = mqtt_settings['host']
mqtt_port            = mqtt_settings['port']
mqtt_topic_prefix    = mqtt_settings['topic_prefix']
mqtt_client_id       = mqtt_settings['client_id'] + "3" #yamcam version 3
mqtt_username        = mqtt_settings['user']
mqtt_password        = mqtt_settings['password']

             ######### Set Log Level ######## 

log_levels = {
    'DEBUG'    : logging.DEBUG,
    'INFO'     : logging.INFO,
    'WARNING'  : logging.WARNING,
    'ERROR'    : logging.ERROR,
    'CRITICAL' : logging.CRITICAL
}
if log_level in log_levels:
    logger.setLevel(log_levels[log_level])
    for handler in logger.handlers:
        handler.setLevel(log_levels[log_level])
    logger.info(f"Logging level: {log_level}")
else:
    logger.warning(f"Invalid log level {log_level}; Defaulting to INFO.")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        handler.setLevel(logging.INFO)

##################### Set up YAMNet Model ################# 

             ######## Easy reading for debug logging ########

def format_input_details(details):
    formatted_details = "Input Details:\n"
    for detail in details:
        formatted_details += "  -\n"
        for key, value in detail.items():
            formatted_details += f"    {key}: {value}\n"
    return formatted_details

             ######## Load YAMNet model using TensorFlow Lite ########  

# todo: for tpu - check to see if we are using a Coral TPU
# if no tpu
logger.debug("Loading YAMNet model")
interpreter    = tflite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.debug("YAMNet model loaded.")
logger.debug(format_input_details(input_details))
# else --- tpu logic here

             ######## YAMNet Class_names ########  

# build the class_names dictionary from the Yamnet class map csv

class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))

