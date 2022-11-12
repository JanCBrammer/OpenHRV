#!/bin/bash

pip install PySide6 numpy

# install missing dependencies
sudo apt-get update && \
sudo apt-get install -y libegl-dev libxkbcommon-x11-0 libdbus-1-dev '^libxcb.*-dev'
