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
import sys
from datetime import datetime

# File paths

config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'
log_dir = '/media/yamcam'
sound_log_dir = '/media/yamcam'

# Global shutdown event
shutdown_event = threading.Event()

# ---------- FUNCTIONS ---------- #

def check_for_log_dir():
    try:
        os.makedirs(sound_log_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Failed to create logging directory '{sound_log_dir}': {e}")
        print(f"STOPPING the add-on. Use *Terminal* or SSH CLI to manually create {sound_log_dir} "
              "or set sound_log to false")
        sys.exit(1)

def check_storage(directory, file_extension):
    try:
        files = [f for f in os.listdir(directory) if f.endswith(file_extension)]
        file_count = len(files)
        total_size_bytes = sum(os.path.getsize(os.path.join(directory, f)) for f in files)
        total_size_mb = total_size_bytes / (1024 * 1024)

        if total_size_mb > 100:
            logger.info(f"NOTE: You have {file_count} {file_extension} files in {directory}, "
                        f"({total_size_mb:.2f}MB)")
    except Exception as e:
        print(f"Error while counting files or calculating size in {directory}: {e}")

class ShutdownFilter(logging.Filter):
    def filter(self, record):
        return not shutdown_event.is_set()

def validate_camera_config(camera_settings):
    for camera_name, camera_config in camera_settings.items():
        ffmpeg_config = camera_config.get('ffmpeg')
        if not ffmpeg_config or not isinstance(ffmpeg_config, dict):
            raise ValueError(f"STOPPING. Camera '{camera_name}': 'ffmpeg' section is missing or invalid.")

        inputs = ffmpeg_config.get('inputs')
        if not inputs or not isinstance(inputs, list) or len(inputs) == 0:
            raise ValueError(f"Camera '{camera_name}': 'inputs' section is missing or invalid.")

        rtsp_url = inputs[0].get('path')
        if not rtsp_url or not isinstance(rtsp_url, str):
            raise ValueError(f"Camera '{camera_name}': RTSP path is missing or invalid.")

def format_input_details(details):
    formatted_details = "Input Details:\n"
    for detail in details:
        formatted_details += "  -\n"
        for key, value in detail.items():
            formatted_details += f"    {key}: {value}\n"
    return formatted_details

# ---------- LOGIC ---------- #

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

for handler in logger.handlers:
    handler.addFilter(ShutdownFilter())

logger.info("\n\n-------- YAMCAM3 Started-------- \n")

try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

try:
    general_settings = config['general']
except KeyError as e:
    logger.error(f"Missing general settings in the configuration file: {e}")
    raise

log_level = general_settings.get('log_level', 'INFO').upper()
logfile = general_settings.get('logfile', False)
sound_log = general_settings.get('sound_log', False)
ffmpeg_debug = general_settings.get('ffmpeg_debug', False)
default_min_score = general_settings.get('default_min_score', 0.5)
noise_threshold = general_settings.get('noise_threshold', 0.1)
top_k = general_settings.get('top_k', 10)
exclude_groups = general_settings.get('exclude_groups', [])
summary_interval = general_settings.get('summary_interval', 5)

if isinstance(logfile, str):
    logfile_lower = logfile.lower()
    if logfile_lower == "true":
        logfile = True
    elif logfile_lower == "false":
        logfile = False
    else:
        logger.warning(f"Invalid boolean value '{logfile}' for logfile. Defaulting to False.")
        logfile = False
elif isinstance(logfile, bool):
    pass
else:
    logger.warning(f"Invalid boolean type for '{logfile}' for logfile. Defaulting to False.")
    logfile = False

if isinstance(sound_log, str):
    sound_log_lower = sound_log.lower()
    if sound_log_lower == "true":
        sound_log = True
    elif sound_log_lower == "false":
        sound_log = False
    else:
        logger.warning(f"Invalid boolean value '{sound_log}' for sound_log. Defaulting to False.")
        sound_log = False
elif isinstance(sound_log, bool):
    pass
else:
    logger.warning(f"Invalid boolean value '{sound_log}' for sound_log. Defaulting to False.")
    sound_log = False

if isinstance(ffmpeg_debug, str):
    ffmpeg_debug_lower = ffmpeg_debug.lower()
    if ffmpeg_debug_lower == "true":
        ffmpeg_debug = True
    elif ffmpeg_debug_lower == "false":
        ffmpeg_debug = False
    else:
        logger.warning(f"Invalid boolean value '{ffmpeg_debug}' for ffmpeg_debug. Defaulting to False.")
        ffmpeg_debug = False
elif isinstance(ffmpeg_debug, bool):
    pass
else:
    logger.warning(f"Invalid boolean value '{ffmpeg_debug}' for ffmpeg_debug. Defaulting to False.")
    ffmpeg_debug = False

if not (0.0 <= default_min_score <= 1.0):
    logger.warning(f"Invalid default_min_score '{default_min_score}'"
                   "Should be between 0.0 and 1.0. Defaulting to 0.5.")
    default_min_score = 0.5

if not (0.0 <= noise_threshold <= 1.0):
    logger.warning(f"Invalid noise_threshold '{noise_threshold}'"
                   "Should be between 0.0 and 1.0. Defaulting to 0.1.")
    noise_threshold = 0.1

if not (1 <= top_k <= 20):
    logger.warning(f"Invalid top_k '{top_k}'"
                   "Should be between 1 and 20. Defaulting to 10.")
    top_k = 10

logger.info(f"Summary reports every {summary_interval} min.")

if logfile:
    check_for_log_dir()

    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    log_path = os.path.join(log_dir, f"{timestamp}.log")

    check_storage(log_dir, '.log')

    logger.info(f"Creating {log_path} for debug analysis.")
    try:
        file_handler = logging.FileHandler(log_path, mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Logging to {log_path}.")
    except Exception as e:
        logger.error(f"Could not create or open the log file at {log_path}: {e}")

if sound_log:
    check_for_log_dir()

try:
    events_settings = config['events']
except KeyError:
    logger.warning("Missing events settings in the configuration file. Using default values.")
    events_settings = {
        'window_detect': 5,
        'persistence': 3,
        'decay': 15
    }

window_detect = events_settings.get('window_detect', 5)
persistence = events_settings.get('persistence', 3)
decay = events_settings.get('decay', 15)

try:
    sounds = config['sounds']
except KeyError:
    logger.warning("

