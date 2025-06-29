#!/bin/bash

language="indonesian"
elang=id
espeed=150
egap=30

if { true<&3; } 2>/dev/null;then
    true
else
    echo "Need to pipe some words to fd3 using \`practice.sh <3 /tmp/words.txt\`" >&2
    exit 1
fi

all_words=""
while IFS= read -r -u 3 line; do
  all_words="$all_words"$'\n'"$line"
done

while true;do
    words=$(echo "$all_words" | shuf | head -n 10)

    prompt="Consider these words in $language:"$'\n'"$words"$'\n\n'"Generate a one line $language sentence using some of those words for the student to translate to english. Output the $language sentence on the first line and its translation on the second. Do not output anything else."

    data=$(echo "$prompt" | ai --oneshot 2>/dev/null)

    read -p 'enter to play> '
    while true;do
        echo "$data" | head -n 1 | espeak-ng -v $elang -s $espeed -g $egap
        read -p 'enter to replay, n to continue> ' action
        if [ "$action" = "n" ];then
            break
        fi
    done
    echo -n "$data" | head -n 1
    read -p 'enter to show english translation> '
    echo -n -e "\e[90m"
    echo -n "$data" | tail -n 1
    echo -n -e "\e[0m"
    echo ""
done
