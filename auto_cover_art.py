#!/usr/bin/env python3
"""
Auto Cover Art Downloader
Analyzes audio files using AcoustID, identifies them via MusicBrainz,
and embeds cover art if missing.
"""
import sys
import os
import argparse
import subprocess
import json
import logging
import urllib.request
import urllib.parse
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AcoustID API configuration
ACOUSTID_API_KEY = os.getenv('ACOUSTID_API_KEY')
if not ACOUSTID_API_KEY:
    logger.error("AcoustID API key not found. Please set the 'ACOUSTID_API_KEY' environment variable.")
    sys.exit(1)

ACOUSTID_API_URL = 'https://api.acoustid.org/v2/lookup'
MUSICBRAINZ_API_URL = 'https://musicbrainz.org/ws/2'
COVERARTARCHIVE_URL = 'https://coverartarchive.org/release'

def run_fpcalc(filepath):
    """Run fpcalc to generate audio fingerprint."""
    try:
        result = subprocess.run(
            ['fpcalc', '-json', '-length', '120', filepath],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return data.get('fingerprint'), int(data.get('duration', 0))
    except subprocess.CalledProcessError as e:
        logger.error(f"fpcalc failed: {e}")
        return None, None
    except FileNotFoundError:
        logger.error("fpcalc not found. Please install chromaprint.")
        return None, None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse fpcalc output: {e}")
        return None, None

def lookup_acoustid(fingerprint, duration):
    """Look up fingerprint in AcoustID database."""
    params = {
        'client': ACOUSTID_API_KEY,
        'meta': 'recordings releases',
        'fingerprint': fingerprint,
        'duration': str(duration)
    }
    
    url = f"{ACOUSTID_API_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            if data.get('status') == 'ok':
                return data.get('results', [])
            else:
                logger.error(f"AcoustID error: {data.get('error', {}).get('message')}")
                return []
    except Exception as e:
        logger.error(f"Failed to query AcoustID: {e}")
        return []

def get_cover_art_url(release_id):
    """Get cover art URL from Cover Art Archive."""
    url = f"{COVERARTARCHIVE_URL}/{release_id}"
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            images = data.get('images', [])
            
            # Prefer front cover
            for img in images:
                if img.get('front'):
                    return img.get('image')
            
            # Fallback to first image
            if images:
                return images[0].get('image')
            
            return None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning(f"No cover art found for release {release_id}")
        else:
            logger.error(f"HTTP error fetching cover art: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch cover art URL: {e}")
        return None

def download_image(url):
    """Download image from URL."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None

def embed_cover_art(filepath, image_data):
    """Embed cover art into audio file."""
    try:
        audio = MutagenFile(filepath)
        
        if audio is None:
            logger.error("Unsupported file format")
            return False
        
        # Handle different file formats
        if isinstance(audio, MP4):
            # MP4/M4A
            audio.tags['covr'] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
        elif isinstance(audio, FLAC):
            # FLAC
            picture = Picture()
            picture.type = 3  # Cover (front)
            picture.mime = 'image/jpeg'
            picture.data = image_data
            audio.clear_pictures()
            audio.add_picture(picture)
        else:
            # Try ID3 (MP3, etc.)
            if not audio.tags:
                audio.add_tags()
            
            # Remove existing covers
            audio.tags.delall('APIC')
            
            # Add new cover
            audio.tags.add(
                APIC(
                    encoding=3,  # UTF-8
                    mime='image/jpeg',
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=image_data
                )
            )
        
        audio.save()
        logger.info(f"Successfully embedded cover art in {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to embed cover art: {e}")
        return False

def has_cover_art(filepath):
    """Check if file has embedded cover art using ffprobe."""
    cmd = [
        'ffprobe', 
        '-v', 'quiet', 
        '-print_format', 'json', 
        '-show_streams', 
        '-select_streams', 'v', 
        filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        for stream in data.get('streams', []):
            if stream.get('disposition', {}).get('attached_pic'):
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking cover art: {e}")
        return False

def process_file(filepath):
    """Process a single audio file."""
    logger.info(f"Processing {filepath}...")
    
    # Check if file already has cover art
    if has_cover_art(filepath):
        logger.info("File already has cover art. Skipping.")
        return True
    
    logger.info("No cover art found. Analyzing with AcoustID...")
    
    # Generate fingerprint
    fingerprint, duration = run_fpcalc(filepath)
    if not fingerprint or not duration:
        logger.error("Failed to generate fingerprint")
        return False
    
    logger.info(f"Fingerprint generated (duration: {duration}s)")
    
    # Lookup in AcoustID
    results = lookup_acoustid(fingerprint, duration)
    if not results:
        logger.error("No AcoustID results found")
        return False
    
    logger.info(f"Found {len(results)} AcoustID result(s)")
    
    # Try each result until we find cover art
    for result in results:
        recordings = result.get('recordings', [])
        if not recordings:
            continue
        
        for recording in recordings:
            releases = recording.get('releases', [])
            if not releases:
                continue
            
            for release in releases:
                release_id = release.get('id')
                if not release_id:
                    continue
                
                logger.info(f"Trying release: {release.get('title', 'Unknown')} ({release_id})")
                
                # Get cover art URL
                cover_url = get_cover_art_url(release_id)
                if not cover_url:
                    continue
                
                logger.info(f"Found cover art URL: {cover_url}")
                
                # Download image
                image_data = download_image(cover_url)
                if not image_data:
                    continue
                
                logger.info(f"Downloaded cover art ({len(image_data)} bytes)")
                
                # Embed cover art
                if embed_cover_art(filepath, image_data):
                    logger.info("Successfully added cover art!")
                    return True
    
    logger.warning("No cover art could be found or embedded")
    return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Auto Cover Art Downloader')
    parser.add_argument('file', help='Audio file to process')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    success = process_file(os.path.abspath(args.file))
    sys.exit(0 if success else 1)

