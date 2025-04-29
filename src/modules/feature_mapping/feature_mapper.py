"""
Feature Mapping Module for vAuto Feature Verification System.

Handles:
- Mapping extracted features to vAuto checkboxes
- Managing feature mapping database
- Fuzzy matching for feature recognition
"""

import logging
import os
import json
from typing import Dict, List, Optional, Any, Tuple
import asyncio

from fuzzywuzzy import fuzz, process

from core.interfaces import FeatureMapperInterface
from utils.common import normalize_text, load_json_file, save_json_file

logger = logging.getLogger(__name__)


class FeatureMapper(FeatureMapperInterface):
    """
    Module for mapping extracted features to vAuto checkboxes.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the feature mapper.
        
        Args:
            config: System configuration
        """
        self.config = config
        self.mapping_file = os.path.join("configs", "feature_mapping.json")
        self.feature_mapping = self._load_mapping()
        self.confidence_threshold = config["feature_mapping"]["confidence_threshold"]
        
        logger.info("Feature Mapper initialized")
    
    def _load_mapping(self) -> Dict[str, List[str]]:
        """
        Load feature mapping from file.
        
        Returns:
            dict: Feature mapping dictionary
        """
        mapping = load_json_file(self.mapping_file, default={})
        
        if not mapping:
            # Create default mapping
            mapping = self._create_default_mapping()
            save_json_file(self.mapping_file, mapping)
            logger.info("Created default feature mapping")
        else:
            logger.info(f"Loaded feature mapping with {len(mapping)} entries")
        
        return mapping
    
    def _create_default_mapping(self) -> Dict[str, List[str]]:
        """
        Create default feature mapping.
        
        Returns:
            dict: Default feature mapping dictionary
        """
        # This is a simplified example of feature mapping
        # In a real implementation, this would be more comprehensive
        return {
            "Sunroof": ["sunroof", "moonroof", "panoramic roof", "glass roof"],
            "Leather Seats": ["leather seats", "leather interior", "leather upholstery"],
            "Navigation System": ["navigation system", "nav system", "gps navigation", "built-in navigation"],
            "Bluetooth": ["bluetooth", "bluetooth connectivity", "bluetooth audio"],
            "Backup Camera": ["backup camera", "rear view camera", "rear camera", "reversing camera"],
            "Heated Seats": ["heated seats", "heated front seats", "heated rear seats"],
            "Blind Spot Monitor": ["blind spot monitor", "blind spot detection", "blind spot warning"],
            "Lane Departure Warning": ["lane departure warning", "lane departure alert", "lane keeping assist"],
            "Adaptive Cruise Control": ["adaptive cruise control", "dynamic cruise control", "radar cruise control"],
            "Keyless Entry": ["keyless entry", "remote entry", "smart key"],
            "Push Button Start": ["push button start", "push start", "keyless start", "remote start"],
            "Power Liftgate": ["power liftgate", "power tailgate", "hands-free liftgate"],
            "Third Row Seating": ["third row seating", "3rd row seating", "third row seats", "7 passenger seating"],
            "All Wheel Drive": ["all wheel drive", "awd", "4wd", "four wheel drive", "4 wheel drive"],
            "Apple CarPlay": ["apple carplay", "carplay"],
            "Android Auto": ["android auto"],
            "Wireless Charging": ["wireless charging", "qi charging", "wireless phone charging"],
            "Premium Sound System": ["premium sound", "bose sound", "harman kardon", "jbl sound", "premium audio"],
            "Parking Sensors": ["parking sensors", "park assist", "parking assist", "front parking sensors", "rear parking sensors"],
            "Collision Warning": ["collision warning", "forward collision warning", "collision alert", "pre-collision system"]
        }
    
    async def map_features(self, extracted_features: List[str]) -> Dict[str, bool]:
        """
        Map extracted features to vAuto checkboxes.
        
        Args:
            extracted_features: List of extracted features
            
        Returns:
            dict: Mapping of vAuto checkbox names to boolean values
        """
        logger.info(f"Mapping {len(extracted_features)} extracted features to vAuto checkboxes")
        
        mapped_features = {}
        
        try:
            # Normalize extracted features
            normalized_features = [normalize_text(feature) for feature in extracted_features]
            
            # Process each vAuto checkbox
            for vauto_feature, feature_variants in self.feature_mapping.items():
                # Check if any variant matches any extracted feature
                is_present = await self._check_feature_presence(normalized_features, feature_variants)
                mapped_features[vauto_feature] = is_present
            
            logger.info(f"Mapped features: {sum(1 for v in mapped_features.values() if v)} present out of {len(mapped_features)} total")
            return mapped_features
            
        except Exception as e:
            logger.error(f"Error mapping features: {str(e)}")
            return {}
    
    async def _check_feature_presence(self, normalized_features: List[str], feature_variants: List[str]) -> bool:
        """
        Check if any feature variant is present in the extracted features.
        
        Args:
            normalized_features: List of normalized extracted features
            feature_variants: List of feature variants to check
            
        Returns:
            bool: True if any variant is present, False otherwise
        """
        # Normalize feature variants
        normalized_variants = [normalize_text(variant) for variant in feature_variants]
        
        # Check for exact matches first
        for variant in normalized_variants:
            if variant in normalized_features:
                return True
        
        # If no exact match, use fuzzy matching
        return await self._fuzzy_match_feature(normalized_features, normalized_variants)
    
    async def _fuzzy_match_feature(self, normalized_features: List[str], normalized_variants: List[str]) -> bool:
        """
        Use fuzzy matching to check if any feature variant is present.
        
        Args:
            normalized_features: List of normalized extracted features
            normalized_variants: List of normalized feature variants
            
        Returns:
            bool: True if any variant matches with sufficient confidence, False otherwise
        """
        # Run fuzzy matching in a separate thread to avoid blocking
        result = await asyncio.to_thread(
            self._fuzzy_match_feature_sync,
            normalized_features,
            normalized_variants
        )
        
        return result
    
    def _fuzzy_match_feature_sync(self, normalized_features: List[str], normalized_variants: List[str]) -> bool:
        """
        Synchronous function for fuzzy matching.
        
        Args:
            normalized_features: List of normalized extracted features
            normalized_variants: List of normalized feature variants
            
        Returns:
            bool: True if any variant matches with sufficient confidence, False otherwise
        """
        for variant in normalized_variants:
            for feature in normalized_features:
                # Skip very short features to avoid false positives
                if len(feature) < 4 or len(variant) < 4:
                    continue
                
                # Use token sort ratio for better matching of phrases
                ratio = fuzz.token_sort_ratio(variant, feature)
                
                # Check if ratio exceeds threshold
                if ratio >= self.confidence_threshold * 100:  # Convert from 0-1 to 0-100
                    return True
        
        return False
    
    def add_mapping(self, feature_text: str, vauto_feature: str) -> bool:
        """
        Add a new mapping.
        
        Args:
            feature_text: Feature text to map
            vauto_feature: vAuto checkbox name
            
        Returns:
            bool: True if mapping added successfully, False otherwise
        """
        logger.info(f"Adding mapping: '{feature_text}' -> '{vauto_feature}'")
        
        try:
            # Normalize feature text
            normalized_text = normalize_text(feature_text)
            
            # Check if vAuto feature exists in mapping
            if vauto_feature in self.feature_mapping:
                # Check if feature text already exists
                if normalized_text in self.feature_mapping[vauto_feature]:
                    logger.warning(f"Mapping already exists: '{feature_text}' -> '{vauto_feature}'")
                    return True
                
                # Add feature text to existing mapping
                self.feature_mapping[vauto_feature].append(normalized_text)
            else:
                # Create new mapping
                self.feature_mapping[vauto_feature] = [normalized_text]
            
            # Save mapping
            success = save_json_file(self.mapping_file, self.feature_mapping)
            
            if success:
                logger.info(f"Mapping added successfully: '{feature_text}' -> '{vauto_feature}'")
            else:
                logger.error(f"Failed to save mapping: '{feature_text}' -> '{vauto_feature}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding mapping: {str(e)}")
            return False
    
    def update_mapping(self, old_feature: str, new_feature: str, vauto_feature: str) -> bool:
        """
        Update an existing mapping.
        
        Args:
            old_feature: Old feature text
            new_feature: New feature text
            vauto_feature: vAuto checkbox name
            
        Returns:
            bool: True if mapping updated successfully, False otherwise
        """
        logger.info(f"Updating mapping: '{old_feature}' -> '{new_feature}' for '{vauto_feature}'")
        
        try:
            # Normalize feature texts
            normalized_old = normalize_text(old_feature)
            normalized_new = normalize_text(new_feature)
            
            # Check if vAuto feature exists in mapping
            if vauto_feature not in self.feature_mapping:
                logger.error(f"vAuto feature not found: '{vauto_feature}'")
                return False
            
            # Check if old feature exists
            if normalized_old not in self.feature_mapping[vauto_feature]:
                logger.error(f"Old feature not found: '{old_feature}' for '{vauto_feature}'")
                return False
            
            # Remove old feature
            self.feature_mapping[vauto_feature].remove(normalized_old)
            
            # Add new feature
            self.feature_mapping[vauto_feature].append(normalized_new)
            
            # Save mapping
            success = save_json_file(self.mapping_file, self.feature_mapping)
            
            if success:
                logger.info(f"Mapping updated successfully: '{old_feature}' -> '{new_feature}' for '{vauto_feature}'")
            else:
                logger.error(f"Failed to save mapping: '{old_feature}' -> '{new_feature}' for '{vauto_feature}'")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating mapping: {str(e)}")
            return False
