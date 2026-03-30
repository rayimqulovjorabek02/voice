#!/usr/bin/env bash
# Xatolik bo'lsa to'xtatish
set -o errexit

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# FFmpeg-ni majburiy o'rnatish (Render uchun)
mkdir -p ffmpeg
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz | tar -xJ --strip-components=1 -C ffmpeg
export PATH=$PATH:$(pwd)/ffmpeg/bin
