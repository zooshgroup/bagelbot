#!/bin/bash

docker build -t bagelbot .
docker run -it bagelbot >> /var/log/bagelbot.log &
