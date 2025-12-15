# auto_cover_art

This app is a command-line tool that scans audio files to check for missing album art and automatically retrieves and embeds it into the files. It relies on the acoustic signature and not on reading any metadata. 

## Setup

### Prerequisites
- Python 3.6 or higher
- FFmpeg installed and available in your PATH
- Chromaprint (`fpcalc`) installed

### Prequisite installation

```
brew install chromaprint
mkdir ven
python3 -m venv ./venv
source venv/bin/activate
python3 -m pip install mutagen
```
### Environment Variables

Set the `ACOUSTID_API_KEY` environment variable to your AcoustID API key. This is required for the tool to function.

```bash
export ACOUSTID_API_KEY="your_acoustid_api_key"
```

### Usage

Run the script with the following command: ```python3 auto_cover_art.py FILE```

or recursively like ```bash batch_cover_art.sh DIRECTORY```
