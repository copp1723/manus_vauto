"""
Configuration module for vAuto Feature Verification System.

This module handles loading and validating configuration from JSON files and environment variables.
"""

import os
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator


class BrowserConfig(BaseModel):
    """Browser configuration."""
    
    headless: bool = Field(True, description="Run browser in headless mode")
    timeout: int = Field(30, description="Default timeout in seconds")
    user_agent: Optional[str] = Field(None, description="Custom user agent string")
    window_size: Dict[str, int] = Field({"width": 1920, "height": 1080}, description="Browser window size")


class AuthenticationConfig(BaseModel):
    """Authentication configuration."""
    
    login_url: str = Field("https://app.vauto.com/login", description="vAuto login URL")
    session_timeout_minutes: int = Field(60, description="Session timeout in minutes")
    
    @validator('session_timeout_minutes')
    def validate_timeout(cls, v):
        """Validate session timeout."""
        if v < 1:
            raise ValueError("Session timeout must be at least 1 minute")
        return v


class InventoryConfig(BaseModel):
    """Inventory configuration."""
    
    max_vehicles: int = Field(10, description="Maximum number of vehicles to process")
    inventory_url: str = Field("https://app.vauto.com/inventory", description="vAuto inventory URL")
    
    @validator('max_vehicles')
    def validate_max_vehicles(cls, v):
        """Validate max vehicles."""
        if v < 1:
            raise ValueError("Max vehicles must be at least 1")
        return v


class FeatureMappingConfig(BaseModel):
    """Feature mapping configuration."""
    
    confidence_threshold: float = Field(0.8, description="Confidence threshold for feature matching")
    similarity_algorithm: str = Field("fuzzywuzzy.fuzz.token_sort_ratio", description="Algorithm for similarity matching")
    
    @validator('confidence_threshold')
    def validate_confidence_threshold(cls, v):
        """Validate confidence threshold."""
        if v < 0 or v > 1:
            raise ValueError("Confidence threshold must be between 0 and 1")
        return v


class ReportingConfig(BaseModel):
    """Reporting configuration."""
    
    email_recipients: list[str] = Field([], description="Email recipients for reports")
    report_format: str = Field("html", description="Report format (html, pdf)")
    include_screenshots: bool = Field(True, description="Include screenshots in reports")
    
    @validator('report_format')
    def validate_report_format(cls, v):
        """Validate report format."""
        if v not in ["html", "pdf"]:
            raise ValueError("Report format must be 'html' or 'pdf'")
        return v


class SystemConfig(BaseModel):
    """System configuration."""
    
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)
    feature_mapping: FeatureMappingConfig = Field(default_factory=FeatureMappingConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    debug: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v


def load_config(config_path: str = "configs/config.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file and environment variables.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    # Default configuration
    config = SystemConfig().dict()
    
    # Load from file if exists
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
                
            # Validate and merge file configuration
            validated_config = SystemConfig(**file_config).dict()
            
            # Update config with validated values
            for section, section_config in validated_config.items():
                if section in config and isinstance(section_config, dict):
                    config[section].update(section_config)
                else:
                    config[section] = section_config
                    
        except Exception as e:
            print(f"Error loading configuration from {config_path}: {str(e)}")
            print("Using default configuration")
    
    # Override with environment variables
    # Example: VAUTO_BROWSER_HEADLESS=false
    for section in config:
        if isinstance(config[section], dict):
            for key in config[section]:
                env_var = f"VAUTO_{section.upper()}_{key.upper()}"
                if env_var in os.environ:
                    value = os.environ[env_var]
                    
                    # Convert value to appropriate type
                    if isinstance(config[section][key], bool):
                        config[section][key] = value.lower() in ["true", "1", "yes"]
                    elif isinstance(config[section][key], int):
                        config[section][key] = int(value)
                    elif isinstance(config[section][key], float):
                        config[section][key] = float(value)
                    elif isinstance(config[section][key], list):
                        config[section][key] = value.split(",")
                    else:
                        config[section][key] = value
    
    return config
