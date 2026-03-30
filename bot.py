import os
import re
import logging
import tempfile
import subprocess
import threading
import http.server
import socketserver
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from gtts import gTTS
import speech_recognition as sr

# --- SOZLAMALAR ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN") # Render-da BOT_TOKEN deb kiriting
PORT = int(os.getenv("PORT", 10000))

# --- MODELLAR VA TILLAR ---
MODE_TTS = "tts"
MODE_STT = "stt"

LANGS = {
    "uz": {"name": "🇺🇿 O'zbek", "gtts": "uz", "sr": "uz-UZ"},
    "ru": {"name": "🇷🇺 Русский", "gtts": "ru", "sr": "ru-RU"},
    "en": {"name": "🇺🇸 English", "gtts": "en", "sr": "en-US"}
}

# Foydalanuvchi sozlamalari (Vaqtinchalik xotira)
user_data = {}

def get_lang(uid): return user_data.get(uid, {}).get("lang", "uz")
def get_mode(uid): return user_data.get(uid, {}).get("mode", MODE_TTS)

def L(uid, key):
    lang = get_lang(uid)
    texts = {
        "start": {"uz": "Assalomu alaykum! Tilni tanlang:", "ru": "Привет! Выберите язык:", "en": "Hello! Choose language:"},
        "mode_select": {"uz": "Xizmatni tanlang:", "ru": "Выберите услуgu:", "en": "Select service:"},
        "tts_req": {"uz": "Matn yuboring (ovozga aylantiraman):", "ru": "Отправьте текст:", "en": "Send text:"},
        "stt_req": {"uz": "Ovozli xabar yuboring (matnga aylantiraman):", "ru": "Отправьте голосовое сообщение:", "en": "Send voice message:"},
        "stt_wait": {"uz": "Eshityapman... 🎧", "ru": "Слушаю... 🎧", "en": "Listening... 🎧"},
        "stt_result": {"uz": "Natija: \n\n*{}*", "ru": "Результат: \n\n*{}*", "en": "Result: \n\n*{}*"},
        "stt_err": {"uz": "Ovozni tushuna olmadim yoki serverda xato.", "ru": "Не удалось распознать голос.", "en": "Could not recognize voice."},
        "menu": {"uz": "Asosiy menyu", "ru": "Главное меню", "en": "Main menu"},
        "back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"}
    }
    return texts.get(key, {}).get(lang, "Error")

# --- KLAVIATURALAR ---
def lang_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(v["name"], callback_data=f"lang_{k}")] for k, v in LANGS.items()])

def mode_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗣 Text-to-Speech", callback_data="mode_tts")],
        [InlineKeyboardButton("🎤 Speech-to-Text", callback_data="mode_stt")],
        [InlineKeyboardButton(L(uid, "back"), callback_data="start")]
    ])

def back_keyboard(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(L(uid, "back"), callback_data="modes")]])

# --- DUMMY SERVER (RENDER UCHUN) ---
def run_dummy_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        logger.info(f"Dummy server {PORT}-portda ishlamoqda")
        httpd.serve_forever()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid] = user_data.get(uid, {"lang": "uz", "mode": MODE_TTS})
    await update.effective_message.reply_text(L(uid, "start"), reply_markup=lang_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data.startswith("lang_"):
        user_data[uid]["lang"] = query.data.split("_")[1]
        await query.edit_message_text(L(uid, "mode_select"), reply_markup=mode_keyboard(uid))
    
    elif query.data == "mode_tts":
        user_data[uid]["mode"] = MODE_TTS
        await query.edit_message_text(L(uid, "tts_req"), reply_markup=back_keyboard(uid))
    
    elif query.data == "mode_stt":
        user_data[uid]["mode"] = MODE_STT
        await query.edit_message_text(L(uid, "stt_req"), reply_markup=back_keyboard(uid))
    
    elif query.data == "start":
        await query.edit_message_text(L(uid, "start"), reply_markup=lang_keyboard())
    
    elif query.data == "modes":
        await query.edit_message_text(L(uid, "mode_select"), reply_markup=mode_keyboard(uid))
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # Agar foydalanuvchi hali til tanlamagan bo'lsa, startga qaytarish
    if uid not in user_data:
        user_data[uid] = {"lang": "uz", "mode": MODE_TTS}

    # TTS Rejimi bo'lsa
    if get_mode(uid) == MODE_TTS:
        # Yuklanish xabari (ixtiyoriy)
        status = await update.message.reply_text("⏳...")
        try:
            # gTTS yordamida ovoz yaratish
            lang_code = LANGS[get_lang(uid)]["gtts"]
            tts = gTTS(text=text, lang=lang_code)
            
            # Vaqtinchalik faylga saqlash
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_name = tmp.name
                tts.save(temp_name)
            
            # Ovozli xabar qilib yuborish (Voice)
            with open(temp_name, 'rb') as voice_file:
                await update.message.reply_voice(voice=voice_file)
            
            # Faylni o'chirish
            if os.path.exists(temp_name):
                os.unlink(temp_name)
                
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            await update.message.reply_text("Xatolik: Ovoz yaratib bo'lmadi.")
        finally:
            await status.delete()
    else:
        # Agar STT rejimida bo'lsa-yu, matn yuborsa
        await update.message.reply_text(L(uid, "stt_req"))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_mode(uid) == MODE_STT:
        status = await update.message.reply_text(L(uid, "stt_wait"))
        ogg_path = None
        wav_path = None
        try:
            file = await context.bot.get_file(update.message.voice.file_id)
            temp_dir = tempfile.gettempdir()
            ogg_path = os.path.join(temp_dir, f"v_{uid}.ogg")
            wav_path = os.path.join(temp_dir, f"v_{uid}.wav")
            await file.download_to_drive(ogg_path)

            # FFmpeg yo'lini tekshirish
            ffmpeg_exe = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg")
            if not os.path.exists(ffmpeg_exe): ffmpeg_exe = "ffmpeg"

            # Konvertatsiya
            subprocess.run([ffmpeg_exe, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path], 
                           check=True, capture_output=True)

            r = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = r.record(source)
                text = r.recognize_google(audio, language=LANGS[get_lang(uid)]["sr"])
                await update.message.reply_text(L(uid, "stt_result").format(text), 
                                               reply_markup=back_keyboard(uid), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"STT Error: {e}")
            await update.message.reply_text(L(uid, "stt_err"))
        finally:
            for p in [ogg_path, wav_path]:
                if p and os.path.exists(p): os.unlink(p)
            await status.delete()

# --- ASOSIY ISHGA TUSHIRISH ---
if __name__ == '__main__':
    if not TOKEN:
        print("XATO: BOT_TOKEN topilmadi!")
        exit(1)

    # Dummy serverni alohida oqimda yurgizish
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("Bot ishga tushdi...")
    app.run_polling()
