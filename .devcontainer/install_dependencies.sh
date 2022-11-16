#!/bin/bash

# install dependencies specified in pyproject.toml
pip install --upgrade pip
pip install -e .[dev]

# install missing OS dependencies
sudo apt-get update && \
sudo apt-get install -y libegl-dev libxkbcommon-x11-0 libdbus-1-dev '^libxcb.*-dev'
