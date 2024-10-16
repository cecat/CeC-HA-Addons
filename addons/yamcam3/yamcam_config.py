#
# yamcam3 - CeC - October 2024
# yamcam_config.py 
#

import yaml
import csv
import logging
import tflite_runtime.interpreter as tflite
import time
import threading
import os
from datetime import datetime

# File paths

config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'
log_dir = '/media/yamcam'
sound_log_dir = '/media/yamcam'

# Global shutdown event
shutdown_event = threading.Event()

#                                              #
### ---------- SET UP LOGGING  --------------###
#                                              #

     # -------- MAKE SURE THE LOG DIRECTORY EXISTS
def check_for_log_dir():
    try:
        os.makedirs(sound_log_dir, exist_ok=True)
    except OSError as e:
        # Use print since logging is not configured yet
        print(f"Error: Failed to create logging directory '{sound_log_dir}': {e}")
        print(f"STOPPING the add-on. Use *Terminal* or SSH CLI to manually create {sound_log_dir} "
               "or set sound_log to false")

        sys.exit(1)  # Exit with a non-zero code to indicate failure

     # -------- KEEP THE USER INFORMED OF ACCUMULATED LOGS
def check_storage(directory, file_extension):
    try:
        # count *.file_extension files
        files = [f for f in os.listdir(directory) if f.endswith(file_extension)]
        file_count = len(files)

        # Calculate total size (B) and convert to MB
        total_size_bytes = sum(os.path.getsize(os.path.join(directory, f)) for f in files)
        total_size_mb = total_size_bytes / (1024 * 1024)

        # Log the file count and total size if we are taking up more than 100MB
        if total_size_mb > 100:
            logger.info(f"NOTE: You have {file_count} {file_extension} files in {directory}, "
                        f"({total_size_mb:.2f}MB)")
    except Exception as e:
        print(f"Error while counting files or calculating size in {directory}: {e}")

     # -------- SET INITIAL LOGGING LEVEL
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

#                                              #
### ---------- SHUT_DOWN HANDLING -----------###
#                                              #

# Add the shutdown filter to all handlers
class ShutdownFilter(logging.Filter):
    def filter(self, record):
        return not shutdown_event.is_set()

for handler in logger.handlers:
    handler.addFilter(ShutdownFilter())

logger.info("\n\n-------- YAMCAM3 Started-------- \n")

#                                                #
### ---------- GET CONFIGURATION --------------###
#                                                #

try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

     # -------- GENERAL 
try:
    general_settings = config['general']
except KeyError as e:
    logger.error(f"Missing general settings in the configuration file: {e}")
    raise

log_level            = general_settings.get('log_level', 'INFO').upper()
logfile              = general_settings.get('logfile', False)
sound_log            = general_settings.get('sound_log', False)
noise_threshold      = general_settings.get('noise_threshold', 0.1)   
default_min_score    = general_settings.get('default_min_score', 0.5)
top_k                = general_settings.get('top_k', 10)
ffmpeg_debug         = general_settings.get('ffmpeg_debug', False)
exclude_groups       = general_settings.get('exclude_groups', []) #group to ignore
summary_interval     = general_settings.get('summary_interval', 5 ) # periodic reports (min)

# default_min_score and noise_thresholdmust be between 0 and 1
if not (0.0 <= default_min_score <= 1.0):
    logger.warning(f"Invalid default_min_score '{default_min_score}'"
                    "Should be between 0.0 and 1.0. Defaulting to 0.5."
    )
    default_min_score = 0.5
if not (0.0 <= noise_threshold <= 1.0):
    logger.warning(f"Invalid noise_threshold '{noise_threshold}'"
                    "Should be between 0.0 and 1.0. Defaulting to 0.1."
    )
    noise_threshold = 0.1
        
# interval for summary entry log messages
logger.info (f"Summary reports every {summary_interval} min.")

     # -------- SET UP LOGGING TO FILE FOR DEBUG ANALYSIS 
if logfile:

    check_for_log_dir() # make sure /media/yamcam exists

    timestamp = datetime.now().strftime('%Y%m%d-%H%M') # timestamp for filename
    log_path = f"{log_dir}/{timestamp}.log"

    check_storage(log_dir, '.log') # let the user know how much storage they're using

    logger.info(f"Creating {log_path} for debug analysis.")
    try:
        file_handler = logging.FileHandler(log_path, mode='a')  # always append
        file_handler.setLevel(logging.DEBUG)  # hard coding logfile to DEBUG
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        # Add the file handler to the logger
        logger.addHandler(file_handler)
        logger.info(f"Logging to {log_path}.")
    except Exception as e:
        logger.error(f"Could not create or open the log file at {log_path}: {e}")


     # -------- SET UP LOGGING TO FILE FOR SOUND ANALYSIS
if sound_log:
    check_for_log_dir() # make sure /media/yamcam exists


     # -------- SOUND EVENT PARAMETERS 
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

     # -------- SOUND GROUPS TO WATCH 
try:
    sounds = config['sounds']
except KeyError:
    logger.debug("Missing sounds settings in the configuration file. Using default values.")

sounds_to_track = sounds.get('track', [])
sounds_filters = sounds.get('filters', {})

# min_score values also need to be between 0 and 1
for group, settings in sounds_filters.items():
    min_score = settings.get('min_score')
    if not (0.0 <= min_score <= 1.0):
        logger.warning(f"Invalid min_score '{min_score}' for group '{group}'."
                        "Should be between 0.0 and 1.0. Defaulting to default_min_score."
        )
        settings['min_score'] = default_min_score 

     # -------- SOUND SOURCES 
try:
    camera_settings  = config['cameras']
except KeyError as e:
    logger.error(f"Missing camera settings in the configuration file: {e}")
    raise

     # -------- MQTT SETTINGS 
try:
    mqtt_settings = config['mqtt']
except KeyError as e:
    logger.error(f"Missing mqtt settings in the configuration file: {e}")
    raise

mqtt_host            = mqtt_settings['host', 0.0.0.0]
mqtt_port            = mqtt_settings['port', 1883]
mqtt_topic_prefix    = mqtt_settings['topic_prefix', 'yamcam/sounds' ]
mqtt_client_id       = mqtt_settings['client_id', 'yamcam'] 
mqtt_username        = mqtt_settings['user', 'yourUserName']
mqtt_password        = mqtt_settings['password' 'yourPassWord']
    
     # -------- LOG LEVEL
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
        #add for file log to stay at DEBUG
        if not isinstance(handler, logging.FileHandler):  # Skip file handler
            handler.setLevel(log_levels[log_level])
    logger.info(f"Logging level: {log_level}")
else:
    logger.warning(f"Invalid log level {log_level}; Defaulting to INFO.")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        handler.setLevel(logging.INFO)

#                                              #
### ---------- SET UP YAMNET MODEL ----------###
#                                              #

     # -------- LOG DETAILS FOR DEBUG
def format_input_details(details):
    formatted_details = "Input Details:\n"
    for detail in details:
        formatted_details += "  -\n"
        for key, value in detail.items():
            formatted_details += f"    {key}: {value}\n"
    return formatted_details


     # -------- LOAD MODEL (using TensorFLow Lite)
logger.debug("Loading YAMNet model")
interpreter    = tflite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.debug("YAMNet model loaded.")
logger.debug(format_input_details(input_details))

     # -------- BUILD CLASS NAMES DICTIONARY
class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))

