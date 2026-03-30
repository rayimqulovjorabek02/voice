#!/usr/bin/env bash
set -o errexit

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# Agar ffmpeg papkasi bo'lmasa, yaratish
mkdir -p ffmpeg_bin

# FFmpeg-ni yuklab olish (statik havola)
# Agar birinchisi xato bersa, muqobil havola ishlatiladi
curl -L https://github.com/eugeneware/ffmpeg-static/releases/download/b5.0.1/linux-x64 -o ffmpeg_bin/ffmpeg

# Unga ruxsat berish
chmod +x ffmpeg_bin/ffmpeg

# PATH-ni tekshirish uchun (Build vaqtida)
export PATH=$PATH:$(pwd)/ffmpeg_bin
