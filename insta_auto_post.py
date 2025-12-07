#!/usr/bin/env python3
"""
Instagram Photo Uploader
Uploads photos from images/ directory to Instagram with custom captions.
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from instabot import Bot
from PIL import Image
from PIL.ExifTags import TAGS

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CAPTION = ""            # Global default caption when no caption file exists
IMAGES_DIR = Path("images")
UPLOADED_DIR = Path("uploaded")
CONFIG_DIR = Path("config")     # Instabot stores session files here
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_uploader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CAPTION VARIABLE REGISTRY
# ============================================================================

def to_tag(text: str) -> str:
    """Convert text to lowercase tag without spaces."""
    if not text or text == 'Unknown' or text == 'N/A':
        return 'N/A'
    return text.lower().replace(' ', '')


def get_variable_registry() -> Dict[str, Dict[str, Any]]:
    """
    Registry of all available caption variables.
    
    Each variable has:
    - description: What the variable represents
    - category: Group it belongs to (for organization)
    - extractor: Function that extracts the value from image data
    
    To add new variables:
    1. Add entry to this dictionary
    2. Create extractor function if needed
    3. That's it! Variable is now available
    """
    return {
        # File information
        'FILE_NAME': {
            'description': 'Image file name without extension',
            'category': 'File Info',
            'extractor': lambda img_data: img_data['file_name']
        },
        'FILE_NAME_FULL': {
            'description': 'Image file name with extension',
            'category': 'File Info',
            'extractor': lambda img_data: img_data['file_name_full']
        },
        
        # Camera information
        'IMAGE_MAKE': {
            'description': 'Camera manufacturer (e.g., Canon, Nikon, Panasonic)',
            'category': 'Camera',
            'extractor': lambda img_data: img_data.get('Make', 'Unknown')
        },
        'IMAGE_MODEL': {
            'description': 'Camera model (e.g., EOS 5D Mark IV, DMC-TZ8)',
            'category': 'Camera',
            'extractor': lambda img_data: img_data.get('Model', 'Unknown')
        },
        'IMAGE_MAKE_TAG': {
            'description': 'Camera make as hashtag (e.g., nikoncorporation)',
            'category': 'Camera',
            'extractor': lambda img_data: to_tag(img_data.get('Make', ''))
        },
        'IMAGE_MODEL_TAG': {
            'description': 'Camera model as hashtag (e.g., eos5dmarkiv)',
            'category': 'Camera',
            'extractor': lambda img_data: to_tag(img_data.get('Model', ''))
        },
        
        # Exposure settings
        'IMAGE_F_NUMBER': {
            'description': 'Aperture (f-stop) with "f" prefix',
            'category': 'Exposure',
            'extractor': lambda img_data: f"f{img_data.get('FNumber', 0)}" if img_data.get('FNumber') else 'N/A'
        },
        'IMAGE_EXPOSURE_TIME': {
            'description': 'Shutter speed (e.g., 1/200 sec or 2.5 sec)',
            'category': 'Exposure',
            'extractor': lambda img_data: format_exposure_time(img_data.get('ExposureTime'))
        },
        'IMAGE_ISO': {
            'description': 'ISO sensitivity with "ISO" prefix',
            'category': 'Exposure',
            'extractor': lambda img_data: f"ISO {img_data.get('ISOSpeedRatings', 'N/A')}" if img_data.get('ISOSpeedRatings') else 'N/A'
        },
        'IMAGE_PHOTOGRAPHIC_SENSITIVITY': {
            'description': 'ISO value only (number)',
            'category': 'Exposure',
            'extractor': lambda img_data: str(img_data.get('ISOSpeedRatings', 'N/A'))
        },
        
        # Lens information
        'IMAGE_FOCAL_LENGTH': {
            'description': 'Focal length with "mm" suffix (e.g., 42.6 mm)',
            'category': 'Lens',
            'extractor': lambda img_data: f"{img_data.get('FocalLength', 'N/A')} mm" if img_data.get('FocalLength') else 'N/A'
        },
        'IMAGE_FOCAL_LENGTH_VALUE': {
            'description': 'Focal length value only (number)',
            'category': 'Lens',
            'extractor': lambda img_data: str(img_data.get('FocalLength', 'N/A'))
        },
        
        # Date/Time
        'IMAGE_DATE': {
            'description': 'Date photo was taken (YYYY:MM:DD)',
            'category': 'Date/Time',
            'extractor': lambda img_data: img_data.get('DateTime', 'N/A').split()[0] if img_data.get('DateTime') else 'N/A'
        },
        'IMAGE_TIME': {
            'description': 'Time photo was taken (HH:MM:SS)',
            'category': 'Date/Time',
            'extractor': lambda img_data: img_data.get('DateTime', 'N/A').split()[1] if img_data.get('DateTime') and len(img_data.get('DateTime', '').split()) > 1 else 'N/A'
        },
        'IMAGE_DATETIME': {
            'description': 'Full date and time',
            'category': 'Date/Time',
            'extractor': lambda img_data: img_data.get('DateTime', 'N/A')
        },
        
        # Image properties
        'IMAGE_WIDTH': {
            'description': 'Image width in pixels',
            'category': 'Image Properties',
            'extractor': lambda img_data: str(img_data.get('width', 'N/A'))
        },
        'IMAGE_HEIGHT': {
            'description': 'Image height in pixels',
            'category': 'Image Properties',
            'extractor': lambda img_data: str(img_data.get('height', 'N/A'))
        },
        'IMAGE_ORIENTATION': {
            'description': 'Image orientation (Portrait/Landscape/Square)',
            'category': 'Image Properties',
            'extractor': lambda img_data: get_orientation(img_data.get('width'), img_data.get('height'))
        },
    }


def format_exposure_time(exposure_time: Optional[float]) -> str:
    """Format exposure time as human-readable string."""
    if exposure_time is None:
        return 'N/A'
    
    if exposure_time >= 1:
        return f'{exposure_time} sec'
    else:
        return f'1/{round(1/exposure_time)} sec'


def get_orientation(width, height) -> str:
    """Determine image orientation."""
    if width is None or height is None:
        return 'N/A'
    if width > height:
        return 'Landscape'
    elif height > width:
        return 'Portrait'
    else:
        return 'Square'


# ============================================================================
# IMAGE METADATA EXTRACTION
# ============================================================================

def extract_image_metadata(image_path: Path) -> Dict[str, Any]:
    """
    Extract metadata from image file.
    
    Returns a dictionary with:
    - File information (name, path, etc.)
    - EXIF data (camera, exposure, lens, etc.)
    - Image properties (dimensions, etc.)
    
    Args:
        image_path: Path to the image file
    
    Returns:
        Dictionary containing all extracted metadata
    """
    metadata = {
        'file_name': image_path.stem,
        'file_name_full': image_path.name,
        'file_path': str(image_path),
    }
    
    try:
        with Image.open(image_path) as img:
            # Get image dimensions
            metadata['width'] = img.width
            metadata['height'] = img.height
            
            # Extract EXIF data
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    
                    # Handle rational numbers (fractions)
                    if isinstance(value, tuple) and len(value) == 2:
                        try:
                            value = value[0] / value[1] if value[1] != 0 else value[0]
                        except (TypeError, ZeroDivisionError):
                            pass
                    
                    metadata[tag_name] = value
                
                logger.debug(f"Extracted EXIF data: {len(exif_data)} tags")
            else:
                logger.warning(f"No EXIF data found in {image_path}")
    
    except Exception as e:
        logger.error(f"Error extracting metadata from {image_path}: {e}")
    
    return metadata


# ============================================================================
# CAPTION TEMPLATE PROCESSING
# ============================================================================

def process_caption_template(caption: str, image_path: Path) -> str:
    """
    Process caption template by replacing variables with actual values.
    
    Variables format: {VARIABLE_NAME}
    Example: "Shot with {IMAGE_MAKE} {IMAGE_MODEL} at {IMAGE_ISO}"
    
    Args:
        caption: Caption text with template variables
        image_path: Path to the image file (for extracting metadata)
    
    Returns:
        Processed caption with variables replaced by actual values
    """
    # Check if caption contains any variables
    if '{' not in caption:
        return caption
    
    # Extract image metadata
    metadata = extract_image_metadata(image_path)
    
    # Get variable registry
    registry = get_variable_registry()
    
    # Replace each variable
    processed_caption = caption
    for var_name, var_config in registry.items():
        placeholder = f'{{{var_name}}}'
        if placeholder in processed_caption:
            try:
                value = var_config['extractor'](metadata)
                processed_caption = processed_caption.replace(placeholder, str(value))
                logger.debug(f"Replaced {placeholder} with {value}")
            except Exception as e:
                logger.error(f"Error processing variable {var_name}: {e}")
                processed_caption = processed_caption.replace(placeholder, 'N/A')
    
    return processed_caption


def list_available_variables():
    """Print all available caption variables grouped by category."""
    registry = get_variable_registry()
    
    # Group by category
    categories = {}
    for var_name, var_config in registry.items():
        category = var_config['category']
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'name': var_name,
            'description': var_config['description']
        })
    
    # Print organized list
    print("\n" + "="*70)
    print("AVAILABLE CAPTION VARIABLES")
    print("="*70)
    print("\nUsage: {VARIABLE_NAME} in your caption files")
    print("Example: '{FILE_NAME}.\\n{IMAGE_MAKE} {IMAGE_MODEL} | {IMAGE_F_NUMBER}'")
    print("\nExample caption file:")
    print("  {FILE_NAME}.")
    print("  {IMAGE_MAKE} {IMAGE_MODEL} | {IMAGE_F_NUMBER} | {IMAGE_EXPOSURE_TIME} | {IMAGE_FOCAL_LENGTH} | ISO {IMAGE_PHOTOGRAPHIC_SENSITIVITY}")
    print("  #landscape #nature\n")
    
    for category in sorted(categories.keys()):
        print(f"\n{category}")
        print("-" * len(category))
        for var in categories[category]:
            print(f"  {{{var['name']:<40}}} - {var['description']}")
    
    print("\n" + "="*70)
    print(f"Total: {len(registry)} variables available")
    print("="*70 + "\n")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_directories():
    """Create necessary directories if they don't exist."""
    IMAGES_DIR.mkdir(exist_ok=True)
    UPLOADED_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    logger.info(f"Directories ensured: {IMAGES_DIR}, {UPLOADED_DIR}, {CONFIG_DIR}")


def find_image_to_upload() -> Optional[Path]:
    """
    Find an image to upload from the images directory.
    
    Current implementation: Returns the first image when sorted alphabetically.
    This function can be easily modified to implement different selection algorithms.
    
    Returns:
        Path to the image file, or None if no images found.
    """
    # Get all image files
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(IMAGES_DIR.glob(f"*{ext}"))
    
    if not image_files:
        logger.warning(f"No images found in {IMAGES_DIR}")
        return None
    
    # Sort alphabetically and return the first one
    # You can modify this logic to implement different selection strategies:
    # - Random selection: random.choice(image_files)
    # - Oldest first: min(image_files, key=lambda x: x.stat().st_mtime)
    # - Newest first: max(image_files, key=lambda x: x.stat().st_mtime)
    image_files.sort()
    selected_image = image_files[0]
    
    logger.info(f"Selected image: {selected_image}")
    return selected_image


def get_caption_for_image(image_path: Path, custom_caption: Optional[str] = None) -> str:
    """
    Get caption for an image.
    
    Priority:
    1. Custom caption provided as argument
    2. Caption file (.caption.txt)
    3. Default caption
    
    Args:
        image_path: Path to the image file
        custom_caption: Optional custom caption provided via CLI
    
    Returns:
        Caption text to use for the upload (with variables processed)
    """
    raw_caption = None
    
    if custom_caption is not None:
        logger.info("Using custom caption provided via argument")
        raw_caption = custom_caption
    else:
        # Check for caption file
        caption_file = Path(f"{image_path}.caption.txt")
        if caption_file.exists():
            try:
                with open(caption_file, 'r', encoding='utf-8') as f:
                    raw_caption = f.read().strip()
                logger.info(f"Using caption from file: {caption_file}")
            except Exception as e:
                logger.error(f"Error reading caption file {caption_file}: {e}")
        
        if raw_caption is None:
            logger.info("Using default caption")
            raw_caption = DEFAULT_CAPTION
    
    # Process template variables in caption
    processed_caption = process_caption_template(raw_caption, image_path)
    
    if raw_caption != processed_caption:
        logger.info("Caption template variables processed")
        logger.debug(f"Original: {raw_caption}")
        logger.debug(f"Processed: {processed_caption}")

    return processed_caption


def login_instagram(username: str, password: str) -> Bot:
    """
    Login to Instagram with session management.
    
    This function:
    - Creates Bot instance with optimized settings
    - Loads existing session if available
    - Creates new session if needed
    - Implements anti-detection measures
    
    Args:
        username: Instagram username
        password: Instagram password
    
    Returns:
        Authenticated Instagram bot
    """
    # Create bot instance
    # Instabot automatically handles session management in config/ directory
    bot = Bot()
    
    logger.info("Logging in to Instagram...")
    try:
        # Login - instabot will automatically use cached session if available
        bot.login(username=username, password=password)
        logger.info("Successfully logged in to Instagram")
        return bot
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise


def upload_photo_to_instagram(bot: Bot, image_path: Path, caption: str) -> bool:
    """
    Upload a photo to Instagram.
    
    Args:
        bot: Authenticated Instagram bot
        image_path: Path to the image file
        caption: Caption text for the photo
    
    Returns:
        True if upload successful, False otherwise
    """
    try:
        logger.info(f"Uploading {image_path} to Instagram...")
        logger.info(f"Caption: {caption[:50]}..." if len(caption) > 50 else f"Caption: {caption}")
        
        # Upload photo
        success = bot.upload_photo(
            photo=str(image_path),
            caption=caption
        )
        
        if success:
            logger.info("Successfully uploaded to Instagram!")
            return True
        else:
            logger.error("Upload failed - bot.upload_photo returned False")
            return False
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return False


def move_to_uploaded(image_path: Path):
    """
    Move uploaded image and its caption file (if exists) to uploaded directory.
    
    Args:
        image_path: Path to the uploaded image
    """
    try:
        # Move image
        dest_image = UPLOADED_DIR / image_path.name
        shutil.move(str(image_path), str(dest_image))
        logger.info(f"Moved {image_path} to {dest_image}")
        
        # Move caption file if it exists
        caption_file = Path(f"{image_path}.caption.txt")
        if caption_file.exists():
            dest_caption = UPLOADED_DIR / caption_file.name
            shutil.move(str(caption_file), str(dest_caption))
            logger.info(f"Moved {caption_file} to {dest_caption}")
    except Exception as e:
        logger.error(f"Error moving files: {e}")
        raise


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to orchestrate the upload process."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Upload photos to Instagram with custom captions'
    )
    parser.add_argument(
        '--image',
        type=str,
        help='Path to specific image to upload (optional)'
    )
    parser.add_argument(
        '--caption',
        type=str,
        help='Custom caption text (optional)'
    )
    parser.add_argument(
        '--list-vars',
        action='store_true',
        help='List all available caption variables and exit'
    )
    args = parser.parse_args()
    
    # Handle --list-vars flag
    if args.list_vars:
        list_available_variables()
        sys.exit(0)
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('INSTAGRAM_USERNAME')
    password = os.getenv('INSTAGRAM_PASSWORD')
    
    if not username or not password:
        logger.error("Instagram credentials not found in .env file")
        logger.error("Please create a .env file with INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD")
        sys.exit(1)
    
    # Ensure directories exist
    ensure_directories()
    
    # Determine which image to upload
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            logger.error(f"Specified image not found: {image_path}")
            sys.exit(1)
    else:
        image_path = find_image_to_upload()
        if not image_path:
            logger.error("No images found to upload")
            sys.exit(1)
    
    # Get caption for the image
    caption = get_caption_for_image(image_path, args.caption)
    
    # Login to Instagram
    try:
        bot = login_instagram(username, password)
    except Exception as e:
        logger.error(f"Failed to login: {e}")
        sys.exit(1)
    
    # Upload the photo
    upload_success = upload_photo_to_instagram(bot, image_path, caption)
    
    if upload_success:
        # Move uploaded files to uploaded directory
        move_to_uploaded(image_path)
        logger.info("✓ Upload process completed successfully!")
    else:
        logger.error("✗ Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()



