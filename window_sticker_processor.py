"""
Window Sticker Processor Module for vAuto Feature Verification System.

Handles:
- PDF and image processing of window stickers
- OCR capabilities for image-based window stickers
- Pattern matching for different manufacturer formats
- Feature extraction from window sticker content
"""

import logging
import re
import os
import tempfile
import asyncio
from urllib.parse import urlparse
import pdfplumber
import pytesseract
from PIL import Image
import io
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class WindowStickerProcessor:
    """
    Process window sticker PDFs to extract features.
    """
    
    def __init__(self, config):
        """
        Initialize the window sticker processor.
        
        Args:
            config (dict): System configuration
        """
        self.config = config
        
        # Map of manufacturers to their specific extraction patterns
        self.manufacturer_patterns = {
            "ford": {
                "standard_equipment": r'STANDARD EQUIPMENT\s*(?:INCLUDED AT NO EXTRA CHARGE|:)(.*?)(?:OPTIONAL|PRICE|TOTAL|$)',
                "optional_equipment": r'OPTIONAL EQUIPMENT(?:/OTHER|/MISC)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:SUBTOTAL|TOTAL|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "gm": {  # General Motors (Chevrolet, Buick, GMC, Cadillac)
                "standard_equipment": r'STANDARD (?:VEHICLE )?(?:EQUIPMENT|FEATURES)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:OPTIONS|ADDED|TOTAL|$)',
                "optional_equipment": r'(?:OPTIONAL|ADDED) (?:EQUIPMENT|FEATURES)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|SUBTOTAL|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "fca": {  # Fiat Chrysler Automobiles (Dodge, Jeep, Chrysler, RAM)
                "standard_equipment": r'STANDARD EQUIPMENT(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:OPTIONAL|ADDED|TOTAL|$)',
                "optional_equipment": r'OPTIONAL EQUIPMENT(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|SUBTOTAL|DESTINATION|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "toyota": {
                "standard_equipment": r'STANDARD(?:[^\n]*EQUIPMENT|[^\n]*FEATURES)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:ACCESSORIES|OPTIONAL|ADDED|TOTAL|$)',
                "optional_equipment": r'(?:OPTIONAL EQUIPMENT|ACCESSORIES)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|SUBTOTAL|DELIVERY|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "honda": {
                "standard_equipment": r'STANDARD (?:FEATURES|EQUIPMENT)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:ACCESSORIES|INSTALLED|TOTAL|$)',
                "optional_equipment": r'(?:INSTALLED|ACCESSORIES|ADDED)(?:[^\n]*EQUIPMENT)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|SUBTOTAL|DESTINATION|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "nissan": {
                "standard_equipment": r'STANDARD(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:OPTIONAL|PACKAGES|TOTAL|$)',
                "optional_equipment": r'(?:OPTIONAL|PACKAGES)(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|DESTINATION|$)',
                "safety_security": r'SAFETY(?:/SECURITY)?(?:\s*:[^\n]*|\s*\n[^\n]*|\s*)([^=]*?)(?:TOTAL|$)'
            },
            "default": {
                "standard_equipment": r'STANDARD|INCLUDED|EQUIPMENT|FEATURES',
                "optional_equipment": r'OPTIONAL|ADDED|ACCESSORIES|PACKAGES',
                "safety_security": r'SAFETY|SECURITY'
            }
        }
    
    async def extract_features(self, window_sticker_path_or_url):
        """
        Extract features from a window sticker.
        
        Args:
            window_sticker_path_or_url (str): Path or URL to window sticker
            
        Returns:
            list: Extracted features
        """
        logger.info(f"Extracting features from window sticker: {window_sticker_path_or_url}")
        
        try:
            # Determine if this is a URL or a file path
            if window_sticker_path_or_url.startswith(('http://', 'https://')):
                # Download the file to a temporary location first
                pdf_path = await self._download_file(window_sticker_path_or_url)
                delete_after = True
            else:
                pdf_path = window_sticker_path_or_url
                delete_after = False
            
            # Determine if this is a text-based or image-based PDF
            is_text_based = await self._is_text_based_pdf(pdf_path)
            
            if is_text_based:
                logger.info("Processing text-based PDF")
                features = await self._extract_from_text_pdf(pdf_path)
            else:
                logger.info("Processing image-based PDF")
                features = await self._extract_from_image_pdf(pdf_path)
            
            # Clean up temporary file if needed
            if delete_after and os.path.exists(pdf_path):
                os.remove(pdf_path)
                
            logger.info(f"Extracted {len(features)} features from window sticker")
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features from window sticker: {str(e)}")
            raise
    
    async def _download_file(self, url):
        """
        Download a file from a URL.
        
        Args:
            url (str): URL to download
            
        Returns:
            str: Path to downloaded file
        """
        logger.info(f"Downloading file from URL: {url}")
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_extension_from_url(url)) as tmp:
            temp_path = tmp.name
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download file: HTTP {response.status}")
                    
                    content = await response.read()
                    
                    # Write content to temporary file
                    with open(temp_path, 'wb') as f:
                        f.write(content)
            
            logger.info(f"File downloaded to: {temp_path}")
            return temp_path
            
        except Exception as e:
            # Clean up the temporary file in case of error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Error downloading file: {str(e)}")
            raise
    
    def _get_extension_from_url(self, url):
        """
        Get file extension from URL.
        
        Args:
            url (str): URL
            
        Returns:
            str: File extension (e.g., '.pdf', '.jpg')
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        extension = os.path.splitext(path)[1]
        
        if not extension:
            # Default to .pdf if no extension is found
            return '.pdf'
        
        return extension
    
    async def _is_text_based_pdf(self, pdf_path):
        """
        Determine if a PDF is text-based or image-based.
        
        Args:
            pdf_path (str): Path to PDF file
            
        Returns:
            bool: True if text-based, False if image-based
        """
        try:
            def check_pdf():
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text and len(text.strip()) > 100:  # Arbitrary threshold
                            return True
                return False
            
            return await asyncio.to_thread(check_pdf)
        except Exception as e:
            logger.error(f"Error determining if PDF is text-based: {str(e)}")
            # Default to image-based if we can't determine
            return False
    
    async def _extract_from_text_pdf(self, pdf_path):
        """
        Extract features from a text-based PDF.
        
        Args:
            pdf_path (str): Path to PDF file
            
        Returns:
            list: Extracted features
        """
        logger.info("Extracting features from text-based PDF")
        
        try:
            def process_pdf():
                features = []
                manufacturer = "default"  # Default pattern set
                
                with pdfplumber.open(pdf_path) as pdf:
                    # Extract all text from the PDF
                    all_text = ""
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            all_text += text + "\n"
                    
                    # Try to identify the manufacturer based on text patterns
                    for mfr in self.manufacturer_patterns:
                        if mfr == "default":
                            continue
                        # Look for manufacturer name or common patterns
                        if mfr.upper() in all_text.upper() or self._matches_manufacturer_pattern(all_text, mfr):
                            manufacturer = mfr
                            logger.info(f"Identified manufacturer: {manufacturer}")
                            break
                    
                    # Get the patterns for the identified manufacturer
                    patterns = self.manufacturer_patterns[manufacturer]
                    
                    # Extract standard equipment
                    std_equipment = self._extract_section(all_text, patterns["standard_equipment"])
                    if std_equipment:
                        std_features = self._parse_feature_list(std_equipment)
                        features.extend(std_features)
                        logger.debug(f"Extracted {len(std_features)} standard equipment features")
                    
                    # Extract optional equipment
                    opt_equipment = self._extract_section(all_text, patterns["optional_equipment"])
                    if opt_equipment:
                        opt_features = self._parse_feature_list(opt_equipment)
                        features.extend(opt_features)
                        logger.debug(f"Extracted {len(opt_features)} optional equipment features")
                    
                    # Extract safety and security features
                    safety_security = self._extract_section(all_text, patterns["safety_security"])
                    if safety_security:
                        safety_features = self._parse_feature_list(safety_security)
                        features.extend(safety_features)
                        logger.debug(f"Extracted {len(safety_features)} safety and security features")
                    
                    # If we didn't extract any features using the patterns, fall back to a more generic approach
                    if not features:
                        logger.warning("No features extracted using pattern matching, falling back to generic extraction")
                        features = self._extract_generic_features(all_text)
                
                # Remove duplicates while preserving order
                unique_features = []
                for feature in features:
                    if feature not in unique_features:
                        unique_features.append(feature)
                
                return unique_features
            
            return await asyncio.to_thread(process_pdf)
        except Exception as e:
            logger.error(f"Error extracting features from text-based PDF: {str(e)}")
            return []
    
    def _matches_manufacturer_pattern(self, text, manufacturer):
        """
        Check if text matches common patterns for a specific manufacturer.
        
        Args:
            text (str): Text to check
            manufacturer (str): Manufacturer name
            
        Returns:
            bool: True if matches, False otherwise
        """
        # Map of manufacturer-specific patterns to identify window stickers
        manufacturer_identifiers = {
            "ford": [r'FORD', r'BUILD FOR AMERICA', r'LINCOLN'],
            "gm": [r'GENERAL MOTORS', r'CHEVROLET', r'BUICK', r'GMC', r'CADILLAC'],
            "fca": [r'CHRYSLER', r'DODGE', r'JEEP', r'RAM', r'FIAT', r'MOPAR'],
            "toyota": [r'TOYOTA', r'LEXUS', r'SCION'],
            "honda": [r'HONDA', r'ACURA'],
            "nissan": [r'NISSAN', r'INFINITI']
        }
        
        if manufacturer in manufacturer_identifiers:
            for pattern in manufacturer_identifiers[manufacturer]:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
        
        return False
    
    def _extract_section(self, text, pattern):
        """
        Extract a section of text using a regex pattern.
        
        Args:
            text (str): Text to extract from
            pattern (str): Regex pattern
            
        Returns:
            str: Extracted section or empty string if not found
        """
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match and len(match.groups()) > 0:
            return match.group(1).strip()
        return ""
    
    def _parse_feature_list(self, section_text):
        """
        Parse a feature list from section text.
        
        Args:
            section_text (str): Section text
            
        Returns:
            list: Extracted features
        """
        features = []
        
        # Try to identify if items are separated by bullets, asterisks, or numbers
        if re.search(r'•|\*|\d+\.', section_text):
            # Split by common bullet patterns
            items = re.split(r'\s*(?:•|\*|\d+\.)\s*', section_text)
        else:
            # Split by newlines
            items = section_text.split('\n')
        
        for item in items:
            item = item.strip()
            
            # Skip empty items or items that appear to be prices or codes
            if not item or re.match(r'^[\d\s\.,\$]+$', item) or len(item) < 3:
                continue
            
            # Clean up the feature text
            feature = self._clean_feature_text(item)
            if feature:
                features.append(feature)
        
        return features
    
    def _extract_generic_features(self, text):
        """
        Extract features using a generic approach when pattern matching fails.
        
        Args:
            text (str): Text to extract from
            
        Returns:
            list: Extracted features
        """
        features = []
        
        # Look for common feature patterns
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # Skip empty lines, prices, and short strings
            if not line or re.match(r'^[\d\s\.,\$]+$', line) or len(line) < 5:
                continue
            
            # Skip header lines and totals
            if re.search(r'(?:TOTAL|SUBTOTAL|PRICE|MSRP|DESTINATION|DELIVERY|MANUFACTURER)', line, re.IGNORECASE):
                continue
            
            # Clean up the feature text
            feature = self._clean_feature_text(line)
            if feature:
                features.append(feature)
        
        return features
    
    def _clean_feature_text(self, feature):
      
(Content truncated due to size limit. Use line ranges to read in chunks)