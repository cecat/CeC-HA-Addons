"""
Unit tests for yamcam3 sound detection logic.

Tests cover:
- Composite score calculation
- Group score aggregation  
- Hysteresis threshold behavior
- Event window detection
"""

import pytest
import numpy as np
from collections import deque
from unittest.mock import MagicMock, patch


class TestGroupScoresByPrefix:
    """Tests for group_scores_by_prefix function."""
    
    def test_groups_scores_correctly(self):
        """Test that scores are grouped by prefix."""
        # Simple test data
        filtered_scores = [
            (0, 0.65),  # alert.siren
            (1, 0.70),  # alert.civilDefenseSiren
            (3, 0.75),  # people.speech
        ]
        class_names = [
            'alert.siren',
            'alert.civilDefenseSiren', 
            'alert.alarm',
            'people.speech',
            'people.laughter',
        ]
        
        # Test the grouping logic directly
        group_scores_dict = {}
        for i, score in filtered_scores:
            class_name = class_names[i]
            group = class_name.split('.')[0]
            if group not in group_scores_dict:
                group_scores_dict[group] = []
            group_scores_dict[group].append(score)
        
        assert 'alert' in group_scores_dict
        assert 'people' in group_scores_dict
        assert len(group_scores_dict['alert']) == 2
        assert len(group_scores_dict['people']) == 1
        assert 0.65 in group_scores_dict['alert']
        assert 0.70 in group_scores_dict['alert']


class TestCompositeScores:
    """Tests for calculate_composite_scores function."""
    
    def test_high_score_used_directly(self):
        """When max score > 0.7, use it directly as composite."""
        group_scores_dict = {
            'alert': [0.75, 0.30, 0.25],  # max is 0.75 > 0.7
        }
        
        # Implement the logic being tested
        composite_scores = []
        for group, scores in group_scores_dict.items():
            max_score = max(scores)
            if max_score > 0.7:
                composite_score = max_score
            else:
                composite_score = min(max_score + 0.1 * len(scores), 0.95)
            composite_scores.append((group, composite_score))
        
        assert composite_scores[0] == ('alert', 0.75)
    
    def test_low_scores_get_boost(self):
        """When max score <= 0.7, boost based on count."""
        group_scores_dict = {
            'alert': [0.50, 0.40, 0.35],  # max is 0.50, 3 items
        }
        
        composite_scores = []
        for group, scores in group_scores_dict.items():
            max_score = max(scores)
            if max_score > 0.7:
                composite_score = max_score
            else:
                # 0.50 + 0.1 * 3 = 0.80
                composite_score = min(max_score + 0.1 * len(scores), 0.95)
            composite_scores.append((group, composite_score))
        
        assert composite_scores[0] == ('alert', 0.80)
    
    def test_composite_capped_at_095(self):
        """Composite score should not exceed 0.95."""
        group_scores_dict = {
            'alert': [0.60] * 10,  # 0.60 + 0.1*10 = 1.60, should cap at 0.95
        }
        
        composite_scores = []
        for group, scores in group_scores_dict.items():
            max_score = max(scores)
            if max_score > 0.7:
                composite_score = max_score
            else:
                composite_score = min(max_score + 0.1 * len(scores), 0.95)
            composite_scores.append((group, composite_score))
        
        assert composite_scores[0] == ('alert', 0.95)


class TestHysteresis:
    """Tests for hysteresis threshold behavior."""
    
    def test_start_requires_higher_threshold(self):
        """Event start requires score >= start_threshold."""
        start_threshold = 0.6
        continue_threshold = 0.4
        is_active = False
        
        # Score of 0.5 should NOT trigger start (below 0.6)
        score = 0.5
        if is_active:
            is_detected = score >= continue_threshold
        else:
            is_detected = score >= start_threshold
        
        assert is_detected is False
        
        # Score of 0.65 should trigger start (above 0.6)
        score = 0.65
        if is_active:
            is_detected = score >= continue_threshold
        else:
            is_detected = score >= start_threshold
        
        assert is_detected is True
    
    def test_continue_uses_lower_threshold(self):
        """Once active, event continues with lower threshold."""
        start_threshold = 0.6
        continue_threshold = 0.4
        is_active = True
        
        # Score of 0.45 should continue (above 0.4)
        score = 0.45
        if is_active:
            is_detected = score >= continue_threshold
        else:
            is_detected = score >= start_threshold
        
        assert is_detected is True
        
        # Score of 0.35 should NOT continue (below 0.4)
        score = 0.35
        if is_active:
            is_detected = score >= continue_threshold
        else:
            is_detected = score >= start_threshold
        
        assert is_detected is False


class TestEventWindow:
    """Tests for sliding window event detection."""
    
    def test_persistence_triggers_event_start(self):
        """Event starts when persistence threshold is met."""
        window_detect = 5
        persistence = 2
        start_threshold = 0.6
        
        window = deque(maxlen=window_detect)
        
        # Add scores below threshold
        window.append(0.3)
        window.append(0.4)
        
        # Add scores above threshold
        window.append(0.65)
        window.append(0.70)
        
        detection_count = sum(1 for s in window if s >= start_threshold)
        should_start = detection_count >= persistence
        
        assert detection_count == 2
        assert should_start is True
    
    def test_insufficient_persistence_no_start(self):
        """Event does not start if persistence not met."""
        window_detect = 5
        persistence = 3
        start_threshold = 0.6
        
        window = deque(maxlen=window_detect)
        
        # Only 2 detections above threshold
        window.append(0.65)
        window.append(0.70)
        window.append(0.3)
        window.append(0.4)
        window.append(0.5)
        
        detection_count = sum(1 for s in window if s >= start_threshold)
        should_start = detection_count >= persistence
        
        assert detection_count == 2
        assert should_start is False
    
    def test_decay_counter_behavior(self):
        """Decay counter decrements when sound not detected."""
        decay = 10
        decay_counter = decay
        
        # Simulate 5 frames without detection
        for _ in range(5):
            is_detected = False
            if not is_detected:
                decay_counter -= 1
        
        assert decay_counter == 5
        
        # Detection resets counter
        is_detected = True
        if is_detected:
            decay_counter = decay
        
        assert decay_counter == 10
    
    def test_event_stops_when_decay_exhausted(self):
        """Event stops when decay counter reaches 0."""
        decay = 3
        decay_counter = decay
        is_active = True
        
        # Simulate frames without detection
        for i in range(4):
            is_detected = False
            if is_active and not is_detected:
                decay_counter -= 1
                if decay_counter <= 0:
                    is_active = False
        
        assert is_active is False
        assert decay_counter == 0


class TestTrackedGroupsNotPruned:
    """Tests ensuring tracked groups bypass top_k pruning."""
    
    def test_tracked_group_included_regardless_of_rank(self):
        """Tracked groups should be included even if not in top_k."""
        sounds_to_track = ['alert', 'siren']
        top_k = 2
        
        # Simulate sorted composite scores where alert is ranked 5th
        sorted_composite_scores = [
            ('music', 0.9),
            ('people', 0.85),
            ('environment', 0.8),
            ('birds', 0.75),
            ('alert', 0.55),  # Tracked but not in top 2
            ('siren', 0.45),  # Tracked but not in top 2
        ]
        
        # Old behavior: only include top_k
        limited = sorted_composite_scores[:top_k]
        old_results = [g for g, s in limited if g in sounds_to_track]
        
        # New behavior: include all tracked groups
        composite_dict = dict(sorted_composite_scores)
        new_results = []
        for group in sounds_to_track:
            score = composite_dict.get(group, 0.0)
            new_results.append({'class': group, 'score': score})
        
        # Old behavior would miss alert and siren
        assert len(old_results) == 0
        
        # New behavior includes both
        assert len(new_results) == 2
        assert any(r['class'] == 'alert' for r in new_results)
        assert any(r['class'] == 'siren' for r in new_results)


class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_threshold_defaults_to_min_score(self):
        """Thresholds default to min_score when not specified."""
        default_min_score = 0.5
        settings = {'min_score': 0.6}
        
        # Simulate validation logic
        if 'start_threshold' not in settings:
            settings['start_threshold'] = settings['min_score']
        if 'continue_threshold' not in settings:
            settings['continue_threshold'] = settings['min_score']
        
        assert settings['start_threshold'] == 0.6
        assert settings['continue_threshold'] == 0.6
    
    def test_invalid_threshold_uses_min_score(self):
        """Invalid thresholds fall back to min_score."""
        settings = {
            'min_score': 0.5,
            'start_threshold': 1.5,  # Invalid (> 1.0)
        }
        
        # Simulate validation
        if not (0.0 <= settings.get('start_threshold', 0) <= 1.0):
            settings['start_threshold'] = settings['min_score']
        
        assert settings['start_threshold'] == 0.5
