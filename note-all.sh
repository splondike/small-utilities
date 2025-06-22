#!/bin/sh

cd $(dirname $0)
python note-export.py $(jq -r '.note_types[].location' < ~/.config/makenote-config.json)
