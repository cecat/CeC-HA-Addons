"""
Pytest configuration and fixtures for yamcam3 tests.

Mocks external dependencies (TFLite, config files) so tests can run in CI.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch
from collections import deque

# Mock tflite_runtime before any imports that use it
sys.modules['tflite_runtime'] = MagicMock()
sys.modules['tflite_runtime.interpreter'] = MagicMock()


@pytest.fixture
def mock_yamcam_config():
    """Create a mock yamcam_config module with test settings."""
    config = MagicMock()
    
    # General settings
    config.default_min_score = 0.5
    config.noise_threshold = 0.1
    config.top_k = 10
    config.window_detect = 5
    config.persistence = 2
    config.decay = 10
    config.summary_interval = 15
    
    # Sound tracking
    config.sounds_to_track = ['alert', 'people', 'birds']
    config.sounds_filters = {
        'alert': {
            'min_score': 0.5,
            'start_threshold': 0.6,
            'continue_threshold': 0.4
        },
        'people': {
            'min_score': 0.6,
            'start_threshold': 0.6,
            'continue_threshold': 0.6
        },
        'birds': {
            'min_score': 0.7,
            'start_threshold': 0.7,
            'continue_threshold': 0.7
        }
    }
    
    # Class names (simplified for testing)
    config.class_names = [
        'alert.siren',
        'alert.civilDefenseSiren',
        'alert.alarm',
        'people.speech',
        'people.laughter',
        'birds.birdsong',
        'music.piano',
        'environment.wind',
        'silence.silence',
    ]
    
    # Camera settings
    config.camera_settings = {
        'test_cam': {'ffmpeg': {'inputs': [{'path': 'rtsp://test'}]}}
    }
    
    # Logger
    config.logger = MagicMock()
    
    # Shutdown event
    config.shutdown_event = MagicMock()
    config.shutdown_event.is_set.return_value = False
    
    return config


@pytest.fixture
def sample_scores():
    """Generate sample YAMNet-style scores array."""
    import numpy as np
    # Create a scores array like YAMNet outputs: shape (1, 521)
    scores = np.zeros((1, 521), dtype=np.float32)
    return scores


@pytest.fixture
def sample_scores_with_siren(sample_scores):
    """Scores array with high siren detection."""
    import numpy as np
    scores = sample_scores.copy()
    # Assuming siren classes are at indices 0, 1, 2 in our mock class_names
    scores[0, 0] = 0.65  # alert.siren
    scores[0, 1] = 0.70  # alert.civilDefenseSiren  
    scores[0, 2] = 0.30  # alert.alarm
    return scores


@pytest.fixture
def sample_scores_with_people(sample_scores):
    """Scores array with people detection."""
    import numpy as np
    scores = sample_scores.copy()
    scores[0, 3] = 0.75  # people.speech
    scores[0, 4] = 0.40  # people.laughter
    return scores
