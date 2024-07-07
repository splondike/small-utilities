#!/bin/sh

parallel -j 4 'trans -no-translate -s id -download-audio-as {#}.mp3 "{}"'
