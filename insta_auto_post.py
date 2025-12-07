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
from typing import Optional, Tuple
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CAPTION = ""  # Global default caption when no caption file exists
IMAGES_DIR = Path("images")
UPLOADED_DIR = Path("uploaded")
SESSION_FILE = "instagram_session.json"
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
# HELPER FUNCTIONS
# ============================================================================

def ensure_directories():
    """Create necessary directories if they don't exist."""
    IMAGES_DIR.mkdir(exist_ok=True)
    UPLOADED_DIR.mkdir(exist_ok=True)
    logger.info(f"Directories ensured: {IMAGES_DIR}, {UPLOADED_DIR}")


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
        Caption text to use for the upload
    """
    if custom_caption is not None:
        logger.info("Using custom caption provided via argument")
        return custom_caption
    
    # Check for caption file
    caption_file = Path(f"{image_path}.caption.txt")
    if caption_file.exists():
        try:
            with open(caption_file, 'r', encoding='utf-8') as f:
                caption = f.read().strip()
            logger.info(f"Using caption from file: {caption_file}")
            return caption
        except Exception as e:
            logger.error(f"Error reading caption file {caption_file}: {e}")
    
    logger.info("Using default caption")
    return DEFAULT_CAPTION


def login_instagram(username: str, password: str) -> Client:
    """
    Login to Instagram with session management.
    
    This function:
    - Loads existing session if available
    - Creates new session if needed
    - Implements anti-detection measures
    - Handles 2FA and verification challenges
    - Saves session for future use
    
    Args:
        username: Instagram username
        password: Instagram password
    
    Returns:
        Authenticated Instagram client
    """
    client = Client()
    
    # Configure client to avoid bot detection
    client.delay_range = [1, 3]  # Random delay between 1-3 seconds
    
    session_path = Path(SESSION_FILE)
    
    # Try to load existing session
    if session_path.exists():
        logger.info("Loading existing session...")
        try:
            client.load_settings(session_path)
            client.login(username, password)
            
            # Verify session is still valid
            client.get_timeline_feed()
            logger.info("Successfully loaded existing session")
            return client
        except Exception as e:
            logger.warning(f"Existing session invalid or expired: {e}")
            logger.info("Creating new session...")
    
    # Create new session
    try:
        logger.info("Logging in to Instagram...")
        
        # Handle potential 2FA
        try:
            client.login(username, password)
        except Exception as login_error:
            error_msg = str(login_error).lower()
            
            # Check if it's a 2FA challenge
            if "two_factor_required" in error_msg or "challenge_required" in error_msg:
                logger.info("Two-factor authentication or challenge required")
                logger.info("Please check your Instagram app or email for verification code")
                
                verification_code = input("Enter verification code: ").strip()
                client.login(username, password, verification_code=verification_code)
            elif "checkpoint_required" in error_msg or "challenge" in error_msg:
                logger.error("Instagram requires manual verification")
                logger.error("Please:")
                logger.error("1. Log in to Instagram via app or website")
                logger.error("2. Complete any security checks")
                logger.error("3. Wait 1-2 hours before trying again")
                raise
            else:
                raise login_error
        
        # Save session for future use
        client.dump_settings(session_path)
        logger.info(f"Session saved to {session_path}")
        
        return client
    except Exception as e:
        logger.error(f"Login failed: {e}")
        logger.error("\nTroubleshooting steps:")
        logger.error("1. Run: python setup_session.py")
        logger.error("2. Verify your login via Instagram app/website")
        logger.error("3. Check if you need to complete a security check")
        logger.error("4. Wait 1-2 hours if you've tried multiple times")
        raise


def upload_photo_to_instagram(client: Client, image_path: Path, caption: str) -> bool:
    """
    Upload a photo to Instagram.
    
    Args:
        client: Authenticated Instagram client
        image_path: Path to the image file
        caption: Caption text for the photo
    
    Returns:
        True if upload successful, False otherwise
    """
    try:
        logger.info(f"Uploading {image_path} to Instagram...")
        logger.info(f"Caption: {caption[:50]}..." if len(caption) > 50 else f"Caption: {caption}")
        
        media = client.photo_upload(
            path=str(image_path),
            caption=caption
        )
        
        logger.info(f"Successfully uploaded! Media ID: {media.pk}")
        return True
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
    args = parser.parse_args()
    
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
        client = login_instagram(username, password)
    except Exception as e:
        logger.error(f"Failed to login: {e}")
        sys.exit(1)
    
    # Upload the photo
    upload_success = upload_photo_to_instagram(client, image_path, caption)
    
    if upload_success:
        # Move uploaded files to uploaded directory
        move_to_uploaded(image_path)
        logger.info("✓ Upload process completed successfully!")
    else:
        logger.error("✗ Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()



