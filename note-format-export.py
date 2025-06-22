#!/usr/bin/env python3
import sys
import json
import argparse
import re

def main():
    parser = argparse.ArgumentParser(description='Format JSONL stream using template string')
    parser.add_argument('format_string', help='Format string with %token% placeholders')
    args = parser.parse_args()
    
    format_string = args.format_string
    
    # Read JSONL from stdin
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
                
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            # Replace %token% placeholders with values from JSON
            output = format_string.replace('\\n', '\n')
            tokens = re.findall(r'%([^%]+)%', format_string)
            
            for token in tokens:
                value = data.get(token, '')
                output = output.replace(f'%{token}%', str(value))
            
            print(output.strip())
            
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()
