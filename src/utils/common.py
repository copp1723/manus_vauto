"""
Common utility functions for vAuto Feature Verification System.
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text by converting to lowercase, removing extra whitespace, etc.
    
    Args:
        text: Text to normalize
        
    Returns:
        str: Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    normalized = text.lower()
    
    # Replace newlines and tabs with spaces
    normalized = re.sub(r'[\n\t\r]+', ' ', normalized)
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized


def ensure_dir(directory: str) -> str:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        directory: Directory path
        
    Returns:
        str: Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return directory


def load_json_file(file_path: str, default: Optional[Any] = None) -> Any:
    """
    Load JSON from file.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Any: Loaded JSON data or default value
    """
    try:
        if not os.path.exists(file_path):
            return default
        
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {str(e)}")
        return default


def save_json_file(file_path: str, data: Any) -> bool:
    """
    Save data to JSON file.
    
    Args:
        file_path: Path to JSON file
        data: Data to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory:
            ensure_dir(directory)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False


def format_timestamp(timestamp: Union[datetime, str], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format timestamp as string.
    
    Args:
        timestamp: Timestamp to format
        format_str: Format string
        
    Returns:
        str: Formatted timestamp
    """
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except:
            return timestamp
    
    return timestamp.strftime(format_str)


async def retry_async(func, *args, retries=3, delay=1, **kwargs):
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Function arguments
        retries: Number of retries
        delay: Initial delay in seconds
        **kwargs: Function keyword arguments
        
    Returns:
        Any: Function result
        
    Raises:
        Exception: Last exception if all retries fail
    """
    import asyncio
    
    last_exception = None
    
    for attempt in range(retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt < retries - 1:
                wait_time = delay * (2 ** attempt)
                logger.warning(f"Retry {attempt + 1}/{retries} failed: {str(e)}. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {retries} retries failed: {str(e)}")
    
    raise last_exception
