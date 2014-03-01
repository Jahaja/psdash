#!/bin/sh

apt-get update -y
apt-get upgrade -y
apt-get install -y build-essential python-dev python-pip
pip install flask psutil
