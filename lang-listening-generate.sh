#!/bin/bash

# Generate and save examples from your vocab list when online,
# reuse when offline.

usage() {
    echo "Usage: $0 <online/offline> <language> <examples dir> [vocab file] [espeak args]" >&2
    echo "e.g. $0 online Indonesian id ~/indo-examples/ ~/indo-vocab.txt"
    exit 1
}

if [ $# -lt 4 ];then
    usage
fi

mode=$1
shift
language=$1
shift
examples_dir=$1
shift
vocab_file=$1

if [ -n $vocab_file ];then
    shift
fi

mkdir -p "$examples_dir"

script_dir=$(dirname $0)
generate="python $script_dir/lang-example-generate.py --count 5 --language $language"
speak="python $script_dir/lang-listening-ui.py -- $@"

if [ "$mode" == "offline" ];then
    $speak 3< <(cat "$examples_dir"/*.jsonl | shuf)
elif [ "$mode" == "online" ];then
    counter=$(($(ls "$examples_dir"/*.jsonl | wc -l) + 1))
    tempfile=$(mktemp)
    filename="$examples_dir/example-$counter.jsonl"
    if [ -z "$vocab_file" ];then
        $generate > "$filename"
    else
        shuf "$vocab_file" | head -n 20 | $generate > "$tempfile"
        # In case I want to Ctrl-c
        mv "$tempfile" "$filename"
    fi
    $speak 3< "$filename"
else
    usage
fi
