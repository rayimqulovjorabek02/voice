#!/usr/bin/env bash
# Xatolik bo'lsa to'xtatish
set -o errexit

# Kutubxonalarni majburiy o'rnatish
pip install --upgrade pip
pip install python-telegram-bot gTTS SpeechRecognition pydub

# Agar kodingizda 'ffmpeg' kerak bo'lsa (ovoz uchun):
# apt-get update && apt-get install -y ffmpeg
