#!/usr/bin/env python3
"""
yamcam_config.py - Configuration for Yamcam5 Home Assistant Add-on
CeC Feb 2025 (Updated)
"""

import yaml
import csv
import logging
import tflite_runtime.interpreter as tflite
import time
import threading
import os
import sys
from datetime import datetime

# --- File paths (as used in Home Assistant add-on) ---
config_path = '/config/microphones.yaml'
class_map_path = 'yamnet_class_map.csv'
model_path = 'yamnet.tflite'
log_dir = '/media/yamcam'
sound_log_dir = '/media/yamcam'

# --- Global shutdown event ---
shutdown_event = threading.Event()

def check_for_log_dir():
    try:
        os.makedirs(sound_log_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Failed to create logging directory '{sound_log_dir}': {e}")
        print(f"STOPPING the add-on. Manually create {sound_log_dir} or disable sound logging.")
        sys.exit(1)

def validate_camera_config(camera_settings):
    for camera_name, camera_config in camera_settings.items():
        ffmpeg_config = camera_config.get('ffmpeg')
        if not ffmpeg_config or not isinstance(ffmpeg_config, dict):
            raise ValueError(f"Camera '{camera_name}': 'ffmpeg' section is missing or invalid.")
        inputs = ffmpeg_config.get('inputs')
        if not inputs or not isinstance(inputs, list) or len(inputs) == 0:
            raise ValueError(f"Camera '{camera_name}': 'inputs' section is missing or invalid.")
        rtsp_url = inputs[0].get('path')
        if not rtsp_url or not isinstance(rtsp_url, str):
            raise ValueError(f"Camera '{camera_name}': RTSP path is missing or invalid.")

def format_input_details(details):
    formatted = "Input Details:\n"
    for detail in details:
        formatted += "  -\n"
        for key, value in detail.items():
            formatted += f"    {key}: {value}\n"
    return formatted

def validate_boolean(var_name, var_value):
    if isinstance(var_value, str):
        v = var_value.lower()
        if v == "true":
            return True
        elif v == "false":
            return False
        else:
            logger.warning(f"Invalid boolean value '{var_value}' for {var_name}. Defaulting to False.")
            return False
    elif isinstance(var_value, bool):
        return var_value
    else:
        logger.warning(f"Invalid type for {var_name}. Defaulting to False.")
        return False

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Prevent logging once shutdown is initiated.
class ShutdownFilter(logging.Filter):
    def filter(self, record):
        return not shutdown_event.is_set()

for handler in logger.handlers:
    handler.addFilter(ShutdownFilter())

logger.info("\n\n-------- YAMCAM3 Started --------\n")

# --- Load YAML configuration ---
try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except yaml.YAMLError as e:
    logger.error(f"Error reading YAML file {config_path}: {e}")
    raise

# --- General Settings ---
try:
    general_settings = config['general']
except KeyError as e:
    logger.error(f"Missing general settings in config: {e}")
    raise

log_level         = general_settings.get('log_level', 'INFO').upper()
logfile           = general_settings.get('logfile', False)
sound_log         = general_settings.get('sound_log', False)
ffmpeg_debug      = general_settings.get('ffmpeg_debug', False)
default_min_score = general_settings.get('default_min_score', 0.5)
noise_threshold   = general_settings.get('noise_threshold', 0.1)
top_k             = general_settings.get('top_k', 10)
summary_interval  = general_settings.get('summary_interval', 5)

logfile = validate_boolean("logfile", logfile)
sound_log = validate_boolean("sound_log", sound_log)
ffmpeg_debug = validate_boolean("ffmpeg_debug", ffmpeg_debug)

if not (0.0 <= default_min_score <= 1.0):
    logger.warning(f"Invalid default_min_score '{default_min_score}'. Defaulting to 0.5.")
    default_min_score = 0.5
if not (0.0 <= noise_threshold <= 1.0):
    logger.warning(f"Invalid noise_threshold '{noise_threshold}'. Defaulting to 0.1.")
    noise_threshold = 0.1
if not (1 <= top_k <= 20):
    logger.warning(f"Invalid top_k '{top_k}'. Defaulting to 10.")
    top_k = 10

logger.info(f"Summary reports every {summary_interval} minutes.")

check_for_log_dir()
if logfile:
    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    log_path = os.path.join(log_dir, f"{timestamp}.log")
    logger.info(f"Creating log file at {log_path}.")
    try:
        file_handler = logging.FileHandler(log_path, mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Logging to {log_path}.")
    except Exception as e:
        logger.error(f"Could not create log file at {log_path}: {e}")

# --- Event and Sound Settings ---
try:
    events_settings = config['events']
except KeyError:
    logger.warning("Missing events settings. Using defaults.")
    events_settings = {'window_detect': 5, 'persistence': 3, 'decay': 15}
window_detect = events_settings.get('window_detect', 5)
persistence   = events_settings.get('persistence', 3)
decay         = events_settings.get('decay', 15)

try:
    sounds = config['sounds']
except KeyError:
    logger.warning("Missing sounds settings. Using defaults.")
    sounds = {}

sounds_to_track = sounds.get('track', [])
sounds_filters  = sounds.get('filters', {})
for group, settings in sounds_filters.items():
    min_score = settings.get('min_score')
    if not (0.0 <= min_score <= 1.0):
        logger.warning(f"Invalid min_score '{min_score}' for group '{group}'. Defaulting to {default_min_score}.")
        settings['min_score'] = default_min_score

try:
    camera_settings = config['cameras']
    validate_camera_config(camera_settings)
except KeyError as e:
    logger.error(f"Missing camera settings in config: {e}")
    sys.exit(1)
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

# --- MQTT Settings ---
try:
    mqtt_settings = config['mqtt']
except KeyError as e:
    logger.error(f"Missing MQTT settings in config: {e}")
    raise

mqtt_host         = mqtt_settings.get('host', '0.0.0.0')
mqtt_port         = mqtt_settings.get('port', 1883)
mqtt_topic_prefix = mqtt_settings.get('topic_prefix', 'yamcam/sounds')
mqtt_client_id    = mqtt_settings.get('client_id', 'yamcam')
mqtt_username     = mqtt_settings.get('user', 'noUser')
mqtt_password     = mqtt_settings.get('password', 'noPassword')

# --- Set Logging Level ---
log_levels = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
if log_level in log_levels:
    logger.setLevel(log_levels[log_level])
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            handler.setLevel(log_levels[log_level])
    logger.info(f"Logging level set to: {log_level}")
else:
    logger.warning(f"Invalid log level {log_level}; defaulting to INFO.")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        handler.setLevel(logging.INFO)

# --- Initialize YAMNet Model using tflite_runtime ---
logger.debug("Loading YAMNet model...")
interpreter = tflite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
logger.debug("YAMNet model loaded.")
logger.debug(format_input_details(input_details))

# --- Build Class Names Dictionary ---
class_names = []
try:
    with open(class_map_path, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for row in reader:
            class_names.append(row[2].strip('"'))
except Exception as e:
    logger.error(f"Error reading class map from {class_map_path}: {e}")
    sys.exit(1)

