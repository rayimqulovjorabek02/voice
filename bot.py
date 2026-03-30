import os
import re
import logging
import tempfile
import subprocess
import threading
import http.server
import socketserver
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from gtts import gTTS
import speech_recognition as sr
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# O'zgaruvchilarni olish
TELEGRAM_TOKEN   = os.getenv("BOT_TOKEN") # Render Environment-dan oladi
CHANNEL_ID       = os.getenv("CHANNEL_ID", "@your_channel")
ELEVENLABS_KEY   = os.getenv("ELEVENLABS_API_KEY", "")

# ElevenLabs sozlamalari
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
ELEVENLABS_MODEL    = "eleven_multilingual_v2"

# ─── RENDER UCHUN DUMMY SERVER ────────────────────────────────────
def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"Dummy server {port}-portda ishlamoqda")
        httpd.serve_forever()

# Serverni alohida oqimda ishga tushirish
threading.Thread(target=run_dummy_server, daemon=True).start()

# ─── TILLAR VA REJIMLAR ──────────────────────────────────────────
LANGS = {
    "uz": {
        "name": "O'zbek", "flag": "🇺🇿", "gtts": "tr", "sr": "uz-UZ",
        "not_member": "❌ Botdan foydalanish uchun kanalga a'zo bo'ling:\n\n👉 {channel}",
        "check_btn": "✅ A'zo bo'ldim", "menu_title": "📋 Xizmatni tanlang:",
        "btn_tts": "🔊 Matn → Ovoz", "btn_stt": "🎤 Ovoz → Matn",
        "btn_translate": "🌐 Tarjima", "btn_lang": "⚙️ Tilni o'zgartirish",
        "ask_tts": "✍️ Matn yuboring:", "ask_stt": "🎤 Ovozli xabar yuboring:",
        "ask_translate": "✍️ Tarjima uchun matn yuboring:",
        "tts_wait": "🔊 Tayyorlanmoqda...", "stt_wait": "📝 Tanilmoqda...",
        "tr_wait": "🌐 Tarjima qilinmoqda...", "stt_result": "📝 *Tanilgan matn:*\n\n{}",
        "tr_result": "🌐 *Tarjima:*\n\n{}", "tts_ok": "🔊 Tayyor!",
        "stt_err": "❌ Ovoz tanilmadi.", "stt_srv_err": "❌ Xizmatda xato.",
        "tts_err": "❌ Xato: {}", "tr_err": "❌ Xato: {}",
        "send_voice": "⚠️ Ovozli xabar yuboring.", "send_text": "⚠️ Matn yuboring.",
        "select_lang": "🌐 Tilni tanlang:", "lang_set": "✅ Tanlandi: {}",
        "welcome": "👋 Salom, {}!\nXizmatni tanlang 👇",
    },
    "ru": {
        "name": "Русский", "flag": "🇷🇺", "gtts": "ru", "sr": "ru-RU",
        "not_member": "❌ Подпишитесь на канал:\n\n👉 {channel}",
        "check_btn": "✅ Я подписался", "menu_title": "📋 Выберите услуgu:",
        "btn_tts": "🔊 Текст → Голос", "btn_stt": "🎤 Голос → Текст",
        "btn_translate": "🌐 Перевод", "btn_lang": "⚙️ Язык",
        "ask_tts": "✍️ Отправьте текст:", "ask_stt": "🎤 Отправьте голос:",
        "ask_translate": "✍️ Отправьте текст для перевода:",
        "tts_wait": "🔊 Озвучиваю...", "stt_wait": "📝 Распознаю...",
        "tr_wait": "🌐 Перевожу...", "stt_result": "📝 *Текст:*\n\n{}",
        "tr_result": "🌐 *Перевод:*\n\n{}", "tts_ok": "🔊 Готово!",
        "stt_err": "❌ Не распознано.", "stt_srv_err": "❌ Ошибка сервиса.",
        "tts_err": "❌ Ошибка: {}", "tr_err": "❌ Ошибка: {}",
        "send_voice": "⚠️ Отправьте голос.", "send_text": "⚠️ Отправьте текст.",
        "select_lang": "🌐 Выберите язык:", "lang_set": "✅ Выбрано: {}",
        "welcome": "👋 Привет, {}!\nВыберите услугу 👇",
    }
}

MODE_TTS, MODE_STT, MODE_TRANSLATE = "tts", "stt", "translate"
user_state = {}

# ─── YORDAMCHI FUNKSIYALAR ────────────────────────────────────────
def get_lang(uid): return user_state.get(uid, {}).get("lang", "uz")
def get_mode(uid): return user_state.get(uid, {}).get("mode")
def L(uid, key): return LANGS[get_lang(uid)][key]
def set_state(uid, **kwargs):
    if uid not in user_state: user_state[uid] = {}
    user_state[uid].update(kwargs)

def back_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Yana", callback_data=f"mode_{get_mode(uid)}")],
        [InlineKeyboardButton("📋 Menyu", callback_data="back_menu")],
    ])

async def check_membership(bot, uid):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ("member", "administrator", "creator")
    except: return True

# ─── HANDLERS ────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{v['flag']} {v['name']}", callback_data=f"lang_{k}")] for k, v in LANGS.items()])
    await update.message.reply_text("🌐 Tilni tanlang / Выберите язык:", reply_markup=kb)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("lang_"):
        set_state(uid, lang=data.split("_")[1], mode=None)
        await query.edit_message_text(L(uid, "welcome").format(query.from_user.first_name), 
                                     reply_markup=InlineKeyboardMarkup([
                                         [InlineKeyboardButton(L(uid, "btn_tts"), callback_data="mode_tts")],
                                         [InlineKeyboardButton(L(uid, "btn_stt"), callback_data="mode_stt")],
                                         [InlineKeyboardButton(L(uid, "btn_translate"), callback_data="mode_translate")]
                                     ]))
    elif data.startswith("mode_"):
        mode = data.split("_")[1]
        set_state(uid, mode=mode)
        await query.edit_message_text(L(uid, f"ask_{mode}"))
    elif data == "back_menu":
        set_state(uid, mode=None)
        await query.edit_message_text(L(uid, "menu_title"), 
                                     reply_markup=InlineKeyboardMarkup([
                                         [InlineKeyboardButton(L(uid, "btn_tts"), callback_data="mode_tts")],
                                         [InlineKeyboardButton(L(uid, "btn_stt"), callback_data="mode_stt")],
                                         [InlineKeyboardButton(L(uid, "btn_translate"), callback_data="mode_translate")]
                                     ]))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mode = get_mode(uid)
    if mode == MODE_TTS:
        status = await update.message.reply_text(L(uid, "tts_wait"))
        try:
            tts = gTTS(text=update.message.text, lang=LANGS[get_lang(uid)]["gtts"])
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tts.save(tmp.name)
                await update.message.reply_voice(voice=open(tmp.name, "rb"), caption=L(uid, "tts_ok"), reply_markup=back_keyboard(uid))
            os.unlink(tmp.name)
        except Exception as e: await update.message.reply_text(f"Error: {e}")
        await status.delete()
    elif mode == MODE_TRANSLATE:
        try:
            from deep_translator import GoogleTranslator
            tr = GoogleTranslator(source='auto', target=get_lang(uid)).translate(update.message.text)
            await update.message.reply_text(L(uid, "tr_result").format(tr), reply_markup=back_keyboard(uid), parse_mode="Markdown")
        except: await update.message.reply_text("Translation error.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_mode(uid) == MODE_STT:
        status = await update.message.reply_text(L(uid, "stt_wait"))
        try:
            file = await context.bot.get_file(update.message.voice.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
                await file.download_to_drive(tmp.name)
                # Bu yerda oddiygina gsr ishlatamiz (pydub/ffmpeg o'rnatilgan bo'lishi kerak)
                await update.message.reply_text("Ovozni matnga aylantirish uchun serverda FFmpeg bo'lishi shart.", reply_markup=back_keyboard(uid))
            os.unlink(tmp.name)
        except: await update.message.reply_text(L(uid, "stt_err"))
        await status.delete()

def main():
    if not TELEGRAM_TOKEN: return
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Bot ishga tushdi")
    app.run_polling()

if __name__ == "__main__":
    main()
