#!/bin/bash

# install dependencies specified in pyproject.toml
pip install --upgrade pip
pip install -e .[dev]

# install missing dependencies for connecting to X11 server
# https://doc.qt.io/qt-6/linux-requirements.html
# https://doc.qt.io/qt-6/linux.html
# install Bluetooth dependencies
# https://wiki.debian.org/BluetoothUser
sudo apt-get update && \
sudo apt-get install -y build-essential \
libgl1-mesa-dev \
libfontconfig1-dev \
libfreetype6-dev \
libx11-dev \
libx11-xcb-dev \
libxext-dev \
libxfixes-dev \
libxi-dev \
libxrender-dev \
libxcb1-dev \
libxcb-glx0-dev \
libxcb-keysyms1-dev \
libxcb-image0-dev \
libxcb-shm0-dev \
libxcb-icccm4-dev \
libxcb-sync-dev \
libxcb-xfixes0-dev \
libxcb-shape0-dev \
libxcb-randr0-dev \
libxcb-render-util0-dev \
libxcb-util-dev \
libxcb-xinerama0-dev \
libxcb-xkb-dev \
libxkbcommon-dev \
libxkbcommon-x11-dev \
bluez
