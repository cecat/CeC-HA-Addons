# yamcam3 - CeC September 2024
# (add streaming and threads)
# camera_audio_stream.py - Audio streaming class for YamCam

import subprocess
import threading
import numpy as np
import logging
import yamcam_config

logger = yamcam_config.logger

class CameraAudioStream:
    def __init__(self, camera_name, rtsp_url, analyze_callback):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.analyze_callback = analyze_callback
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = 31200  # 15,600 samples * 2 bytes per sample
        self.lock = threading.Lock()

    def start(self):
        # Adjustable parameters for FFmpeg command
        self.ffmpeg_probesize = '50M'            # Amount of data to probe
        self.ffmpeg_analyzeduration = '10M'      # Duration to analyze input stream
        self.ffmpeg_max_delay = '500000'         # Max delay in microseconds
        self.ffmpeg_use_low_delay = True         # Toggle low delay mode
        self.ffmpeg_use_nobuffer = True          # Toggle nobuffer mode

        # Construct the command with adjustable parameters
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',  # Transport mode
            '-i', self.rtsp_url,        # Input RTSP URL
            '-f', 's16le',              # Output format (raw audio)
            '-acodec', 'pcm_s16le',     # Audio codec (PCM 16-bit little-endian)
            '-ac', '1',                 # Mono audio
            '-ar', '16000',             # Sample rate: 16 kHz
            '-reorder_queue_size', '0', # Disable reordering to reduce latency
            '-use_wallclock_as_timestamps', '1',  # Use real-time timestamps
            '-probesize', self.ffmpeg_probesize,  # Adjustable probesize
            '-analyzeduration', self.ffmpeg_analyzeduration,  # Adjustable analyzeduration
            '-max_delay', self.ffmpeg_max_delay,  # Adjustable max delay
        ]

        # Conditionally add flags based on toggles
        if self.ffmpeg_use_low_delay:
            command.extend(['-flags', 'low_delay'])
        if self.ffmpeg_use_nobuffer:
            command.extend(['-fflags', 'nobuffer'])

        # Redirect to standard output for processing
        command.append('-')

        # Start the FFmpeg process with the constructed command
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        self.running = True
        self.thread = threading.Thread(target=self.read_stream, daemon=True)
        self.thread.start()
        logger.info(f"Started audio stream for {self.camera_name}")

    def read_stream(self):
        
        logger.debug(f"Started reading stream for {self.camera_name}")
        
        # Set the buffer size to match the expected size for YAMNet
        self.buffer_size = 31200  # 15,600 samples * 2 bytes per sample
        
        # Initialize raw_audio as an empty byte string to accumulate audio data
        raw_audio = b""
        logger.debug(f"Attempting to read from stream for {self.camera_name}")
        
        # Loop to accumulate audio data until the full buffer size is reached
        while len(raw_audio) < self.buffer_size:
            chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
            if not chunk:
                logger.error(f"Failed to read additional data from {self.camera_name}")
                break
            raw_audio += chunk
            logger.debug(f"Accumulated {len(raw_audio)} bytes for {self.camera_name}")
            
        # Check if the total read audio is incomplete
        if len(raw_audio) < self.buffer_size:
            logger.error(f"Incomplete audio capture for {self.camera_name}. Total buffer size: {len(raw_audio)}")
        else:
            logger.debug(f"Successfully accumulated full buffer for {self.camera_name}")
            
        # Handle FFmpeg stderr output
        try:
            stderr_output = self.process.stderr.read(1024).decode()
            if stderr_output:
                logger.error(f"FFmpeg stderr for {self.camera_name}: {stderr_output}")
        except Exception as e:
            logger.error(f"Error reading FFmpeg stderr for {self.camera_name}: {e}")

        logger.debug(f"Read {len(raw_audio)} bytes from {self.camera_name}")
        # Process the raw audio data if the buffer is complete
        if len(raw_audio) == self.buffer_size:
            try:
                self.analyze_callback(self.camera_name, raw_audio)
            except Exception as e:
                logger.error(f"Error during analysis callback for {self.camera_name}: {e}")
        else:
            logger.error(f"Incomplete audio capture prevented analysis for {self.camera_name}")
        # Handle any cleanup or stopping logic if the stream is no longer viable
        if not self.running:
            self.stop()

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"Stopped audio stream for {self.camera_name}")

