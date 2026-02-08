#!/usr/bin/env python3
"""
yamcam_functions.py - Functions for Yamcam5 Home Assistant Add-on
CeC Feb 2025 (Updated)
"""

import time
import os
import atexit
import csv
from datetime import datetime
import threading
from collections import deque
import numpy as np
import json
import paho.mqtt.client as mqtt
import yamcam_config
from yamcam_config import (
    interpreter, input_details, output_details, logger,
    sound_log, sound_log_dir, shutdown_event,
    window_detect, persistence, decay,
    sounds_to_track, sounds_filters, camera_settings, top_k, default_min_score, noise_threshold, class_names, summary_interval,
    mqtt_host, mqtt_port, mqtt_topic_prefix, mqtt_client_id, mqtt_username, mqtt_password
)

# Global locks for thread-safe logging to CSV.
sound_log_lock = threading.Lock()

if sound_log:
    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    sound_log_path = os.path.join(sound_log_dir, f"{timestamp}.csv")
    logger.info(f"Creating sound log CSV at {sound_log_path}.")
    try:
        sound_log_file = open(sound_log_path, 'a', newline='')
        sound_log_writer = csv.writer(sound_log_file)
        header = ["datetime", "camera", "group", "group_score", "class", "class_score", "event_start", "event_end"]
        sound_log_writer.writerow(header)
        sound_log_file.flush()
    except Exception as e:
        logger.warning(f"Could not create sound log CSV at {sound_log_path}: {e}")
        sound_log_file = None
        sound_log_writer = None
else:
    sound_log_file = None
    sound_log_writer = None

def close_sound_log_file():
    if sound_log_file:
        sound_log_file.close()
        logger.info("Sound log CSV closed.")

atexit.register(close_sound_log_file)

# --- MQTT Functions ---
mqtt_client = None

def set_mqtt_client(client):
    global mqtt_client
    mqtt_client = client

def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        logger.error("MQTT connection failed. Check MQTT settings.")

def start_mqtt():
    client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv5)
    client.username_pw_set(mqtt_username, mqtt_password)
    client.on_connect = on_connect
    try:
        client.connect(mqtt_host, mqtt_port, 60)
        client.loop_start()
        logger.info(f"MQTT client connected to {mqtt_host}:{mqtt_port}.")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
    return client

def report_event(camera_name, sound_class, event_type, timestamp):
    # --- CSV Logging ---
    if sound_log_writer:
        log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if event_type == 'start':
            row = [log_timestamp, camera_name, '', '', sound_class, '', '', '']
        else:
            row = [log_timestamp, camera_name, '', '', '', '', '', sound_class]
        with sound_log_lock:
            sound_log_writer.writerow(row)
            sound_log_file.flush()

    # --- MQTT Reporting ---
    formatted_timestamp = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    payload = {
        'camera_name': camera_name,
        'sound_class': sound_class,
        'event_type': event_type,
        'timestamp': formatted_timestamp
    }
    payload_json = json.dumps(payload)
    if mqtt_client and mqtt_client.is_connected():
        try:
            result = mqtt_client.publish(f"{mqtt_topic_prefix}/{event_type}", payload_json)
            result.wait_for_publish()
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish MQTT message: {result.rc}")
        except Exception as e:
            logger.error(f"Exception publishing MQTT message: {e}")
    else:
        logger.error("MQTT client not connected. Skipping MQTT publish.")

def analyze_audio_waveform(waveform, camera_name, interpreter, input_details, output_details):
    if shutdown_event.is_set():
        return None
    try:
        waveform = np.squeeze(waveform).astype(np.float32)
        if waveform.ndim != 1:
            logger.error(f"{camera_name}: Waveform must be a 1D array.")
            return None
        try:
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()
            scores = np.copy(interpreter.get_tensor(output_details[0]['index']))
            if scores.size == 0:
                logger.warning(f"{camera_name}: No scores returned from inference.")
                return None
        except Exception as e:
            logger.error(f"{camera_name}: Interpreter invocation error: {e}")
            return None
        return scores
    except Exception as e:
        logger.error(f"{camera_name}: Error in analyze_audio_waveform: {e}")
        return None

def group_scores_by_prefix(filtered_scores, class_names):
    group_scores = {}
    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]
        group_scores.setdefault(group, []).append(score)
    return group_scores

def calculate_composite_scores(group_scores):
    composite = []
    for group, scores in group_scores.items():
        max_score = max(scores)
        if max_score > 0.7:
            composite_score = max_score
        else:
            composite_score = min(max_score + 0.05 * len(scores), 0.95)
        composite.append((group, composite_score))
    return composite

def rank_sounds(scores, camera_name):
    if shutdown_event.is_set():
        return []
    filtered = [(i, score) for i, score in enumerate(scores[0]) if score >= noise_threshold]
    logger.debug(f"{camera_name}: {len(filtered)} classes above noise threshold.")
    for i, score in filtered:
        class_name = class_names[i]
        group = class_name.split('.')[0]
        logger.debug(f"{camera_name}: Detected {class_name} with score {score:.2f}")
        if sound_log_writer:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [timestamp, camera_name, '', '', class_name, f"{score:.2f}", '', '']
            with sound_log_lock:
                sound_log_writer.writerow(row)
                sound_log_file.flush()
    if not filtered:
        return []
    group_dict = group_scores_by_prefix(filtered, class_names)
    composite_scores = calculate_composite_scores(group_dict)
    sorted_composite = sorted(composite_scores, key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for group, score in sorted_composite:
        if group in sounds_to_track:
            min_score = sounds_filters.get(group, {}).get('min_score', default_min_score)
            if score >= min_score:
                results.append({'class': group, 'score': score})
    return results

# --- Sound Event Window Management ---
state_lock = threading.Lock()
sound_windows = {}       # {camera_name: {sound_class: deque}}
active_sounds = {}       # {camera_name: {sound_class: bool}}
last_detection_time = {} # {camera_name: {sound_class: timestamp}}
decay_counters = {}      # {camera_name: {sound_class: remaining}}
event_counts = {}        # {camera_name: {sound_class: count}}

def update_sound_window(camera_name, detected_sounds):
    if shutdown_event.is_set():
        return
    current_time = time.time()
    with state_lock:
        if camera_name not in sound_windows:
            sound_windows[camera_name] = {}
            active_sounds[camera_name] = {}
            last_detection_time[camera_name] = {}
            decay_counters[camera_name] = {}
            event_counts[camera_name] = {}
        window = sound_windows[camera_name]
        active = active_sounds[camera_name]
        last_time = last_detection_time[camera_name]
        decay_cam = decay_counters[camera_name]
        counts = event_counts[camera_name]
        for sound_class in sounds_to_track:
            if sound_class not in window:
                window[sound_class] = deque(maxlen=window_detect)
            is_detected = sound_class in detected_sounds
            window[sound_class].append(is_detected)
            if is_detected:
                last_time[sound_class] = current_time
            if window[sound_class].count(True) >= persistence:
                if not active.get(sound_class, False):
                    active[sound_class] = True
                    decay_cam[sound_class] = decay
                    counts[sound_class] = counts.get(sound_class, 0) + 1
                    report_event(camera_name, sound_class, 'start', current_time)
                    logger.info(f"{camera_name}: Sound '{sound_class}' started.")
            else:
                if active.get(sound_class, False):
                    if sound_class in detected_sounds:
                        decay_cam[sound_class] = decay
                    else:
                        decay_cam[sound_class] -= 1
                        if decay_cam[sound_class] <= 0:
                            active[sound_class] = False
                            report_event(camera_name, sound_class, 'stop', current_time)
                            logger.info(f"{camera_name}: Sound '{sound_class}' stopped.")

def log_summary():
    while not shutdown_event.is_set():
        try:
            time.sleep(summary_interval * 60)
            if shutdown_event.is_set():
                break
            with state_lock:
                summary_lines = []
                for camera_name in camera_settings.keys():
                    counts = event_counts.get(camera_name, {})
                    total_events = sum(counts.values())
                    if total_events > 0:
                        groups = ', '.join(sorted(set(counts.keys())))
                        summary_lines.append(f"{camera_name}: {total_events} events: {groups}")
                    else:
                        summary_lines.append(f"{camera_name}: No sound events")
                if summary_lines:
                    formatted = "\n    ".join(summary_lines)
                    logger.info(f"Summary (past {summary_interval} min):\n    {formatted}")
                else:
                    logger.info(f"Summary (past {summary_interval} min): No events detected.")
                for counts in event_counts.values():
                    counts.clear()
        except Exception as e:
            logger.error(f"Exception in log_summary: {e}", exc_info=True)

