#!/bin/bash

# Allow you to use $EDITOR to adjust the set of docker images you want to keep. The rest will be removed.
orig_images=$(mktemp)
kept_images=$(mktemp)

docker images | grep -v '^REPOSITORY' > $orig_images
cp $orig_images $kept_images

$EDITOR $kept_images

if [ $? -eq 0 ];then
    comm -3 -2 <(awk '{print $3}' $orig_images | sort) <(awk '{print $3}' $kept_images | sort) | xargs docker rmi
fi

rm $orig_images $kept_images
