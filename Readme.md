# 🎙 Ovoz ↔ Matn Telegram Boti

**Butunlay bepul** — Google TTS + Google Speech Recognition.

## ✨ Funksiyalar

| Yuborasiz | Olasiz | Texnologiya |
|-----------|--------|-------------|
| 📝 Matn | 🔊 Ovoz (MP3) | gTTS (Google) |
| 🎤 Ovoz | 📝 Matn | Google Speech Recognition |

🌐 **Tillar:** 🇺🇿 O'zbek · 🇷🇺 Rus · 🇬🇧 Ingliz

---

## 🚀 O'rnatish

### 1. ffmpeg o'rnatish
```bash
# Ubuntu/Debian
sudo apt install ffmpeg -y

# macOS
brew install ffmpeg
```

### 2. Kutubxonalar
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> ⚠️ PyAudio muammo bo'lsa:
> ```bash
> # Ubuntu
> sudo apt install portaudio19-dev
> pip install PyAudio
> ```

### 3. Token sozlash
```bash
cp .env.example .env
# .env ni oching, tokenni kiriting
```

[@BotFather](https://t.me/BotFather) → `/newbot` → tokenni oling.

### 4. Ishga tushirish
```bash
python bot.py
```

---

## 📱 Buyruqlar

| Buyruq | Vazifa |
|--------|--------|
| `/start` | Boshlash |
| `/lang` | Til tanlash |
| `/help` | Yordam |