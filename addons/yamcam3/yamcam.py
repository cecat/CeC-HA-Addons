#
# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# yamcam.py - Main script to run YamCam with multiple cameras
import yamcam_config
from camera_audio_stream import CameraAudioStream
from yamcam_functions import analyze_audio_waveform, start_mqtt

# Initialize MQTT
start_mqtt()

# Set up cameras based on the configuration
cameras = yamcam_config.camera_settings

# Start audio streams for each camera
streams = []
for camera_name, settings in cameras.items():
    rtsp_url = settings['ffmpeg']['inputs'][0]['path']
    stream = CameraAudioStream(
        camera_name,
        rtsp_url,
        analyze_audio_waveform
    )
    stream.start()
    streams.append(stream)

# Stop streams when needed
def stop_all_streams():
    for stream in streams:
        stream.stop()

