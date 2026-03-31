import os
import logging
import tempfile
import subprocess
import threading
import http.server
import socketserver
import asyncio
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import edge_tts
import speech_recognition as sr

# --- SOZLAMALAR ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# --- MODELLAR VA TILLAR ---
MODE_TTS = "tts"
MODE_STT = "stt"

LANGS = {
    "uz": {"name": "🇺🇿 O'zbek", "voice": "uz-UZ-MadinaNeural", "sr": "uz-UZ"},
    "ru": {"name": "🇷🇺 Русский", "voice": "ru-RU-SvetlanaNeural", "sr": "ru-RU"},
    "en": {"name": "🇺🇸 English", "voice": "en-US-GuyNeural", "sr": "en-US"}
}

user_data = {}

def get_lang(uid): return user_data.get(uid, {}).get("lang", "uz")
def get_mode(uid): return user_data.get(uid, {}).get("mode", MODE_TTS)

def L(uid, key):
    lang = get_lang(uid)
    texts = {
        "start": {"uz": "Assalomu alaykum! Tilni tanlang:", "ru": "Привет! Выберите язык:", "en": "Hello! Choose language:"},
        "mode_select": {"uz": "Xizmatni tanlang:", "ru": "Выберите услугу:", "en": "Select service:"},
        "tts_req": {"uz": "Matn yuboring (ovozga aylantiraman):", "ru": "Отправьте текст:", "en": "Send text:"},
        "stt_req": {"uz": "Ovozli xabar yuboring (matnga aylantiraman):", "ru": "Отправьте голосовое сообщение:", "en": "Send voice message:"},
        "stt_wait": {"uz": "Eshityapman... 🎧", "ru": "Слушаю... 🎧", "en": "Listening... 🎧"},
        "stt_result": {"uz": "Natija: \n\n*{}*", "ru": "Результат: \n\n*{}*", "en": "Result: \n\n*{}*"},
        "stt_err": {"uz": "Ovozni tushuna olmadim yoki FFmpeg xatosi.", "ru": "Не удалось распознать голос.", "en": "Recognition error."},
        "back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"}
    }
    return texts.get(key, {}).get(lang, "...")

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
        logger.info(f"Dummy server running on port {PORT}")
        httpd.serve_forever()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid] = {"lang": "uz", "mode": MODE_TTS}
    await update.message.reply_text(L(uid, "start"), reply_markup=lang_keyboard())

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
    if uid not in user_data: user_data[uid] = {"lang": "uz", "mode": MODE_TTS}
    
    if get_mode(uid) == MODE_TTS:
        status = await update.message.reply_text("⏳...")
        temp_name = None
        try:
            lang_cfg = LANGS[get_lang(uid)]
            communicate = edge_tts.Communicate(update.message.text, lang_cfg["voice"])
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                temp_name = tmp.name
            await communicate.save(temp_name)
            with open(temp_name, 'rb') as vf:
                await update.message.reply_voice(voice=vf)
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            await update.message.reply_text("Xatolik yuz berdi.")
        finally:
            if temp_name and os.path.exists(temp_name): os.unlink(temp_name)
            await status.delete()

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_data: user_data[uid] = {"lang": "uz", "mode": MODE_TTS}
    
    if get_mode(uid) == MODE_STT:
        status = await update.message.reply_text(L(uid, "stt_wait"))
        ogg_p, wav_p = None, None
        try:
            file = await context.bot.get_file(update.message.voice.file_id)
            tmp_dir = tempfile.gettempdir()
            ogg_p = os.path.join(tmp_dir, f"v_{uid}.ogg")
            wav_p = os.path.join(tmp_dir, f"v_{uid}.wav")
            await file.download_to_drive(ogg_p)

            f_exe = os.path.join(os.getcwd(), "ffmpeg_bin", "ffmpeg")
            if not os.path.exists(f_exe): f_exe = "ffmpeg"

            subprocess.run([f_exe, "-y", "-i", ogg_p, "-ar", "16000", "-ac", "1", wav_p], check=True, capture_output=True)

            r = sr.Recognizer()
            with sr.AudioFile(wav_p) as source:
                audio = r.record(source)
                text = r.recognize_google(audio, language=LANGS[get_lang(uid)]["sr"])
                await update.message.reply_text(L(uid, "stt_result").format(text), reply_markup=back_keyboard(uid), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"STT Error: {e}")
            await update.message.reply_text(L(uid, "stt_err"))
        finally:
            for p in [ogg_p, wav_p]:
                if p and os.path.exists(p): os.unlink(p)
            await status.delete()

# --- MAIN ---
if __name__ == '__main__':
    if not TOKEN: exit("BOT_TOKEN is missing!")
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Bot started...")
    app.run_polling()
# Dummy serverni biroz ishonchliroq qilish
def run_dummy_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return

    with socketserver.TCPServer(("0.0.0.0", PORT), QuietHandler) as httpd:
        logger.info(f"Render uchun Dummy server {PORT}-portda ochildi")
        httpd.serve_forever()

# Main qismini quyidagicha yozing
if __name__ == '__main__':
    if not TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        exit(1)

    # Serverni asosiy oqimdan oldin ishga tushirish
    t = threading.Thread(target=run_dummy_server, daemon=True)
    t.start()

    # Botni qurish
    app = Application.builder().token(TOKEN).build()
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Bot polling rejimida ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True) # Eski xabarlarni tashlab yuboradi (Conflict-ni kamaytiradi)
