# yamcam_config.py
import yaml

config_path = '/config/microphones.yaml'

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


             ######## YAMNet Class_names ########  

# build the class_names dictionary from the Yamnet class map csv

class_names = []
with open(class_map_path, 'r') as file:
    reader = csv.reader(file)
    next(reader)  # Skip the header
    for row in reader:
        class_names.append(row[2].strip('"'))
