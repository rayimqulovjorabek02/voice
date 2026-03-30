import os
import re
import logging
import tempfile
import subprocess
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

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
CHANNEL_ID       = os.getenv("CHANNEL_ID", "@your_channel")
ELEVENLABS_KEY   = os.getenv("ELEVENLABS_API_KEY", "")

# ElevenLabs ovoz ID lari (multilingual-v2 modeli barcha tilni qo'llab-quvvatlaydi)
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah ovozi (tabiiy, universal)
ELEVENLABS_MODEL    = "eleven_multilingual_v2"

# Render uchun soxta port ochish (Port scan timeout xatosini yo'qotadi)
def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

# Serverni alohida oqimda ishga tushiramiz
threading.Thread(target=run_dummy_server, daemon=True).start()

# ─── TILLAR ──────────────────────────────────────────────────────

LANGS = {
    "uz": {
        "name": "O'zbek", "flag": "🇺🇿",
        "gtts": "tr", "sr": "uz-UZ",  # gTTS uz ni qo'llamaydi, tr (turk) yaqin
        "not_member":    "❌ Botdan foydalanish uchun kanalga a'zo bo'ling:\n\n👉 {channel}\n\nA'zo bo'lgandan so'ng /start bosing.",
        "check_btn":     "✅ A'zo bo'ldim",
        "menu_title":    "📋 Xizmatni tanlang:",
        "btn_tts":       "🔊 Matn → Ovoz",
        "btn_stt":       "🎤 Ovoz → Matn",
        "btn_translate": "🌐 Tarjima",
        "btn_lang":      "⚙️ Tilni o'zgartirish",
        "ask_tts":       "✍️ Ovozga aylantirish uchun matn yuboring:",
        "ask_stt":       "🎤 Matnga aylantirish uchun ovozli xabar yuboring:",
        "ask_translate": "✍️ Tarjima qilish uchun matn yuboring:\n\n(Til avtomatik aniqlanadi → O'zbek tarjima qilinadi)",
        "tts_wait":      "🔊 Ovozga aylantirilmoqda...",
        "stt_wait":      "📝 Ovoz tanilmoqda...",
        "tr_wait":       "🌐 Tarjima qilinmoqda...",
        "stt_result":    "📝 *Tanilgan matn:*\n\n{}",
        "tr_result":     "🌐 *Tarjima:*\n\n{}",
        "tts_ok":        "🔊 Tayyor!",
        "stt_err":       "❌ Ovoz tanib bo'lmadi. Aniqroq gapiring.",
        "stt_srv_err":   "❌ Xizmat ishlamayapti. Keyinroq urinib ko'ring.",
        "tts_err":       "❌ Ovoz yaratishda xato: {}",
        "tr_err":        "❌ Tarjimada xato: {}",
        "send_voice":    "⚠️ Iltimos ovozli xabar yuboring.",
        "send_text":     "⚠️ Iltimos matn yuboring.",
        "select_lang":   "🌐 Tilni tanlang:",
        "lang_set":      "✅ Til o'zgartirildi: {} {}",
        "welcome":       "👋 Salom, {}!\n\nXizmatni tanlang 👇",
    },
    "ru": {
        "name": "Русский", "flag": "🇷🇺",
        "gtts": "ru", "sr": "ru-RU",
        "not_member":    "❌ Для использования бота подпишитесь на канал:\n\n👉 {channel}\n\nПосле подписки нажмите /start.",
        "check_btn":     "✅ Я подписался",
        "menu_title":    "📋 Выберите услугу:",
        "btn_tts":       "🔊 Текст → Голос",
        "btn_stt":       "🎤 Голос → Текст",
        "btn_translate": "🌐 Перевод",
        "btn_lang":      "⚙️ Сменить язык",
        "ask_tts":       "✍️ Отправьте текст для озвучки:",
        "ask_stt":       "🎤 Отправьте голосовое сообщение:",
        "ask_translate": "✍️ Отправьте текст для перевода:\n\n(Язык определяется автоматически → переводится на Русский)",
        "tts_wait":      "🔊 Озвучиваю...",
        "stt_wait":      "📝 Распознаю голос...",
        "tr_wait":       "🌐 Перевожу...",
        "stt_result":    "📝 *Распознанный текст:*\n\n{}",
        "tr_result":     "🌐 *Перевод:*\n\n{}",
        "tts_ok":        "🔊 Готово!",
        "stt_err":       "❌ Не удалось распознать. Говорите чётче.",
        "stt_srv_err":   "❌ Сервис недоступен. Попробуйте позже.",
        "tts_err":       "❌ Ошибка озвучки: {}",
        "tr_err":        "❌ Ошибка перевода: {}",
        "send_voice":    "⚠️ Пожалуйста, отправьте голосовое сообщение.",
        "send_text":     "⚠️ Пожалуйста, отправьте текст.",
        "select_lang":   "🌐 Выберите язык:",
        "lang_set":      "✅ Язык изменён: {} {}",
        "welcome":       "👋 Привет, {}!\n\nВыберите услугу 👇",
    },
    "en": {
        "name": "English", "flag": "🇬🇧",
        "gtts": "en", "sr": "en-US",
        "not_member":    "❌ To use the bot, please join our channel:\n\n👉 {channel}\n\nAfter joining, press /start.",
        "check_btn":     "✅ I joined",
        "menu_title":    "📋 Select a service:",
        "btn_tts":       "🔊 Text → Voice",
        "btn_stt":       "🎤 Voice → Text",
        "btn_translate": "🌐 Translate",
        "btn_lang":      "⚙️ Change language",
        "ask_tts":       "✍️ Send text to convert to voice:",
        "ask_stt":       "🎤 Send a voice message to transcribe:",
        "ask_translate": "✍️ Send text to translate:\n\n(Language detected automatically → translated to English)",
        "tts_wait":      "🔊 Converting to speech...",
        "stt_wait":      "📝 Recognizing voice...",
        "tr_wait":       "🌐 Translating...",
        "stt_result":    "📝 *Recognized text:*\n\n{}",
        "tr_result":     "🌐 *Translation:*\n\n{}",
        "tts_ok":        "🔊 Done!",
        "stt_err":       "❌ Could not recognize. Speak more clearly.",
        "stt_srv_err":   "❌ Service unavailable. Try again later.",
        "tts_err":       "❌ Voice error: {}",
        "tr_err":        "❌ Translation error: {}",
        "send_voice":    "⚠️ Please send a voice message.",
        "send_text":     "⚠️ Please send a text message.",
        "select_lang":   "🌐 Select language:",
        "lang_set":      "✅ Language set: {} {}",
        "welcome":       "👋 Hello, {}!\n\nSelect a service 👇",
    },
}

# Rejimlar
MODE_TTS       = "tts"
MODE_STT       = "stt"
MODE_TRANSLATE = "translate"

# Foydalanuvchi holati
user_state: dict = {}


# ─── YORDAMCHI FUNKSIYALAR ────────────────────────────────────────

def get_lang(uid: int) -> str:
    return user_state.get(uid, {}).get("lang", None)

def get_mode(uid: int):
    return user_state.get(uid, {}).get("mode", None)

def L(uid: int, key: str) -> str:
    lang = get_lang(uid) or "uz"
    return LANGS[lang][key]

def set_state(uid: int, **kwargs):
    if uid not in user_state:
        user_state[uid] = {}
    user_state[uid].update(kwargs)

def escape_md(text: str) -> str:
    import re as _re
    result = _re.sub(r'[_*\[\]()~`>#+=|{}.!$]', '', text)
    return result.strip() or "Foydalanuvchi"

def ogg_to_wav(ogg: str, wav: str) -> bool:
    """OGG ni WAV ga aylantirish - ffmpeg yoki pydub orqali"""
    # 1. ffmpeg bilan urinish
    for cmd in ["ffmpeg", "avconv"]:
        try:
            r = subprocess.run(
                [cmd, "-y", "-i", ogg, "-ar", "16000", "-ac", "1", wav],
                capture_output=True, timeout=30
            )
            if r.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 2. pydub bilan urinish
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(ogg, format="ogg")
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(wav, format="wav")
        return True
    except Exception as e:
        logger.warning(f"pydub xato: {e}")

    # 3. SpeechRecognition built-in converter
    try:
        import speech_recognition as _sr
        r = _sr.Recognizer()
        with _sr.AudioFile(ogg) as source:
            audio_data = r.record(source)
        with open(wav, "wb") as f:
            f.write(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
        return True
    except Exception as e:
        logger.warning(f"SR converter xato: {e}")

    return False

async def check_membership(bot, uid: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Membership tekshirish xato: {e}")
        return True  # Xato bo'lsa (kanal private yoki bot admin emas) - o'tkazib yuborish

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{v['flag']} {v['name']}", callback_data=f"lang_{k}")]
        for k, v in LANGS.items()
    ])

def menu_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(L(uid, "btn_tts"),       callback_data="mode_tts")],
        [InlineKeyboardButton(L(uid, "btn_stt"),       callback_data="mode_stt")],
        [InlineKeyboardButton(L(uid, "btn_translate"), callback_data="mode_translate")],
        [InlineKeyboardButton(L(uid, "btn_lang"),      callback_data="show_lang")],
    ])


# ─── /start ──────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)

    # 1. Til tanlanmagan bo'lsa — til tanlash
    if not lang:
        await update.message.reply_text(
            "🌐 Tilni tanlang / Выберите язык / Select language:",
            reply_markup=lang_keyboard(),
        )
        return

    # 2. Kanal a'zoligini tekshirish
    is_member = await check_membership(context.bot, uid)
    if not is_member:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
            [InlineKeyboardButton(L(uid, "check_btn"), callback_data="check_member")],
        ])
        await update.message.reply_text(
            L(uid, "not_member").format(channel=CHANNEL_ID),
            reply_markup=kb
        )
        return

    # 3. Menyu ko'rsatish
    name = escape_md(update.effective_user.first_name or "Foydalanuvchi")
    set_state(uid, mode=None)
    await update.message.reply_text(
        L(uid, "welcome").format(name),
        reply_markup=menu_keyboard(uid),
        parse_mode="Markdown",
    )


# ─── CALLBACKS ───────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # Til tanlash
    if data.startswith("lang_"):
        code = data.replace("lang_", "")
        set_state(uid, lang=code)
        info = LANGS[code]

        # Kanal a'zoligini tekshirish
        is_member = await check_membership(context.bot, uid)
        if not is_member:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
                [InlineKeyboardButton(L(uid, "check_btn"), callback_data="check_member")],
            ])
            await query.edit_message_text(
                L(uid, "not_member").format(channel=CHANNEL_ID),
                reply_markup=kb
            )
            return

        name = escape_md(query.from_user.first_name or "Foydalanuvchi")
        set_state(uid, mode=None)
        await query.edit_message_text(
            L(uid, "welcome").format(name),
            reply_markup=menu_keyboard(uid),
            parse_mode="Markdown"
        )
        return

    # Kanal a'zoligini qayta tekshirish
    if data == "check_member":
        is_member = await check_membership(context.bot, uid)
        if not is_member:
            await query.answer(L(uid, "not_member").format(channel=CHANNEL_ID)[:200], show_alert=True)
            return
        name = escape_md(query.from_user.first_name or "Foydalanuvchi")
        set_state(uid, mode=None)
        await query.edit_message_text(
            L(uid, "welcome").format(name),
            reply_markup=menu_keyboard(uid),
            parse_mode="Markdown"
        )
        return

    # Til o'zgartirish menyusi
    if data == "show_lang":
        await query.edit_message_text(
            L(uid, "select_lang"),
            reply_markup=lang_keyboard()
        )
        return

    # Rejim tanlash
    if data == "mode_tts":
        set_state(uid, mode=MODE_TTS)
        await query.edit_message_text(L(uid, "ask_tts"))
        return

    if data == "mode_stt":
        set_state(uid, mode=MODE_STT)
        await query.edit_message_text(L(uid, "ask_stt"))
        return

    if data == "mode_translate":
        set_state(uid, mode=MODE_TRANSLATE)
        await query.edit_message_text(L(uid, "ask_translate"))
        return

    # Menyuga qaytish
    if data == "back_menu":
        set_state(uid, mode=None)
        name = escape_md(query.from_user.first_name or "Foydalanuvchi")
        await query.edit_message_text(
            L(uid, "welcome").format(name),
            reply_markup=menu_keyboard(uid),
            parse_mode="Markdown"
        )
        return


# ─── MATN XABARLARI ──────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    lang = get_lang(uid)
    mode = get_mode(uid)

    # Til tanlanmagan bo'lsa
    if not lang:
        await update.message.reply_text(
            "🌐 Tilni tanlang / Выберите язык / Select language:",
            reply_markup=lang_keyboard()
        )
        return

    # Kanal a'zoligini tekshirish
    is_member = await check_membership(context.bot, uid)
    if not is_member:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
            [InlineKeyboardButton(L(uid, "check_btn"), callback_data="check_member")],
        ])
        await update.message.reply_text(
            L(uid, "not_member").format(channel=CHANNEL_ID),
            reply_markup=kb
        )
        return

    # Rejim tanlanmagan bo'lsa - menyu ko'rsat
    if not mode:
        await update.message.reply_text(
            L(uid, "menu_title"),
            reply_markup=menu_keyboard(uid)
        )
        return

    # Ovoz → Matn rejimida matn kelsa
    if mode == MODE_STT:
        await update.message.reply_text(
            L(uid, "send_voice"),
            reply_markup=back_keyboard(uid)
        )
        return

    # Matn → Ovoz
    if mode == MODE_TTS:
        await do_tts(update, uid, text)
        return

    # Tarjima
    if mode == MODE_TRANSLATE:
        await do_translate(update, uid, text)
        return


# ─── OVOZ XABARLARI ──────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    mode = get_mode(uid)

    if not get_lang(uid):
        await update.message.reply_text("🌐 Tilni tanlang:", reply_markup=lang_keyboard())
        return

    if not mode:
        await update.message.reply_text(L(uid, "menu_title"), reply_markup=menu_keyboard(uid))
        return

    if mode in (MODE_TTS, MODE_TRANSLATE):
        await update.message.reply_text(L(uid, "send_text"))
        return

    if mode == MODE_STT:
        await do_stt(update, context, uid)
        return


# ─── TTS ─────────────────────────────────────────────────────
# ─── MATNNI TTS UCHUN TAYYORLASH ─────────────────────────────────

def prepare_text_for_tts(text: str, lang: str) -> str:
    """Matnni TTS uchun tozalash va tayyorlash"""
    import re

    # URL larni olib tashlash
    text = re.sub(r'http\S+|www\.\S+', '', text)

    # Telegram mention va hashtaglarni tozalash
    text = re.sub(r'[@#]\w+', '', text)

    # Raqamlarni so'zga aylantirish (oddiy holatlar)
    number_words_uz = {
        '0': 'nol', '1': 'bir', '2': 'ikki', '3': 'uch',
        '4': 'tort', '5': 'besh', '6': 'olti', '7': 'yetti',
        '8': 'sakkiz', '9': 'toqqiz', '10': 'on',
    }
    number_words_ru = {
        '0': 'ноль', '1': 'один', '2': 'два', '3': 'три',
        '4': 'четыре', '5': 'пять', '6': 'шесть', '7': 'семь',
        '8': 'восемь', '9': 'девять', '10': 'десять',
    }

    # Emojilarni olib tashlash
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(' ', text)

    # Ko'p bo'sh joylarni birlashtirish
    text = re.sub(r'\s+', ' ', text).strip()

    # Matn bo'sh bo'lsa standart xabar
    if not text:
        if lang == "uz":
            return "Matn bo'sh"
        elif lang == "ru":
            return "Текст пустой"
        else:
            return "Empty text"

    return text


def build_elevenlabs_payload(text: str, lang: str) -> dict:
    """ElevenLabs uchun optimal payload yaratish"""

    # Har bir til uchun optimallashtirilgan sozlamalar
    voice_settings = {
        "uz": {
            # O'zbek: barqaror, aniq, o'rta tezlik
            "stability": 0.65,
            "similarity_boost": 0.80,
            "style": 0.20,
            "use_speaker_boost": True,
        },
        "ru": {
            # Rus: tabiiy, ifodali
            "stability": 0.55,
            "similarity_boost": 0.78,
            "style": 0.30,
            "use_speaker_boost": True,
        },
        "en": {
            # Ingliz: professional, aniq
            "stability": 0.58,
            "similarity_boost": 0.75,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }

    settings = voice_settings.get(lang, voice_settings["en"])

    return {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": settings,
        "pronunciation_dictionary_locators": [],
    }



async def do_tts(update: Update, uid: int, text: str):
    lang = get_lang(uid) or "uz"
    info = LANGS[lang]
    status = await update.message.reply_text(L(uid, "tts_wait"))
    tmp_path = None
    try:
        # Matnni TTS uchun tayyorlash
        clean_text = prepare_text_for_tts(text, lang)
        logger.info(f"TTS boshlandi [{uid}|{lang}]: {clean_text[:50]}")

        fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        if lang == "uz":
            # 🇺🇿 O'zbek — Google TTS
            tts = gTTS(text=clean_text, lang="tr", slow=False)
            tts.save(tmp_path)
            logger.info(f"TTS [gTTS/uz] uid={uid}")

        elif ELEVENLABS_KEY:
            # 🇷🇺🇬🇧 Rus, Ingliz — ElevenLabs (yuqori sifat)
            import httpx as _httpx
            payload = build_elevenlabs_payload(clean_text, lang)
            headers = {
                "xi-api-key": ELEVENLABS_KEY,
                "Content-Type": "application/json",
            }
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            async with _httpx.AsyncClient(timeout=40) as client:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise Exception(f"ElevenLabs {resp.status_code}: {resp.text[:150]}")
            with open(tmp_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"TTS [ElevenLabs/{lang}] uid={uid}")

        else:
            # Fallback — gTTS
            tts = gTTS(text=clean_text, lang=info["gtts"], slow=False)
            tts.save(tmp_path)
            logger.info(f"TTS [gTTS fallback/{lang}] uid={uid}")

        with open(tmp_path, "rb") as audio:
            await update.message.reply_voice(
                voice=audio,
                caption=L(uid, "tts_ok"),
                reply_markup=back_keyboard(uid)
            )
        await status.delete()

    except Exception as e:
        logger.error(f"TTS xato [{uid}]: {e}")
        await status.edit_text(
            L(uid, "tts_err").format(str(e)[:120]),
            reply_markup=back_keyboard(uid)
        )
    finally:
        if tmp_path and Path(tmp_path).exists():
            try: Path(tmp_path).unlink()
            except: pass


# ─── STT ─────────────────────────────────────────────────────────

async def do_stt(update: Update, context, uid: int):
    lang = get_lang(uid) or "uz"
    status = await update.message.reply_text(L(uid, "stt_wait"))
    ogg_path = None
    try:
        voice = update.message.voice or update.message.audio
        tg_file = await context.bot.get_file(voice.file_id)
        fd, ogg_path = tempfile.mkstemp(suffix=".ogg")
        os.close(fd)
        await tg_file.download_to_drive(ogg_path)

        OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

        if OPENAI_KEY:
            # ── OpenAI Whisper API (eng ishonchli) ──────────────
            import httpx as _httpx
            lang_map = {"uz": "uz", "ru": "ru", "en": "en"}
            with open(ogg_path, "rb") as f:
                files = {"file": ("voice.ogg", f, "audio/ogg")}
                data = {
                    "model": "whisper-1",
                    "language": lang_map.get(lang, "ru"),
                    "response_format": "text"
                }
                headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
                async with _httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers=headers, data=data, files=files
                    )
            if resp.status_code != 200:
                raise Exception(f"Whisper API {resp.status_code}: {resp.text[:100]}")
            recognized = resp.text.strip()
            logger.info(f"STT [Whisper/{lang}] uid={uid}: {recognized[:50]}")

        else:
            # ── Google Speech Recognition (fallback) ────────────
            converted_path = ogg_path.replace(".ogg", ".wav")
            converted = ogg_to_wav(ogg_path, converted_path)
            audio_file = converted_path if converted else ogg_path

            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            with sr.AudioFile(audio_file) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = recognizer.record(source)

            info = LANGS[lang]
            recognized = recognizer.recognize_google(audio_data, language=info["sr"])
            logger.info(f"STT [Google/{lang}] uid={uid}: {recognized[:50]}")

            if Path(converted_path).exists():
                Path(converted_path).unlink(missing_ok=True)

        await status.edit_text(
            L(uid, "stt_result").format(recognized),
            parse_mode="Markdown",
            reply_markup=back_keyboard(uid)
        )

    except Exception as e:
        logger.error(f"STT xato [{uid}]: {type(e).__name__}: {e}")
        await status.edit_text(L(uid, "stt_srv_err"), reply_markup=back_keyboard(uid))
    finally:
        if ogg_path and Path(ogg_path).exists():
            try: Path(ogg_path).unlink()
            except: pass


# ─── TARJIMA ─────────────────────────────────────────────────────

async def do_translate(update: Update, uid: int, text: str):
    lang = get_lang(uid) or "uz"
    status = await update.message.reply_text(L(uid, "tr_wait"))
    try:
        from deep_translator import GoogleTranslator
        target = {"uz": "uz", "ru": "ru", "en": "en"}[lang]
        translated = GoogleTranslator(source="auto", target=target).translate(text)
        await status.edit_text(
            L(uid, "tr_result").format(translated),
            parse_mode="Markdown",
            reply_markup=back_keyboard(uid)
        )
    except ImportError:
        await status.edit_text(
            L(uid, "tr_err").format("deep-translator o'rnatilmagan. Quyidagini bajaring:\npip install deep-translator"),
            reply_markup=back_keyboard(uid)
        )
    except Exception as e:
        logger.error(f"Tarjima xato [{uid}]: {e}")
        await status.edit_text(
            L(uid, "tr_err").format(str(e)[:80]),
            reply_markup=back_keyboard(uid)
        )


# ─── MENYUGA QAYTISH TUGMASI ─────────────────────────────────────

def back_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Yana", callback_data=f"mode_{get_mode(uid)}")],
        [InlineKeyboardButton("📋 Menyu", callback_data="back_menu")],
    ])


# ─── ISHGA TUSHIRISH ─────────────────────────────────────────────

def main():
    if TELEGRAM_TOKEN == "YOUR_TOKEN_HERE":
        print("❌ TELEGRAM_BOT_TOKEN sozlanmagan!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    print("🤖 Bot ishga tushdi!")
    print(f"📢 Kanal: {CHANNEL_ID}")
    print("🔊 TTS | 🎤 STT | 🌐 Tarjima")
    print("⏹  To'xtatish: Ctrl+C")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
