"""
Feature Mapping Module for vAuto Feature Verification System.

Handles:
- Mapping between extracted window sticker features and vAuto checkboxes
- Fuzzy matching with configurable thresholds
- Learning mechanism for improving mappings over time
- Category-based boosting
- Dealership-specific overrides
"""

import logging
import json
import os
import asyncio
import re
from datetime import datetime
from fuzzywuzzy import fuzz
import importlib

logger = logging.getLogger(__name__)

class FeatureMapper:
    """
    Module for mapping between extracted features and vAuto checkboxes.
    """
    
    def __init__(self, config):
        """
        Initialize the feature mapping module.
        
        Args:
            config (dict): System configuration
        """
        self.config = config
        self.feature_mapping = {}
        self.mapping_file = os.path.join("configs", "feature_mapping.json")
        self.confidence_threshold = config["feature_mapping"]["confidence_threshold"]
        
        # Load the similarity algorithm based on config
        similarity_module_path = config["feature_mapping"]["similarity_algorithm"]
        module_parts = similarity_module_path.split('.')
        self.similarity_algorithm = getattr(
            importlib.import_module('.'.join(module_parts[:-1])),
            module_parts[-1]
        )
        
        # Initialize category boosts
        self.category_boosts = config.get('category_boosts', {
            'Convenience': 0.1,
            'Safety': 0.1,
            'Technology': 0.05,
            'Performance': 0.05,
            'Exterior': 0.05,
            'Interior': 0.05
        })
        
        # Load dealership overrides
        self.dealership_overrides = self._load_dealership_overrides()
        
        self._load_mapping()
        
        logger.info(f"Feature Mapping module initialized with {len(self.feature_mapping)} mappings")
    
    def _load_mapping(self):
        """
        Load feature mappings from file.
        """
        try:
            with open(self.mapping_file, 'r') as f:
                self.feature_mapping = json.load(f)
            
            logger.info(f"Loaded {len(self.feature_mapping)} feature mappings from {self.mapping_file}")
            
        except Exception as e:
            logger.error(f"Error loading feature mappings: {str(e)}")
            logger.warning("Using empty feature mapping")
            self.feature_mapping = {}
    
    def _load_dealership_overrides(self):
        """
        Load dealership-specific overrides from configuration.
        
        Returns:
            dict: Dictionary of dealership-specific overrides
        """
        override_file = self.config.get('dealership_override_file')
        dealership_id = self.config.get('dealership_id')
        
        if not override_file or not dealership_id:
            return {}
            
        try:
            with open(override_file, 'r') as f:
                all_overrides = json.load(f)
            
            # Get overrides for this specific dealership
            dealership_overrides = all_overrides.get(dealership_id, {})
            
            logger.info(f"Loaded {len(dealership_overrides)} dealership-specific overrides")
            return dealership_overrides
        except Exception as e:
            logger.error(f"Failed to load dealership overrides: {str(e)}")
            return {}
    
    def _save_mapping(self):
        """
        Save feature mappings to file.
        
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            with open(self.mapping_file, 'w') as f:
                json.dump(self.feature_mapping, f, indent=2)
            
            logger.info(f"Saved {len(self.feature_mapping)} feature mappings to {self.mapping_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving feature mappings: {str(e)}")
            return False
    
    def normalize_text(self, text):
        """
        Normalize text for comparison.
        
        Args:
            text (str): Text to normalize
            
        Returns:
            str: Normalized text
        """
        if not text:
            return ""
            
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove special characters
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Replace multiple spaces with a single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def get_category_boost(self, feature_text):
        """
        Get category boost based on feature text.
        
        Args:
            feature_text (str): Feature text to check for category indicators
            
        Returns:
            float: Boost value between 0 and 1
        """
        normalized_text = self.normalize_text(feature_text)
        
        for category, boost in self.category_boosts.items():
            if category.lower() in normalized_text:
                logger.debug(f"Applied category boost {boost} for category '{category}'")
                return boost
                
        return 0.0
    
    def check_dealership_override(self, feature_text):
        """
        Check if there's a dealership-specific override for this feature.
        
        Args:
            feature_text (str): Feature text to check
            
        Returns:
            tuple or None: (checkbox_name, 1.0) if override exists, None otherwise
        """
        normalized_text = self.normalize_text(feature_text)
        
        for pattern, checkbox in self.dealership_overrides.items():
            if pattern.lower() in normalized_text:
                logger.info(f"Applied dealership override: '{pattern}' -> '{checkbox}'")
                return checkbox, 1.0  # Override has maximum confidence
                
        return None
    
    async def map_features(self, extracted_features):
        """
        Map extracted features to vAuto checkboxes.
        
        Args:
            extracted_features (list): List of extracted features from window sticker
            
        Returns:
            dict: Dictionary mapping vAuto checkbox labels to boolean values
        """
        logger.info(f"Mapping {len(extracted_features)} extracted features")
        
        mapped_features = {}
        
        for feature in extracted_features:
            vAuto_feature = await self._map_single_feature(feature)
            if vAuto_feature:
                mapped_features[vAuto_feature] = True
        
        logger.info(f"Mapped {len(mapped_features)} features to vAuto checkboxes")
        return mapped_features
    
    async def _map_single_feature(self, feature_text):
        """
        Map a single feature to a vAuto checkbox.
        
        Args:
            feature_text (str): Extracted feature text
            
        Returns:
            str: vAuto checkbox label or None if no match
        """
        # Check dealership overrides first
        override = self.check_dealership_override(feature_text)
        if override:
            checkbox_name, _ = override
            return checkbox_name
        
        # First, try direct lookup in mapping dictionary
        for vAuto_feature, aliases in self.feature_mapping.items():
            if feature_text in aliases:
                logger.debug(f"Direct mapping found: '{feature_text}' -> '{vAuto_feature}'")
                return vAuto_feature
        
        # If no direct match, use fuzzy matching
        best_match = None
        best_score = 0
        
        for vAuto_feature, aliases in self.feature_mapping.items():
            for alias in aliases:
                # Try different fuzzy matching algorithms
                base_score = self.similarity_algorithm(feature_text.lower(), alias.lower())
                
                # Apply category boost if applicable
                category_boost = self.get_category_boost(feature_text)
                final_score = min(1.0, base_score + category_boost)
                
                if final_score > best_score:
                    best_score = final_score
                    best_match = vAuto_feature
        
        # Check if score exceeds confidence threshold
        if best_score >= self.confidence_threshold:
            logger.debug(f"Fuzzy mapping found: '{feature_text}' -> '{best_match}' (score: {best_score})")
            return best_match
        else:
            logger.debug(f"No mapping found for feature: '{feature_text}' (best score: {best_score})")
            return None

class MappingLearner:
    """
    Learning mechanism to improve feature mappings over time.
    """
    
    def __init__(self, mapper):
        """
        Initialize the mapping learner.
        
        Args:
            mapper (FeatureMapper): Feature mapper instance
        """
        self.mapper = mapper
        self.corrections = {}  # Store user corrections
        self.corrections_file = os.path.join("configs", "mapping_corrections.json")
        
        self._load_corrections()
        
        logger.info("Mapping Learner initialized")
    
    def _load_corrections(self):
        """
        Load mapping corrections from file.
        """
        try:
            if os.path.exists(self.corrections_file):
                with open(self.corrections_file, 'r') as f:
                    self.corrections = json.load(f)
                
                logger.info(f"Loaded {len(self.corrections)} mapping corrections from {self.corrections_file}")
            else:
                logger.info("No mapping corrections file found")
                self.corrections = {}
                
        except Exception as e:
            logger.error(f"Error loading mapping corrections: {str(e)}")
            logger.warning("Using empty corrections")
            self.corrections = {}
    
    def _save_corrections(self):
        """
        Save mapping corrections to file.
        
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            with open(self.corrections_file, 'w') as f:
                json.dump(self.corrections, f, indent=2)
            
            logger.info(f"Saved {len(self.corrections)} mapping corrections to {self.corrections_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving mapping corrections: {str(e)}")
            return False
    
    def record_correction(self, feature_text, old_mapping, new_mapping):
        """
        Record a user correction for learning.
        
        Args:
            feature_text (str): Extracted feature text
            old_mapping (str): Old vAuto checkbox mapping (or None)
            new_mapping (str): New vAuto checkbox mapping
            
        Returns:
            bool: True if correction recorded, False otherwise
        """
        logger.info(f"Recording correction: '{feature_text}' from '{old_mapping}' to '{new_mapping}'")
        
        try:
            if feature_text not in self.corrections:
                self.corrections[feature_text] = []
                
            self.corrections[feature_text].append({
                'old': old_mapping,
                'new': new_mapping,
                'timestamp': datetime.now().isoformat()
            })
            
            # Add the new mapping
            self.mapper.add_mapping(feature_text, new_mapping)
            
            # Save corrections
            saved = self._save_corrections()
            
            return saved
                
        except Exception as e:
            logger.error(f"Error recording correction: {str(e)}")
            return False
    
    def suggest_improvements(self):
        """
        Suggest improvements to the mapping based on corrections.
        
        Returns:
            dict: Dictionary of suggested improvements
        """
        logger.info("Suggesting mapping improvements")
        
        suggestions = {}
        
        try:
            # Analyze correction patterns
            for feature_text, corrections in self.corrections.items():
                if len(corrections) >= 3:  # Require at least 3 corrections
                    # Count the frequency of new mappings
                    mapping_counts = {}
                    for correction in corrections:
                        new_mapping = correction['new']
                        mapping_counts[new_mapping] = mapping_counts.get(new_mapping, 0) + 1
                    
                    # Find the most common mapping
                    most_common = max(mapping_counts.items(), key=lambda x: x[1])
                    most_common_mapping, count = most_common
                    
                    # If the most common mapping is used more than 75% of the time, suggest it
                    if count / len(corrections) >= 0.75:
                        suggestions[feature_text] = most_common_mapping
            
            logger.info(f"Generated {len(suggestions)} mapping improvement suggestions")
            return suggestions
                
        except Exception as e:
            logger.error(f"Error suggesting improvements: {str(e)}")
            return {}
    
    def apply_suggestions(self):
        """
        Apply suggested improvements to the mapping.
        
        Returns:
            int: Number of improvements applied
        """
        logger.info("Applying mapping improvement suggestions")
        
        count = 0
        
        try:
            # Get suggestions
            suggestions = self.suggest_improvements()
            
            # Apply each suggestion
            for feature_text, suggested_mapping in suggestions.items():
                # Check current mapping
                current_mapping = None
                for vAuto_feature, aliases in self.mapper.feature_mapping.items():
                    if feature_text in aliases:
                        current_mapping = vAuto_feature
                        break
                
                # Skip if already mapped correctly
                if current_mapping == suggested_mapping:
                    continue
                
                # Apply the suggested mapping
                if current_mapping:
                    # Update existing mapping
                    self.mapper.update_mapping(feature_text, feature_text, suggested_mapping)
                else:
                    # Add new mapping
                    self.mapper.add_mapping(feature_text, suggested_mapping)
                
                count += 1
            
            logger.info(f"Applied {count} mapping improvements")
            return count
                
        except Exception as e:
            logger.error(f"Error applying suggestions: {str(e)}")
            return 0
