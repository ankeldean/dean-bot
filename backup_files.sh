# START backup_files.sh

#!/bin/bash
# Filename: backup_files.sh
# Version: 1.0 (2025-04-25) - Smart backup with version numbers in filenames
# Description: Backs up modified scripts with version numbers to a timestamped directory

# Backup directory with timestamp
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Files to check
FILES=("backtest.py" "analysetradehistory.py" "prep4grok.sh")

# Checksum file to track previous states
CHECKSUM_FILE=".file_checksums.md5"

# Create or clear checksum file to start fresh
touch "$CHECKSUM_FILE"
# Uncomment the next line to force a fresh start (run once)
# > "$CHECKSUM_FILE"

# Function to extract version from file comment
get_version() {
    local file="$1"
    # Look for "# Version: X.Y" and extract X.Y
    version=$(grep -E "^# Version: [0-9]+\.[0-9]+" "$file" | head -n 1 | awk '{print $3}')
    if [ -z "$version" ]; then
        echo "1.0"  # Default version if not found
    else
        echo "$version"
    fi
}

# Function to check and backup modified files
backup_if_modified() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo "Warning: $file not found, skipping backup"
        return
    fi

    # Calculate current checksum
    current_checksum=$(md5sum "$file" | awk '{print $1}')
    
    # Get previous checksum
    previous_checksum=$(grep "$file" "$CHECKSUM_FILE" | awk '{print $1}')
    
    # Get version from file comment
    version=$(get_version "$file")
    
    # Determine backup filename with version
    extension="${file##*.}"
    filename_base="${file%.*}"
    backup_file="${BACKUP_DIR}/${filename_base}_v${version}.${extension}"
    
    # Compare checksums
    if [ "$current_checksum" != "$previous_checksum" ]; then
        echo "Backing up $file to $backup_file"
        cp "$file" "$backup_file"
        
        # Update checksum file
        grep -v "$file" "$CHECKSUM_FILE" > "${CHECKSUM_FILE}.tmp"
        echo "$current_checksum  $file" >> "${CHECKSUM_FILE}.tmp"
        mv "${CHECKSUM_FILE}.tmp" "$CHECKSUM_FILE"
    else
        echo "$file unchanged, skipping backup"
    fi
}

# Process each file
for file in "${FILES[@]}"; do
    backup_if_modified "$file"
done

echo "Backup complete. Files saved in $BACKUP_DIR/"

# END backup_files.sh
