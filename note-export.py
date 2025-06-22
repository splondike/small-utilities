#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime


def parse_tags(tags_string):
    """Parse tags string into original and expanded arrays."""
    if not tags_string:
        return [], []
    
    original_tags = []
    expanded_tags = []
    
    for tag in tags_string.split():
        tag = tag.strip('#')
        if tag not in original_tags:
            original_tags.append(tag)
        
        if '__' in tag:
            parts = tag.split('__')
            for i in range(len(parts), 0, -1):
                hierarchical_tag = '__'.join(parts[:i])
                if hierarchical_tag not in expanded_tags:
                    expanded_tags.append(hierarchical_tag)
        else:
            if tag not in expanded_tags:
                expanded_tags.append(tag)
    
    return original_tags, expanded_tags


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
    lines = content.split('\n')
    
    if not lines or lines[0].strip() != '---':
        return {}, content
    
    frontmatter_end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            frontmatter_end = i
            break
    
    if frontmatter_end == -1:
        return {}, content
    
    frontmatter_lines = lines[1:frontmatter_end]
    frontmatter = {}
    
    for line in frontmatter_lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            if key == 'tags':
                original_tags, expanded_tags = parse_tags(value)
                frontmatter[key] = original_tags
                frontmatter['expanded_tags'] = expanded_tags
            else:
                frontmatter[key] = value
    
    body = '\n'.join(lines[frontmatter_end + 1:])
    return frontmatter, body


def extract_summary(body):
    """Extract summary from markdown body."""
    if not body:
        return ""
    
    lines = body.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            if line.startswith('#'):
                return ""
            return line
    
    return ""


def parse_created_at_from_filename(filename):
    """Parse created_at timestamp from filename format: YYMMDDHHMM-..."""
    try:
        timestamp_part = filename.split('-')[0]
        if len(timestamp_part) != 10:
            return None
        
        year = int('20' + timestamp_part[:2])
        month = int(timestamp_part[2:4])
        day = int(timestamp_part[4:6])
        hour = int(timestamp_part[6:8])
        minute = int(timestamp_part[8:10])
        
        dt = datetime(year, month, day, hour, minute, 0)
        return dt.isoformat()
    except (ValueError, IndexError):
        return None


def process_md_file(file_path):
    """Process a single markdown file and return its frontmatter as JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        frontmatter, body = parse_frontmatter(content)
        frontmatter['file_path'] = str(file_path)
        
        created_at = parse_created_at_from_filename(file_path.name)
        if created_at:
            frontmatter['created_at'] = created_at
        
        # Ensure tags, expanded_tags and title are always present
        if 'tags' not in frontmatter:
            frontmatter['tags'] = []
        if 'expanded_tags' not in frontmatter:
            frontmatter['expanded_tags'] = []
        if 'title' not in frontmatter:
            frontmatter['title'] = ""
        
        # Add summary from body
        frontmatter['summary'] = extract_summary(body)
        
        return frontmatter
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description='Convert .md files to JSONL format')
    parser.add_argument('directories', nargs='+', help='One or more directories containing .md files')
    
    args = parser.parse_args()
    
    for directory in args.directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"Error: Directory '{directory}' does not exist", file=sys.stderr)
            sys.exit(1)
        if not dir_path.is_dir():
            print(f"Error: '{directory}' is not a directory", file=sys.stderr)
            sys.exit(1)
        
        for md_file in dir_path.glob('*.md'):
            result = process_md_file(md_file)
            if result:
                print(json.dumps(result))


if __name__ == '__main__':
    main()