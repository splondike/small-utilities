#!/bin/sh

DIR=$(jq -r '.note_types | map(select(.name=="person"))[].location' < ~/.config/makenote-config.json)

cd $(dirname $0)

tag=$(python note-export.py $DIR | jq -r .expanded_tags[] | sort | uniq -c | sort -r -n | awk '{print $2}' | fzf)

python note-export.py $DIR | jq -c "select(.expanded_tags[] == \"$tag\")" | python note-format-export.py "* %title% (%appearance%) %tags% \n  %summary%"
