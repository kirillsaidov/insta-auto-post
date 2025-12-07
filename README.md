# Instagram Photo Uploader

Automated Python script for uploading photos to Instagram with custom captions.

#### Features

- Automatic photo upload to Instagram
- Custom captions per image or default caption
- Session management to avoid repeated logins

## Directory structure

```
project/
├── instagram_uploader.py      # Main script
├── requirements.txt           # Python dependencies
├── .env                       # Your credentials (create this)
├── .env.example               # Template for credentials
├── images/                    # Place images here (create this)
│   ├── photo1.jpg
│   ├── photo1.jpg.caption.txt # Optional caption for photo1
│   ├── photo2.png
│   └── photo2.png.caption.txt
├── uploaded/                  # Uploaded files moved here (auto-created)
├── instagram_session.json     # Instabot session files (auto-created)
└── instagram_uploader.log     # Log file (auto-created)
```

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and add your Instagram credentials:

```bash
cp .env.example .env

# edit env file:
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
```

### 3. Prepare images

Place your images in the `images/` directory:
- Supported formats: `.jpg`, `.jpeg`, `.png`
- Optional: Create `.caption.txt` files alongside your image for custom captions

Example:
```
images/sunset.jpg
images/sunset.jpg.caption.txt
```

## Usage

### Basic usage

```bash
python instagram_uploader.py
```

This will:
1. Find the first image (alphabetically) from `images/`
2. Look for a matching `.caption.txt` file
3. Upload to Instagram
4. Move files to `uploaded/`

### Upload specific image

```bash
python instagram_uploader.py --image images/myphoto.jpg
```

### Upload with custom caption

```bash
python instagram_uploader.py --image images/myphoto.jpg --caption "Beautiful sunset! 🌅"
```

### Upload with caption file

Create a caption file with the same name as your image plus `.caption.txt`:

```bash
echo "Amazing view from my trip! #travel #nature" > images/vacation.jpg.caption.txt
python instagram_uploader.py --image images/vacation.jpg
```

## Caption Priority

The script uses captions in this order:
1. **Command-line argument** (`--caption`)
2. **Caption file** (`image_name.caption.txt`)
3. **Default caption** (empty string, configurable in script)

## Customization

### Change default caption

Edit `instagram_uploader.py`:
```python
DEFAULT_CAPTION = "Posted via automation 🤖"  # Your default caption
```

### Change image selection algorithm

The `find_image_to_upload()` function can be easily modified:

```python
def find_image_to_upload() -> Optional[Path]:
    """Find an image to upload."""
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(IMAGES_DIR.glob(f"*{ext}"))
    
    if not image_files:
        return None
    
    # === CUSTOMIZE THIS SECTION ===
    
    # Current: Alphabetical (first)
    image_files.sort()
    return image_files[0]
    
    # Alternative 1: Random selection
    # import random
    # return random.choice(image_files)
    
    # Alternative 2: Oldest file first
    # return min(image_files, key=lambda x: x.stat().st_mtime)
    
    # Alternative 3: Newest file first
    # return max(image_files, key=lambda x: x.stat().st_mtime)
```

## License
MIT.



