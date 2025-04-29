"""
Unit tests for the feature mapper module.

This module contains tests for the FeatureMapper class.
"""

import pytest
import asyncio
import os
import json
from unittest.mock import MagicMock, patch, mock_open

from modules.feature_mapping.feature_mapper import FeatureMapper


@pytest.fixture
def config():
    """Create a mock configuration."""
    return {
        "feature_mapping": {
            "confidence_threshold": 0.8,
            "similarity_algorithm": "fuzzywuzzy.fuzz.token_sort_ratio"
        }
    }


@pytest.fixture
def feature_mapper(config):
    """Create a feature mapper with mocked dependencies."""
    with patch("utils.common.load_json_file") as mock_load, \
         patch("utils.common.save_json_file", return_value=True):
        # Mock feature mapping data
        mock_load.return_value = {
            "Sunroof": ["sunroof", "moonroof", "panoramic roof"],
            "Leather Seats": ["leather seats", "leather interior"],
            "Navigation System": ["navigation system", "nav system", "gps navigation"]
        }
        
        return FeatureMapper(config)


@pytest.mark.asyncio
async def test_map_features_exact_match(feature_mapper):
    """Test mapping features with exact matches."""
    # Test data
    extracted_features = [
        "Sunroof",
        "Leather seats",
        "Some other feature"
    ]
    
    # Call map_features method
    result = await feature_mapper.map_features(extracted_features)
    
    # Verify result
    assert result["Sunroof"] is True
    assert result["Leather Seats"] is True
    assert result["Navigation System"] is False


@pytest.mark.asyncio
async def test_map_features_fuzzy_match(feature_mapper):
    """Test mapping features with fuzzy matching."""
    # Test data
    extracted_features = [
        "Panoramic glass roof",  # Should match "panoramic roof" for Sunroof
        "Interior with leather",  # Should match "leather interior" for Leather Seats
        "Some other feature"
    ]
    
    # Mock _fuzzy_match_feature to simulate matches
    feature_mapper._fuzzy_match_feature = MagicMock(side_effect=[
        asyncio.Future(),  # Sunroof
        asyncio.Future(),  # Leather Seats
        asyncio.Future()   # Navigation System
    ])
    feature_mapper._fuzzy_match_feature.side_effect[0].set_result(True)   # Sunroof matches
    feature_mapper._fuzzy_match_feature.side_effect[1].set_result(True)   # Leather Seats matches
    feature_mapper._fuzzy_match_feature.side_effect[2].set_result(False)  # Navigation System doesn't match
    
    # Call map_features method
    result = await feature_mapper.map_features(extracted_features)
    
    # Verify result
    assert result["Sunroof"] is True
    assert result["Leather Seats"] is True
    assert result["Navigation System"] is False


@pytest.mark.asyncio
async def test_map_features_no_matches(feature_mapper):
    """Test mapping features with no matches."""
    # Test data
    extracted_features = [
        "Air conditioning",
        "Power windows",
        "Alloy wheels"
    ]
    
    # Call map_features method
    result = await feature_mapper.map_features(extracted_features)
    
    # Verify result
    assert result["Sunroof"] is False
    assert result["Leather Seats"] is False
    assert result["Navigation System"] is False


@pytest.mark.asyncio
async def test_fuzzy_match_feature(feature_mapper):
    """Test fuzzy matching of features."""
    # Test data
    normalized_features = ["panoramic glass roof", "interior with leather"]
    normalized_variants = ["panoramic roof", "moonroof", "sunroof"]
    
    # Mock _fuzzy_match_feature_sync to return True
    feature_mapper._fuzzy_match_feature_sync = MagicMock(return_value=True)
    
    # Call _fuzzy_match_feature method
    result = await feature_mapper._fuzzy_match_feature(normalized_features, normalized_variants)
    
    # Verify result
    assert result is True
    
    # Verify _fuzzy_match_feature_sync was called with correct arguments
    feature_mapper._fuzzy_match_feature_sync.assert_called_once_with(normalized_features, normalized_variants)


def test_fuzzy_match_feature_sync(feature_mapper):
    """Test synchronous fuzzy matching of features."""
    # Test cases
    test_cases = [
        # Should match (high similarity)
        (["panoramic glass roof"], ["panoramic roof"], True),
        (["leather interior seats"], ["leather seats"], True),
        (["navigation system with maps"], ["navigation system"], True),
        
        # Should not match (low similarity)
        (["cloth seats"], ["leather seats"], False),
        (["regular roof"], ["panoramic roof"], False),
        (["radio system"], ["navigation system"], False)
    ]
    
    # Test each case
    for features, variants, expected_result in test_cases:
        with patch("fuzzywuzzy.fuzz.token_sort_ratio") as mock_fuzz:
            # Set up mock to return high or low similarity score
            mock_fuzz.return_value = 90 if expected_result else 60
            
            # Call _fuzzy_match_feature_sync method
            result = feature_mapper._fuzzy_match_feature_sync(features, variants)
            
            # Verify result
            assert result is expected_result


def test_add_mapping_new_feature(feature_mapper):
    """Test adding a new mapping for a new feature."""
    # Initial state
    assert "Blind Spot Monitor" not in feature_mapper.feature_mapping
    
    # Call add_mapping method
    result = feature_mapper.add_mapping("blind spot detection", "Blind Spot Monitor")
    
    # Verify result
    assert result is True
    
    # Verify feature mapping was updated
    assert "Blind Spot Monitor" in feature_mapper.feature_mapping
    assert "blind spot detection" in feature_mapper.feature_mapping["Blind Spot Monitor"]


def test_add_mapping_existing_feature(feature_mapper):
    """Test adding a new mapping for an existing feature."""
    # Initial state
    assert "Sunroof" in feature_mapper.feature_mapping
    assert "glass roof" not in feature_mapper.feature_mapping["Sunroof"]
    
    # Call add_mapping method
    result = feature_mapper.add_mapping("glass roof", "Sunroof")
    
    # Verify result
    assert result is True
    
    # Verify feature mapping was updated
    assert "glass roof" in feature_mapper.feature_mapping["Sunroof"]


def test_add_mapping_duplicate(feature_mapper):
    """Test adding a duplicate mapping."""
    # Initial state
    assert "Sunroof" in feature_mapper.feature_mapping
    assert "sunroof" in feature_mapper.feature_mapping["Sunroof"]
    
    # Call add_mapping method
    result = feature_mapper.add_mapping("sunroof", "Sunroof")
    
    # Verify result
    assert result is True  # Should still return True for duplicates
    
    # Verify feature mapping was not changed
    assert feature_mapper.feature_mapping["Sunroof"].count("sunroof") == 1


def test_update_mapping_success(feature_mapper):
    """Test updating an existing mapping."""
    # Initial state
    assert "Sunroof" in feature_mapper.feature_mapping
    assert "sunroof" in feature_mapper.feature_mapping["Sunroof"]
    assert "electric sunroof" not in feature_mapper.feature_mapping["Sunroof"]
    
    # Call update_mapping method
    result = feature_mapper.update_mapping("sunroof", "electric sunroof", "Sunroof")
    
    # Verify result
    assert result is True
    
    # Verify feature mapping was updated
    assert "sunroof" not in feature_mapper.feature_mapping["Sunroof"]
    assert "electric sunroof" in feature_mapper.feature_mapping["Sunroof"]


def test_update_mapping_feature_not_found(feature_mapper):
    """Test updating a mapping when the feature doesn't exist."""
    # Initial state
    assert "Blind Spot Monitor" not in feature_mapper.feature_mapping
    
    # Call update_mapping method
    result = feature_mapper.update_mapping("blind spot detection", "blind spot monitor", "Blind Spot Monitor")
    
    # Verify result
    assert result is False


def test_update_mapping_variant_not_found(feature_mapper):
    """Test updating a mapping when the variant doesn't exist."""
    # Initial state
    assert "Sunroof" in feature_mapper.feature_mapping
    assert "electric sunroof" not in feature_mapper.feature_mapping["Sunroof"]
    
    # Call update_mapping method
    result = feature_mapper.update_mapping("electric sunroof", "power sunroof", "Sunroof")
    
    # Verify result
    assert result is False
