"""
Window Sticker Processing Module for vAuto Feature Verification System.

Handles:
- Downloading window sticker PDFs
- Extracting text from PDFs
- Identifying features from window sticker text
"""

import logging
import os
import re
import tempfile
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
import aiohttp

import pdfplumber
from PIL import Image
import pytesseract

from core.interfaces import BrowserInterface, WindowStickerInterface
from utils.common import normalize_text, ensure_dir

logger = logging.getLogger(__name__)


class WindowStickerProcessor(WindowStickerInterface):
    """
    Module for processing window stickers and extracting features.
    """
    
    def __init__(self, browser: BrowserInterface, config: Dict[str, Any]):
        """
        Initialize the window sticker processor.
        
        Args:
            browser: Browser interface implementation
            config: System configuration
        """
        self.browser = browser
        self.config = config
        self.temp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "vauto_window_stickers"))
        
        logger.info("Window Sticker Processor initialized")
    
    async def extract_features(self, window_sticker_path_or_url: str) -> List[str]:
        """
        Extract features from a window sticker.
        
        Args:
            window_sticker_path_or_url: Path or URL to window sticker
            
        Returns:
            list: List of extracted features
        """
        logger.info(f"Extracting features from window sticker: {window_sticker_path_or_url}")
        
        try:
            # Check if it's a URL or local path
            if window_sticker_path_or_url.startswith(("http://", "https://")):
                # Download the window sticker
                local_path = await self._download_window_sticker(window_sticker_path_or_url)
                if not local_path:
                    logger.error("Failed to download window sticker")
                    return []
            else:
                # It's already a local path
                local_path = window_sticker_path_or_url
            
            # Extract text from the window sticker
            text = await self._extract_text_from_window_sticker(local_path)
            if not text:
                logger.error("Failed to extract text from window sticker")
                return []
            
            # Extract features from the text
            features = self._extract_features_from_text(text)
            
            logger.info(f"Extracted {len(features)} features from window sticker")
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features from window sticker: {str(e)}")
            return []
    
    async def _download_window_sticker(self, url: str) -> Optional[str]:
        """
        Download a window sticker from a URL.
        
        Args:
            url: URL to window sticker
            
        Returns:
            str: Local path to downloaded window sticker or None if download failed
        """
        logger.info(f"Downloading window sticker from URL: {url}")
        
        try:
            # Parse URL to get filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            # If no filename or extension, use a default
            if not filename or "." not in filename:
                filename = f"window_sticker_{hash(url)}.pdf"
            
            # Create local path
            local_path = os.path.join(self.temp_dir, filename)
            
            # Check if file already exists
            if os.path.exists(local_path):
                logger.info(f"Window sticker already downloaded: {local_path}")
                return local_path
            
            # Download the file
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download window sticker: HTTP {response.status}")
                        return None
                    
                    # Check content type
                    content_type = response.headers.get("Content-Type", "")
                    if "pdf" not in content_type and "application/octet-stream" not in content_type:
                        logger.warning(f"Unexpected content type: {content_type}")
                        
                        # If it's HTML, it might be a viewer page, try to extract the PDF URL
                        if "html" in content_type:
                            logger.info("Detected HTML content, attempting to extract PDF URL")
                            return await self._extract_pdf_url_from_html(url)
                    
                    # Save the file
                    with open(local_path, "wb") as f:
                        f.write(await response.read())
            
            logger.info(f"Window sticker downloaded to: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Error downloading window sticker: {str(e)}")
            return None
    
    async def _extract_pdf_url_from_html(self, url: str) -> Optional[str]:
        """
        Extract PDF URL from HTML page.
        
        Args:
            url: URL to HTML page
            
        Returns:
            str: Local path to downloaded PDF or None if extraction failed
        """
        logger.info(f"Extracting PDF URL from HTML page: {url}")
        
        try:
            # Navigate to the URL
            await self.browser.navigate_to(url)
            
            # Wait for the page to load
            await asyncio.sleep(3)
            
            # Look for PDF embed or iframe
            pdf_selectors = [
                "//embed[@type='application/pdf']",
                "//iframe[contains(@src, '.pdf')]",
                "//object[@type='application/pdf']",
                "//a[contains(@href, '.pdf')]"
            ]
            
            for selector in pdf_selectors:
                elements = await self.browser.find_elements(selector)
                for element in elements:
                    pdf_url = await self.browser.get_attribute(element, "src") or await self.browser.get_attribute(element, "href")
                    if pdf_url:
                        logger.info(f"Found PDF URL: {pdf_url}")
                        return await self._download_window_sticker(pdf_url)
            
            # If no PDF found, take a screenshot as fallback
            logger.warning("No PDF found in HTML page, taking screenshot as fallback")
            screenshot_path = os.path.join(self.temp_dir, f"window_sticker_screenshot_{hash(url)}.png")
            await self.browser.take_screenshot(screenshot_path)
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error extracting PDF URL from HTML: {str(e)}")
            return None
    
    async def _extract_text_from_window_sticker(self, file_path: str) -> str:
        """
        Extract text from a window sticker file.
        
        Args:
            file_path: Path to window sticker file
            
        Returns:
            str: Extracted text
        """
        logger.info(f"Extracting text from window sticker file: {file_path}")
        
        try:
            # Check file extension
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            if ext == ".pdf":
                # Extract text from PDF
                return await self._extract_text_from_pdf(file_path)
            elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                # Extract text from image
                return await self._extract_text_from_image(file_path)
            else:
                logger.error(f"Unsupported file format: {ext}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting text from window sticker: {str(e)}")
            return ""
    
    async def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            str: Extracted text
        """
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        try:
            # Use pdfplumber to extract text
            text = await asyncio.to_thread(self._extract_text_from_pdf_sync, pdf_path)
            
            # If no text extracted, try OCR as fallback
            if not text or len(text.strip()) < 100:  # Arbitrary threshold
                logger.warning("Minimal text extracted from PDF, trying OCR as fallback")
                return await self._extract_text_from_pdf_with_ocr(pdf_path)
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""
    
    def _extract_text_from_pdf_sync(self, pdf_path: str) -> str:
        """
        Synchronous function to extract text from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            str: Extracted text
        """
        text = ""
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
                text += "\n\n"
        
        return text
    
    async def _extract_text_from_pdf_with_ocr(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file using OCR.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            str: Extracted text
        """
        logger.info(f"Extracting text from PDF using OCR: {pdf_path}")
        
        try:
            # Convert PDF to images
            images = await asyncio.to_thread(self._convert_pdf_to_images, pdf_path)
            
            # Extract text from each image
            all_text = ""
            for image_path in images:
                text = await self._extract_text_from_image(image_path)
                all_text += text + "\n\n"
                
                # Clean up temporary image
                try:
                    os.remove(image_path)
                except:
                    pass
            
            return all_text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF with OCR: {str(e)}")
            return ""
    
    def _convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """
        Convert PDF to images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            list: List of paths to image files
        """
        from pdf2image import convert_from_path
        
        # Generate output paths
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = os.path.join(self.temp_dir, f"{base_name}_images")
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=300)
        
        # Save images
        image_paths = []
        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"{base_name}_page_{i+1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)
        
        return image_paths
    
    async def _extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file using OCR.
        
        Args:
            image_path: Path to image file
            
        Returns:
            str: Extracted text
        """
        logger.info(f"Extracting text from image: {image_path}")
        
        try:
            # Use pytesseract to extract text
            text = await asyncio.to_thread(self._extract_text_from_image_sync, image_path)
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""
    
    def _extract_text_from_image_sync(self, image_path: str) -> str:
        """
        Synchronous function to extract text from image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            str: Extracted text
        """
        # Open the image
        image = Image.open(image_path)
        
        # Extract text
        text = pytesseract.image_to_string(image)
        
        return text
    
    def _extract_features_from_text(self, text: str) -> List[str]:
        """
        Extract features from window sticker text.
        
        Args:
            text: Window sticker text
            
        Returns:
            list: List of extracted features
        """
        logger.info("Extracting features from window sticker text")
        
        features = []
        
        try:
            # Normalize text
            normalized_text = normalize_text(text)
            
            # Split into lines
            lines = normalized_text.split("\n")
            
            # Look for feature sections
            feature_section = False
            feature_headers = [
                "standard equipment",
                "factory installed options",
                "optional equipment",
                "included equipment",
                "features",
                "equipment",
                "packages"
            ]
            
            non_feature_headers = [
                "warranty",
                "safety ratings",
                "fuel economy",
                "price",
                "msrp",
                "destination",
                "total"
            ]
            
            current_features = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this is a feature section header
                if any(header in line.lower() for header in feature_headers):
                    feature_section = True
                    continue
                
                # Check if this is the end of a feature section
                if feature_section and any(header in line.lower() for header in non_feature_headers):
                    feature_section = False
                
                # If we're in a feature section, extract features
                if feature_section:
                    # Skip price information
                    if re.search(r'\$\d+', line):
                        continue
                    
                    # Skip lines that are too short
                    if len(line) < 3:
                        continue
                    
                    # Add to features
                    current_features.append(line)
            
            # If no feature sections found, try to extract features based on patterns
            if not current_features:
                logger.warning("No feature sections found, trying pattern-based extraction")
                current_features = self._extract_features_by_pattern(lines)
            
            # Clean up features
            for feature in current_features:
                # Skip very short features
                if len(feature) < 3:
                    continue
                
                # Skip features that are just numbers or codes
                if re.match(r'^[\d\s\-\.]+$', feature):
                    continue
                
                # Skip features that are just single letters
                if re.match(r'^[a-zA-Z]$', feature):
                    continue
                
                # Clean up the feature text
                cleaned_feature = self._clean_feature_text(feature)
                if cleaned_feature:
                    features.append(cleaned_feature)
            
            # Remove duplicates while preserving order
            unique_features = []
            for feature in features:
                if feature not in unique_features:
                    unique_features.append(feature)
            
            logger.info(f"Extracted {len(unique_features)} features from text")
            return unique_features
            
        except Exception as e:
            logger.error(f"Error extracting features from text: {str(e)}")
            return []
    
    def _extract_features_by_pattern(self, lines: List[str]) -> List[str]:
        """
        Extract features based on patterns.
        
        Args:
            lines: Lines of text
            
        Returns:
            list: List of extracted features
        """
        features = []
        
        # Look for bullet points or dashes
        bullet_pattern = re.compile(r'^[\s\-•\*]+(.+)$')
        
        # Look for feature-like patterns (e.g., "Feature Name: Feature Value")
        feature_pattern = re.compile(r'^(.+?)[\:\-](.+)$')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for bullet points
            bullet_match = bullet_pattern.match(line)
            if bullet_match:
                feature = bullet_match.group(1).strip()
                if feature:
                    features.append(feature)
                continue
            
            # Check for feature patterns
            feature_match = feature_pattern.match(line)
            if feature_match:
                feature_name = feature_match.group(1).strip()
                feature_value = feature_match.group(2).strip()
                
                # Skip if feature name is too short
                if len(feature_name) < 3:
                    continue
                
                # Skip if feature value is just a number
                if re.match(r'^[\d\s\-\.]+$', feature_value):
                    features.append(feature_name)
                else:
                    features.append(f"{feature_name}: {feature_value}")
                
                continue
            
            # If line contains common feature keywords, add it
            feature_keywords = [
                "system", "package", "wheels", "seats", "audio", "climate", "control",
                "assist", "camera", "sensor", "navigation", "bluetooth", "usb", "heated",
                "cooled", "leather", "sunroof", "roof", "door", "window", "mirror", "light",
                "led", "automatic", "manual", "transmission", "engine", "cylinder", "turbo",
                "awd", "4wd", "fwd", "rwd", "drive", "brake", "safety", "airbag", "alarm",
                "lock", "key", "remote", "start", "stop", "cruise", "lane", "blind", "spot",
                "parking", "backup", "rear", "front", "side", "collision", "warning", "alert"
            ]
            
            if any(keyword in line.lower() for keyword in feature_keywords):
                features.append(line)
        
        return features
    
    def _clean_feature_text(self, feature: str) -> str:
        """
        Clean up feature text.
        
        Args:
            feature: Feature text
            
        Returns:
            str: Cleaned feature text
        """
        # Remove leading/trailing whitespace
        cleaned = feature.strip()
        
        # Remove leading bullet points, dashes, etc.
        cleaned = re.sub(r'^[\s\-•\*]+', '', cleaned)
        
        # Remove trailing punctuation
        cleaned = re.sub(r'[\.\,\;\:]+$', '', cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
