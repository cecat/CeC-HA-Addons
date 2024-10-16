#
# yamcam3 - CeC September 2024
#
# yamcam_functions.py - Functions for yamcam3
# 
#
#  ### Communications via MQTT
#
#         set_mqtt_client(client):
#
#         on_connect(client, userdata, flags, rc, properties=None)
#             Set up thread
#
#         start_mqtt()
#             Connect to the MQTT broker (host) with settings from configuration yaml file
#
#         report(results, mqtt_client, camera_name)
#             Report via MQTT using topic prefix from configuration yaml file and
#             with a JSON payload.
#
#  ### Analyse the waveform using YAMNet
#
#         analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details)
#             Check waveform for compatibility with YAMNet interpreter, invoke the
#             intepreter, and return scores (a [1,521] array of scores, ordered per the
#             YAMNet class map CSV (files/yamnet_class_map.csv)
#
#  ### Ranking and Scoring Sounds
#
#         rank_sounds(scores, camera_name)
#             Use noise_threshold to toss out very low scores; take the top_k highest
#             scores, return a [2,521] array with pairs of class names (from class map CSV)
#             and scores.  Calls group_scores to group these class name/score pairs by
#             group, in turn calling calculate_composite_scores to create scores for these
#             groups. A modified yamnet_class_map.csv prepends each Yamnet display name
#             with a group name (people, music, birds, etc.) for this purpose.
#
#         group_scores_by_prefix(filtered_scores, class_names)
#             Organize filtered scores into groups according to the prefix of each class
#             name in (modified) files/yamnet_class_map.csv
#
#         calculate_composite_scores(group_scores_dict)
#             To report by group (vs. individual classes), take the individual scores from
#             each group (within the filtered scores) and use a simple algorithm to
#             score the group.  If any individual class score within the group is above 0.7,
#             that score will be used for the entire group.  Otherwise, take the highest
#             score within the group and add a confidence credit (0.05) for each individual
#             class within that group that made it through the filtering process.  Max 
#             composite score is 0.95 (unless the highest scoring class within the group 
#             is higher).
#
#  ### Sound Event Detection
#
#          update_sound_window(camera_name, detected_sounds)
#             Set up sliding window for detecting start/end sound events
#             
#          report_event(camera_name, sound_class, event_type, timestamp)
#
#          log_summary()
#
# ###  Misc
#
#          close_sound_log_file()
#             Make sure the sound_log CSV file is closed at exit
#

import time
import os
import atexit
import csv
from datetime import datetime
import threading 
from collections import deque
import paho.mqtt.client as mqtt
import numpy as np
import json
import yamcam_config
from yamcam_config import (
        interpreter, input_details, output_details, logger,
        sound_log, sound_log_dir,
        exclude_groups, summary_interval, shutdown_event
)

logger = yamcam_config.logger

#                                                #
### ---------- SOUND LOG CSV SETUP --------------###
#                                                #

sound_log_lock = threading.Lock()  # lock the file when writing since we have multiple threads writing

timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M') # timestamp as log filename
sound_log_path = os.path.join(sound_log_dir, f"{timestamp}.csv") # create the log file

if sound_log:
    logger.info(f"Creating {sound_log_path} for sound history analysis.")
    try:
        sound_log_file = open(sound_log_path, 'a', newline='')
        sound_log_writer = csv.writer(sound_log_file)
    except Exception as e:
        logger.error(f"Could not create {sound_log_path}: {e}")
        sound_log_file = None
        sound_log_writer = None
else:
    sound_log_file = None
    sound_log_writer = None



     # -------- MAKE SURE WE CLOSE CSV AT EXIT

def close_sound_log_file():
    if sound_log_file is not None:
        sound_log_file.close()
        logger.info("Sound log file closed.")

atexit.register(close_sound_log_file)

#                                                #
### ---------- REPORTING SETUP ----------------###
#                                                #

     # -------- GLOBALS FOR SUMMARY REPORTING
sound_event_tracker = {}
sound_event_lock = threading.Lock()
event_counts = {}

     # -------- DATA STRUCTS FOR EVENTS
# Decay counter data structure for detecting sound event termination
# Stores decay counters for each active sound class per camera
decay_counters = {}  # Structure: {camera_name: {sound_class: remaining_chunks}}

# State management for sound event detection
sound_windows = {}        # {camera_name: {sound_class: deque}}
active_sounds = {}        # {camera_name: {sound_class: bool}}
last_detection_time = {}  # {camera_name: {sound_class: timestamp}}

state_lock = threading.Lock()

#                                                #
### ---------- COMMUNICATIONS -----------------###
#                                                #

mqtt_client = None # will initialize in yamcam.py and set via a function

     # -------- MQTT CLIENT AS GLOBAL
def set_mqtt_client(client):
    global mqtt_client
    mqtt_client = client

     # -------- VERIFY CONNECTION
def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        logger.error("FAILED to connect to MQTT broker. Check MQTT settings.")

     # -------- CONNECT TO BROKER
def start_mqtt():
    mqtt_host = yamcam_config.mqtt_host
    mqtt_port = yamcam_config.mqtt_port
    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix
    mqtt_client_id = yamcam_config.mqtt_client_id
    mqtt_username = yamcam_config.mqtt_username
    mqtt_password = yamcam_config.mqtt_password
        
    logger.debug(
        f"MQTT Settings:\n"
        f"   Host: {mqtt_host} ; Port: {mqtt_port}\n"
        f"   Topic Prefix: {mqtt_topic_prefix} ; Client ID: {mqtt_client_id} ; User: {mqtt_username}."
    )

    mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    mqtt_client.on_connect = on_connect

    try:
        mqtt_client.connect(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_start()
        logger.info(f"MQTT client CONNECTED to {mqtt_host}:{mqtt_port}.")
    except Exception as e:
        logger.error(f"FAILED to connect to MQTT broker: {e}")

    return mqtt_client  

     # -------- REPORT SOUND EVENT
def report_event(camera_name, sound_class, event_type, timestamp):
    global mqtt_client

    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

    formatted_timestamp = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    payload = {
        'camera_name': camera_name,
        'sound_class': sound_class,
        'event_type': event_type,
        'timestamp': formatted_timestamp
    }

    payload_json = json.dumps(payload)

    if mqtt_client.is_connected():
        try:
            result = mqtt_client.publish(f"{mqtt_topic_prefix}/{event_type}", payload_json)
            result.wait_for_publish()
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"FAILED to publish MQTT message: {result.rc}")
        except Exception as e:
            logger.error(f"Exception: Failed to publish MQTT message: {e}")
    else:
        logger.error("MQTT client is NOT CONNECTED. Skipping publish.")
        logger.error("MQTT client is NOT CONNECTED. Skipping publish.")


#                                                #
### ---------- SOUND FUNCTIONS ----------------###
#                                                #

     # -------- ANALYZE Waveform using YAMNet  
def analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details):

    if shutdown_event.is_set():
        return None

    try:
        # Ensure waveform is a 1D array of float32 values between -1 and 1
        waveform = np.squeeze(waveform).astype(np.float32)
        if waveform.ndim != 1:
            logger.error(f"{camera_name}: Waveform must be a 1D array.")
            return None

        # Invoke the YAMNET inference engine 
        try:
            # Set input tensor and invoke interpreter
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()

            # Get output scores; convert to a copy to avoid holding internal references
            scores = np.copy(interpreter.get_tensor(output_details[0]['index']))  

            if scores.size == 0:
                logger.error(f"{camera_name}: No scores available to analyze.")
                return None

        except Exception as e:
            logger.error(f"{camera_name}: Error during interpreter invocation: {e}")
            return None

        return scores

    except Exception as e:
        logger.error(f"{camera_name}: Error during waveform analysis: {e}")
        return None


     # -------- Calculate, Group, and Filter Scores  
def rank_sounds(scores, camera_name):
    if shutdown_event.is_set():
        return []

    # Get config settings
    default_min_score = yamcam_config.default_min_score
    top_k = yamcam_config.top_k
    noise_threshold = yamcam_config.noise_threshold
    class_names = yamcam_config.class_names
    sounds_filters = yamcam_config.sounds_filters


# Step 1: Filter out scores below noise_threshold
    filtered_scores = [
        (i, score) for i, score in enumerate(scores[0]) if score >= noise_threshold
    ]

    logger.debug(f"{camera_name}: {len(filtered_scores)} classes found:")
    # Log individual classes and their scores before grouping
    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]  # Get the group prefix
        if group in exclude_groups:
            logger.debug(f"{camera_name}:--> {class_name}: {score:.2f} (excluded_group)")
        else:
            logger.debug(f"{camera_name}:--> {class_name}: {score:.2f}")
        # CSV logging (classes)
        if sound_log_writer is not None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [timestamp, camera_name, '', '', class_name, f"{score:.2f}"]
            with sound_log_lock:
                sound_log_writer.writerow(row)
                sound_log_file.flush()

    if not filtered_scores:
        return []

    # Step 2: Group classes
    group_scores_dict = group_scores_by_prefix(filtered_scores, class_names)

    # Step 3: Calculate composite scores
    composite_scores = calculate_composite_scores(group_scores_dict)

    # Step 3.1: Sort composite scores in descending order
    sorted_composite_scores = sorted(composite_scores, key=lambda x: x[1], reverse=True)

    # Step 3.2: Limit to top_k composite scores
    limited_composite_scores = sorted_composite_scores[:top_k]

    # Log the group names and composite scores
    for group, score in limited_composite_scores:
        if group in exclude_groups:
            continue # Skip logging this group
        logger.debug(f"{camera_name}: ----->{group}: {score:.2f}")

        # CSV logging (groups)
        if sound_log_writer is not None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [timestamp, camera_name, group, f"{score:.2f}", '', '']
            with sound_log_lock:
                sound_log_writer.writerow(row)
                sound_log_file.flush()

    # Step 4: Apply min_score filters and prepare results
    results = []
    for group, score in limited_composite_scores:
        if group in yamcam_config.sounds_to_track:
            min_score = sounds_filters.get(group, {}).get('min_score', default_min_score)
            if score >= min_score:
                results.append({'class': group, 'score': score})

    return results


     # -------- Combine filtered class/score Pairs into Groups  
     # Group scores by prefix (e.g., 'music.*'), and keep track 
     # of the individual class scores.
def group_scores_by_prefix(filtered_scores, class_names):
    group_scores_dict = {}

    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]  # Get the group prefix before the first period '.'

        if group not in group_scores_dict:
            group_scores_dict[group] = []

        group_scores_dict[group].append(score)

    return group_scores_dict


     # -------- Calculate Composite Scores for Groups 
     # Group scores by prefix (e.g., 'music.*'), and keep track of the individual class scores.
     # Algorithm to create a group score using the scores of the component classes from that group
     # - If max score in group is > 0.7, use this as the group composite score.
     # - Otherwise, boost score with credit based on number of group classes that were found:
     #   Max score + 0.05 * number of classes in the group (Cap Max score at 0.95).
def calculate_composite_scores(group_scores_dict):

    composite_scores = []

    for group, scores in group_scores_dict.items():
        max_score = max(scores)
        if max_score > 0.7:
            composite_score = max_score
        else:
            composite_score = min(max_score + 0.05 * len(scores), 0.95)

        composite_scores.append((group, composite_score))

    return composite_scores

     # -------- Manage Sound Event Window 
def update_sound_window(camera_name, detected_sounds):

    if shutdown_event.is_set():
        return

    current_time = time.time()
    with state_lock:

        # Initialize if not present
        if camera_name not in sound_windows:
            sound_windows[camera_name] = {}
            active_sounds[camera_name] = {}
            last_detection_time[camera_name] = {}
            decay_counters[camera_name] = {}  # Initialize decay_counters for the camera
            event_counts[camera_name] = {}    # Initialize event_counts for the camera

        window = sound_windows[camera_name]
        active = active_sounds[camera_name]
        last_time = last_detection_time[camera_name]
        decay_camera = decay_counters[camera_name]
        counts = event_counts[camera_name]

        for sound_class in yamcam_config.sounds_to_track:
            # Initialize deque for sound class
            if sound_class not in window:
                window[sound_class] = deque(maxlen=yamcam_config.window_detect)

            # Update detections
            is_detected = sound_class in detected_sounds
            window[sound_class].append(is_detected)

            # Update last detection time
            if is_detected:
                last_time[sound_class] = current_time

            # Check for start event
            if window[sound_class].count(True) >= yamcam_config.persistence:
                if not active.get(sound_class, False):
                    active[sound_class] = True
                    decay_camera[sound_class] = yamcam_config.decay
                    # Increment the event count for this sound_class
                    counts[sound_class] = counts.get(sound_class, 0) + 1
                    report_event(camera_name, sound_class, 'start', current_time)
                    if not shutdown_event.is_set():
                        logger.info(f"{camera_name}: Sound '{sound_class}' started.")
            else:
                # Check for stop event using decay counters
                if active.get(sound_class, False):
                    if sound_class in detected_sounds:
                        # Reset decay counter if sound is detected
                        decay_camera[sound_class] = yamcam_config.decay
                    else:
                        # Decrement decay counter if sound is not detected
                        decay_camera[sound_class] -= 1
                        if decay_camera[sound_class] <= 0:
                            active[sound_class] = False
                            report_event(camera_name, sound_class, 'stop', current_time)
                            if not shutdown_event.is_set():
                                logger.info(f"{camera_name}: Sound '{sound_class}' stopped.")



     # -------- Generate Periodic summaries

def generate_summary():
    logger.info("Summary:")
    with state_lock:
        for camera_name in yamcam_config.cameras:
            counts = event_counts.get(camera_name, {})
            total_events = sum(counts.values())
            if total_events > 0:
                groups = ', '.join(set(counts.keys()))
                logger.info(f"    {camera_name} : {total_events} sounds in past {yamcam_config.n} min: {groups}")
            else:
                logger.info(f"    {camera_name} : No sounds detected in past {yamcam_config.n} min")

        # Reset event counts after summary
        for counts in event_counts.values():
            counts.clear()


     # -------- Schedule Periodic summaries 

def schedule_summary():
    while not shutdown_event.is_set():
        time.sleep(yamcam_config.summary_interval * 60)  # Wait for summary_interval minutes
        generate_summary()


     # -------- Log a summary

def log_summary():
    while not shutdown_event.is_set():
        try:
            time.sleep(yamcam_config.summary_interval * 60)  # Sleep for the specified interval
            if shutdown_event.is_set():
                break  # Exit if the shutdown flag is set

            with state_lock:
                summary_lines = []
                for camera_name in yamcam_config.camera_settings.keys():
                    counts = event_counts.get(camera_name, {})
                    total_events = sum(counts.values())
                    if total_events > 0:
                        groups = ', '.join(sorted(set(counts.keys())))
                        summary_lines.append(f"{camera_name} : {total_events} sounds in "
                                             f"past {yamcam_config.summary_interval} min: {groups}")
                    else:
                        summary_lines.append(f"{camera_name} : No sounds detected in past {yamcam_config.summary_interval} min")

                if summary_lines:
                    # Create a multi-line summary with indentation
                    formatted_summary = "\n    ".join(summary_lines)
                    logger.info(f"Summary:\n    {formatted_summary}")
                else:
                    logger.info("Summary: No sounds detected for any camera.")

                # Reset event counts after summary
                for counts in event_counts.values():
                    counts.clear()

        except Exception as e:
            logger.error(f"Exception in log_summary: {e}", exc_info=True)

     # -------- REPORT (deprecated, see REPORT_EVENT)
     #----- this function deprecated by report_event
     #----- leaving it in case we decide to report more detail
def report(results, mqtt_client, camera_name):

    mqtt_topic_prefix = yamcam_config.mqtt_topic_prefix

    if mqtt_client.is_connected():
        try:
            formatted_results = [
                {
                    'class': r['class'],
                    'score': float(f"{r['score']:.2f}")
                }
                for r in results
            ]

            payload = {
                'camera_name': camera_name,
                'sound_classes': formatted_results
            }

            payload_json = json.dumps(payload)
            logger.debug(f"{camera_name}: {mqtt_topic_prefix}, {payload_json}")
            result = mqtt_client.publish( f"{mqtt_topic_prefix}", payload_json)
            result.wait_for_publish()

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"\n{payload_json}")
            else:
                logger.error(f"FAILED to publish MQTT message: {result.rc}")
        except Exception as e:
            logger.error(f"Exception: Failed to form/publish MQTT message: {e}")
    else:
            logger.error("MQTT client is not connected. Skipping publish.")


