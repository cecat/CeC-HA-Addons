#!/usr/bin/env python3
"""
yamcam_functions.py - Functions for Yamcam Sound Profiler (YSP)
CeC November 2024
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
import yamcam_config
from yamcam_config import (
    interpreter, input_details, output_details, logger,
    sound_log, sound_log_dir, shutdown_event,
    window_detect, persistence, decay,
    sounds_to_track, sounds_filters, camera_settings, top_k, default_min_score, noise_threshold, class_names, summary_interval
)

# -----------------------------------------------------------
# SOUND LOG CSV SETUP
# -----------------------------------------------------------
sound_log_lock = threading.Lock()

if sound_log:
    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    sound_log_path = os.path.join(sound_log_dir, f"{timestamp}.csv")
    logger.info(f"Creating sound log CSV at {sound_log_path}.")
    try:
        sound_log_file = open(sound_log_path, 'a', newline='')
        sound_log_writer = csv.writer(sound_log_file)
        # Write header row
        header = ["datetime", "sound_source", "group_name", "group_score", "class_name",
                  "class_score", "event_start", "event_end"]
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
    if sound_log_file is not None:
        sound_log_file.close()
        logger.info("Sound log file closed.")

atexit.register(close_sound_log_file)

# -----------------------------------------------------------
# Analyze Audio Waveform using YAMNet
# -----------------------------------------------------------
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
                logger.warning(f"{camera_name}: No scores available.")
                return None
        except Exception as e:
            logger.error(f"{camera_name}: Error during interpreter invocation: {e}")
            return None
        return scores
    except Exception as e:
        logger.error(f"{camera_name}: Error analyzing waveform: {e}")
        return None

# -----------------------------------------------------------
# Ranking and Scoring Sounds
# -----------------------------------------------------------
def group_scores_by_prefix(filtered_scores, class_names):
    group_scores_dict = {}
    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]
        if group not in group_scores_dict:
            group_scores_dict[group] = []
        group_scores_dict[group].append(score)
    return group_scores_dict

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

def rank_sounds(scores, camera_name):
    if shutdown_event.is_set():
        return []
    filtered_scores = [(i, score) for i, score in enumerate(scores[0]) if score >= noise_threshold]
    logger.debug(f"{camera_name}: Found {len(filtered_scores)} classes with score >= {noise_threshold}")
    for i, score in filtered_scores:
        class_name = class_names[i]
        group = class_name.split('.')[0]
        logger.debug(f"{camera_name}: Detected {class_name}: {score:.2f}")
        if sound_log_writer is not None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [timestamp, camera_name, '', '', class_name, f"{score:.2f}", '', '']
            with sound_log_lock:
                sound_log_writer.writerow(row)
                sound_log_file.flush()
    if not filtered_scores:
        return []
    group_scores_dict = group_scores_by_prefix(filtered_scores, class_names)
    composite_scores = calculate_composite_scores(group_scores_dict)
    sorted_composite_scores = sorted(composite_scores, key=lambda x: x[1], reverse=True)
    limited_composite_scores = sorted_composite_scores[:top_k]
    results = []
    for group, score in limited_composite_scores:
        if group in sounds_to_track:
            min_score = sounds_filters.get(group, {}).get('min_score', default_min_score)
            if score >= min_score:
                results.append({'class': group, 'score': score})
    return results

# -----------------------------------------------------------
# Manage Sound Event Window
# -----------------------------------------------------------
state_lock = threading.Lock()
sound_windows = {}       # {camera_name: {sound_class: deque}}
active_sounds = {}       # {camera_name: {sound_class: bool}}
last_detection_time = {} # {camera_name: {sound_class: timestamp}}
decay_counters = {}      # {camera_name: {sound_class: remaining_chunks}}
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
        decay_camera = decay_counters[camera_name]
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
                    decay_camera[sound_class] = decay
                    counts[sound_class] = counts.get(sound_class, 0) + 1
                    report_event(camera_name, sound_class, 'start', current_time)
                    logger.debug(f"{camera_name}: Sound '{sound_class}' started.")
            else:
                if active.get(sound_class, False):
                    if sound_class in detected_sounds:
                        decay_camera[sound_class] = decay
                    else:
                        decay_camera[sound_class] -= 1
                        if decay_camera[sound_class] <= 0:
                            active[sound_class] = False
                            report_event(camera_name, sound_class, 'stop', current_time)
                            logger.debug(f"{camera_name}: Sound '{sound_class}' stopped.")

# -----------------------------------------------------------
# Reporting (CSV logging)
# -----------------------------------------------------------
def report_event(camera_name, sound_class, event_type, timestamp):
    if sound_log_writer is not None:
        log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if event_type == 'start':
            row = [log_timestamp, camera_name, '', '', '', '', sound_class, '']
        else:
            row = [log_timestamp, camera_name, '', '', '', '', '', sound_class]
        with sound_log_lock:
            sound_log_writer.writerow(row)
            sound_log_file.flush()

# -----------------------------------------------------------
# Periodic Summary Logging
# -----------------------------------------------------------
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
                    formatted_summary = "\n    ".join(summary_lines)
                    logger.info(f"Summary (past {summary_interval} min):\n    {formatted_summary}")
                else:
                    logger.info(f"Summary (past {summary_interval} min): No events detected.")
                for counts in event_counts.values():
                    counts.clear()
        except Exception as e:
            logger.error(f"Exception in log_summary: {e}", exc_info=True)

