#!/bin/sh

find . -name "*.sync-conflict*" | grep -v "stversions" | while read file;do
    file_extension=$(echo "$file" | grep -o "[a-z]\+$")
    base_file="$(echo $file | sed 's/\.sync-conflict.\+//').$file_extension"
    nvim -d "$file" "$base_file"
    status=$?
    if [ $status -eq 0 ];then
        echo "Deleting"
        rm "$file"
    elif [ $status -eq 1 ];then
        echo "Skipping"
    elif [ $status -eq 2 ];then
        echo "Terminating"
        exit 0
    fi
done
