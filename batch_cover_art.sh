#!/bin/bash

# Batch Cover Art Downloader
# Processes audio files recursively in a directory using auto_cover_art.py

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if directory argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <directory>"
    echo "Example: $0 ~/Music"
    exit 1
fi

TARGET_DIR="$1"

# Check if directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}Error: Directory '$TARGET_DIR' does not exist${NC}"
    exit 1
fi

# Check if auto_cover_art.py exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_COVER_ART="$SCRIPT_DIR/auto_cover_art.py"

if [ ! -f "$AUTO_COVER_ART" ]; then
    echo -e "${RED}Error: auto_cover_art.py not found in $SCRIPT_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}=== Batch Cover Art Downloader ===${NC}"
echo -e "Scanning directory: ${YELLOW}$TARGET_DIR${NC}"
echo ""

# Supported audio file extensions
EXTENSIONS=("mp3" "m4a" "flac" "ogg" "opus" "wav" "aiff" "aif" "ape" "wv" "tta" "mpc" "mp4" "aac" "wma" "alac")

# Build find command with all extensions
FIND_CMD="find \"$TARGET_DIR\" -type f \\( "
for i in "${!EXTENSIONS[@]}"; do
    if [ $i -gt 0 ]; then
        FIND_CMD="$FIND_CMD -o "
    fi
    FIND_CMD="$FIND_CMD -iname \"*.${EXTENSIONS[$i]}\""
done
FIND_CMD="$FIND_CMD \\)"

# Find all audio files
echo -e "${BLUE}Searching for audio files...${NC}"
FILES=()
while IFS= read -r -d $'\0' file; do
    FILES+=("$file")
done < <(eval "$FIND_CMD -print0")

# Check if any files were found
if [ ${#FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No audio files found in '$TARGET_DIR'${NC}"
    exit 0
fi

echo -e "${GREEN}Found ${#FILES[@]} audio file(s):${NC}"
echo ""

# Print all files
for file in "${FILES[@]}"; do
    echo "  $file"
done

echo ""
echo -e "${YELLOW}========================================${NC}"
read -p "Process these ${#FILES[@]} file(s)? (y/n): " -n 1 -r
echo ""
echo -e "${YELLOW}========================================${NC}"
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Operation cancelled${NC}"
    exit 0
fi

# Process files
echo -e "${BLUE}Starting batch processing...${NC}"
echo ""

SUCCESS_COUNT=0
FAILURE_COUNT=0
SKIPPED_COUNT=0
FAILED_FILES=()

for i in "${!FILES[@]}"; do
    file="${FILES[$i]}"
    current=$((i + 1))
    total=${#FILES[@]}
    
    echo -e "${BLUE}[$current/$total]${NC} Processing: ${YELLOW}$(basename "$file")${NC}"
    
    if python3 "$AUTO_COVER_ART" "$file"; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "${GREEN}✓ Success${NC}"
    else
        exit_code=$?
        if [ $exit_code -eq 0 ]; then
            # File was skipped (already has cover art)
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            echo -e "${YELLOW}○ Skipped (already has cover art)${NC}"
        else
            # File processing failed
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
            FAILED_FILES+=("$file")
            echo -e "${RED}✗ Failed${NC}"
        fi
    fi
    echo ""
done

# Print summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}=== Processing Complete ===${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total files:    ${total}"
echo -e "${GREEN}Successful:     ${SUCCESS_COUNT}${NC}"
echo -e "${YELLOW}Skipped:        ${SKIPPED_COUNT}${NC}"
echo -e "${RED}Failed:         ${FAILURE_COUNT}${NC}"
echo -e "${BLUE}========================================${NC}"

# Print failed files if any
if [ $FAILURE_COUNT -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed files:${NC}"
    for file in "${FAILED_FILES[@]}"; do
        echo "  $file"
    done
fi

# Exit with appropriate code
if [ $FAILURE_COUNT -gt 0 ]; then
    exit 1
else
    exit 0
fi
