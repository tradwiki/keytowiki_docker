#!/bin/sh

docker run -it -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
--device /dev/snd/ \
music_bot
