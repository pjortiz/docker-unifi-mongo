#!/bin/bash
# Script to generate shield badges from build_info.json files
# Dynamically builds a table organized by major version (3.x, 4.x, 5.x, etc.)

set -e

# Output file where table will be saved
BADGES_TABLE_FILE=".badges_table_content.txt"

# Temporary file to store badge data
TEMP_FILE=$(mktemp)
VERSIONS_TEMP=$(mktemp)
trap "rm -f $TEMP_FILE $VERSIONS_TEMP" EXIT

# Function to create shield badge markdown with proper escaping for shields.io
create_badge() {
    local name=$1
    # URL encode the name for shields.io
    local encoded_name="${name//-/--}"
    local url="https://hub.docker.com/layers/portiz93/unifi-mongo/${name}"
    # Static shield badge format
    echo "[![tag -  ${name}](https://img.shields.io/badge/tag-${encoded_name}-blue?logo=Docker)](${url})"
}

# Find all build_info.json files and process them
find build_info -name "build_info.json" -type f | sort | while IFS= read -r file; do
    # Extract version info from JSON
    name=$(jq -r '.name' "$file" 2>/dev/null || echo "")
    
    if [ -z "$name" ]; then
        continue
    fi
    
    # Determine major version from file path
    # Path format: build_info/X.Y.Z/distro/build_info.json
    major_version=$(echo "$file" | grep -oP 'build_info/\K[0-9](?=\.)')
    
    # Create the badge
    badge=$(create_badge "$name")
    
    # Strip codename from version (remove suffix after first hyphen)
    version_no_codename="${name%%-*}"
    if [ -n "$version_no_codename" ]; then
        echo "$version_no_codename" >> "$VERSIONS_TEMP"
    fi

    # Output: major_version|badge
    echo "${major_version}|${badge}" >> "$TEMP_FILE"
done

# Read from temp file and organize by major version, dynamically discovering versions
declare -A version_badges
declare -a found_versions

if [ -f "$TEMP_FILE" ]; then
    while IFS='|' read -r major_ver badge; do
        if [ -z "${version_badges[$major_ver]}" ]; then
            version_badges[$major_ver]="$badge"
            found_versions+=("$major_ver")
        else
            version_badges[$major_ver]="${version_badges[$major_ver]}<br>$badge"
        fi
    done < "$TEMP_FILE"
fi

# Sort found versions numerically
IFS=$'\n' found_versions=($(sort -n <<<"${found_versions[*]}"))
unset IFS

# Build header row dynamically
header_row="| "
separator_row="| "
data_row="|"

for ver in "${found_versions[@]}"; do
    header_row+="${ver}.x | "
    separator_row+="- | "
    data_row+="${version_badges[$ver]}|"
done

# Build the complete dynamic table with actual newlines
{
    echo "${header_row%| } |"
    echo "${separator_row%| } |"
    echo "${data_row}"
} > "$BADGES_TABLE_FILE"

# Output just the file path - we'll read it in the workflow
echo "$BADGES_TABLE_FILE"

# Determine latest version (no codename) and write to file
if [ -s "$VERSIONS_TEMP" ]; then
    latest=$(sort -V "$VERSIONS_TEMP" | tail -n1)
    echo "$latest" > .badges_latest_version.txt
    echo ".badges_latest_version.txt"
fi
