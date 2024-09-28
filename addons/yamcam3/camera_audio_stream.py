# yamcam3 - CeC September 2024
# (add streaming and threads)
#
# audio streaming class
#
import subprocess
import time
import threading
import numpy as np
import logging
import select
import yamcam_config
from yamcam_config import interpreter, input_details, output_details

logger = yamcam_config.logger

###################################

class CameraAudioStream:

    def __init__(self, camera_name, rtsp_url, analyze_callback):
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.analyze_callback = analyze_callback  # Assign the callback function
        self.process = None
        self.thread = None
        self.running = False
        self.buffer_size = 31200  # YAMNet needs 15,600 samples, 2B per sample
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
        logger.info(f"{self.camera_name}: Started audio stream ")

    def invoke_with_timeout(self, interpreter, timeout=5):
        def target():
            try:
                interpreter.invoke()
            except Exception as e:
                logger.error(f"{self.camera_name}: Error during interpreter invocation: {e}")

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            logger.error(f"{self.camera_name}: Interpreter invocation timed out.")
            return False
        return True

    def read_stream(self):
        logger.debug(f"{self.camera_name}: Started reading stream.")

        # Set the buffer size to match the expected size for YAMNet
        self.buffer_size = 31200  # 15,600 samples * 2 bytes per sample
        retry_count = 0  # Initialize retry counter

        while self.running:  # Continuous loop for reading the stream
            raw_audio = b""
            logger.debug(f"{self.camera_name}: Attempting to read from stream.")

            # Loop to accumulate audio data until the full buffer size is reached
            while len(raw_audio) < self.buffer_size:
                chunk = self.process.stdout.read(self.buffer_size - len(raw_audio))
                if not chunk:
                    logger.error(f"{self.camera_name}: Failed to read additional data.")
                    retry_count += 1
                    if retry_count >= 3:  # After 3 failed attempts, mark stream as unusable
                        logger.error(f"{self.camera_name}: Stream marked as unusable after 3 failed attempts.")
                        self.stop()  # Stop the stream gracefully
                        return
                    time.sleep(2)  # Wait before retrying
                    continue
                raw_audio += chunk
                retry_count = 0  # Reset retry counter on successful read
                #logger.debug(f"{self.camera_name}: Accumulated {len(raw_audio)} bytes.")

            # Check if the total read audio is incomplete
            if len(raw_audio) < self.buffer_size:
                logger.error(f"{self.camera_name}: Incomplete audio capture. Total buffer size: {len(raw_audio)}")
                continue  # Skip analysis and retry reading

            logger.debug(f"{self.camera_name}: Successfully accumulated full buffer.")

            # Handle FFmpeg stderr output
            try:
                stderr_output = self.process.stderr.read(1024).decode()
                if stderr_output:
                    logger.error(f"{self.camera_name} - FFmpeg sderr: {stderr_output}")
            except Exception as e:
                logger.error(f"{self.camera_name} - Error reading FFmpeg stderr: {e}")

            logger.debug(f"{self.camera_name}: Read {len(raw_audio)} bytes.")

            # Process the raw audio data if the buffer is complete
            if len(raw_audio) == self.buffer_size:
                waveform = np.frombuffer(raw_audio, dtype=np.int16) / 32768.0
                waveform = np.squeeze(waveform)  # Ensure waveform is a 1D array
                logger.debug(f"{self.camera_name}: Waveform length: {len(waveform)}")
                logger.debug(f"{self.camera_name}: Segment shape: {waveform.shape}")
                self.analyze_callback(self.camera_name, waveform)  # Invoke callback with waveform
            else:
                logger.error(f"{self.camera_name}: Incomplete audio capture prevented analysis.")



# no longer used:
    def score_segment(self, raw_audio):
        try:

            # Ensure waveform is in the correct shape (15600,) for the interpreter
            if len(waveform) == 15600:
                interpreter.set_tensor(input_details[0]['index'], waveform.astype(np.float32))

                # Use the timeout mechanism to invoke the interpreter
                if not self.invoke_with_timeout(interpreter):
                    logger.error(f"{self.camera_name}: Failed to analyze audio due to interpreter timeout.")
                    return None

                scores = interpreter.get_tensor(output_details[0]['index'])
                #logger.debug(f"Scores shape: {scores.shape}, Scores: {scores}")
                logger.debug(f"{self.camera_name}: got scores")

                if len(scores) == 0:
                    logger.error(f"{self.camera_name}: No scores available for analysis.")
                    return None
            else:
                logger.error(f"{self.camera_name}: Waveform size mismatch for analysis: {len(waveform)} != 15600")

        except Exception as e:
            logger.error(f"{self.camera_name}: Error during interpreter invocation: {e}")

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()
                self.process = None
            logger.info(f"{self.camera_name}: Stopped audio stream ")

