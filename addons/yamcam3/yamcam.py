#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# yamcam.py - Main script to run YamCam with multiple cameras

import yamcam_config
from camera_audio_stream import CameraAudioStream
from yamcam_functions import analyze_audio_waveform, start_mqtt, report, rank_sounds, group_scores

# Initialize MQTT
start_mqtt()

# Define analyze_callback to handle classification and reporting
def analyze_callback(camera_name, waveform):
    # Analyze the audio waveform and get scores
    scores = analyze_audio_waveform(waveform)

    if scores is not None:
        # Rank the scores based on top_k setting
        ranked_scores = rank_sounds(scores, yamcam_config.top_k)

        # Group the scores if group_classes is set to True
        grouped_scores = group_scores(ranked_scores, yamcam_config.group_classes)

        # Report the results using MQTT
        report(camera_name, grouped_scores)
    else:
        yamcam_config.logger.error(f"No valid scores found for {camera_name}.")

# Set up cameras based on the configuration
cameras = yamcam_config.camera_settings

# Start audio streams for each camera
streams = []
for camera_name, settings in cameras.items():
    rtsp_url = settings['ffmpeg']['inputs'][0]['path']
    stream = CameraAudioStream(
        camera_name,
        rtsp_url,
        analyze_callback  # Pass the callback function here
    )
    stream.start()
    streams.append(stream)

# Stop streams when needed
def stop_all_streams():
    for stream in streams:
        stream.stop()

