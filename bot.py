import threading
import time
import schedule as sched
import telebot
from telebot import types
import random
import re
from gigachat import GigaChat
import requests
import logging
import emoji
import os
from dotenv import load_dotenv
import json
import datetime

# INIT

load_dotenv()

AUTH_KEY = os.getenv("AUTH_KEY")
CERTIFICATE_PATH = os.getenv("CERTIFICATE_PATH")
MW_API_KEY = os.getenv("api_merriam_webster")

CHAT_ID = os.getenv("test_CHAT_ID")
BOT_TOKEN = os.getenv("test_BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
DICTIONARY_FILE = "dictionary.txt"

MAX_ATTEMPTS = 100

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# UTILS

def reader(filepath, encoding="utf-8"):
    with open(filepath, encoding=encoding) as f:
        return f.read()

# MERRIAM-WEBSTER

def connect_mw_dictionary(word: str):
    url = f"https://www.dictionaryapi.com/api/v3/references/learners/json/{word}?key={MW_API_KEY}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception:
        logger.exception(f"MW request failed: {word}")
        return None

    if not data or isinstance(data[0], str):
        logger.info(f"MW invalid entry: {word}")
        return None

    return data

def fetch_dictionary_result(data):
    try:
        entry = data[0]

        word = entry["meta"]["id"]
        pos = entry.get("fl")
        pronunciation = entry["hwi"]["prs"][0]["ipa"]
        definition = entry["def"][0]["sseq"][0][0][1]["dt"][0][1]

        definition = re.sub(r"\{.*?\}", "", definition).strip().capitalize()
        word = re.sub(r"[^\w]", "", word).capitalize()

        if not all([word, definition, pronunciation, pos]):
            raise ValueError("Empty MW fields")

        return [word, definition, pronunciation, pos]

    except Exception:
        logger.exception("MW parsing error")
        return None

def merriam_webster_pick(word):
    data = connect_mw_dictionary(word)
    if not data:
        return None
    return fetch_dictionary_result(data)

# GIGACHAT HELPERS

def gigachat_request(message, temperature=0.3):
    try:
        with GigaChat(credentials=AUTH_KEY, ca_bundle_file=CERTIFICATE_PATH) as giga:
            response = giga.chat({
                "model": "GigaChat",
                "messages": [{"role": "user", "content": message}],
                "temperature": temperature
            })
            return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("GigaChat request failed")
        return None

def gigachat_word_CEFR_checker(info):
    word, definition, _, pos = info
    msg = (
        "Return ONLY the word if CEFR C1/C2, otherwise None.\n"
        f"Word: {word}, definition: {definition}, POS: {pos}"
    )
    res = gigachat_request(msg)
    return word if res == word else None

def gigachat_categories_filter(info):
    word, definition, *_ = info
    msg = (
        "Return ONLY the word if common vocabulary, otherwise None.\n"
        f"Word: {word}, definition: {definition}"
    )
    res = gigachat_request(msg)
    return word if res == word else None

def gigachat_sentence_examples(info):
    word, definition, _, pos = info
    msg = f"Generate ONE short example sentence (max 13 words) using '{word}'."
    res = gigachat_request(msg, temperature=0.8)
    if not res:
        return None
    matches = re.findall(r"\*([^*]+)\*", res)
    return matches[0] if matches else None

def gigachat_translate(info):
    word, definition, _, pos = info
    msg = f"Translate '{word}' into Russian using definition '{definition}'. Output ONLY translation."
    res = gigachat_request(msg)
    if not res or len(res.split()) > 2:
        return None
    return res.lower()

def gigachat_emoji(info):
    word, definition, *_ = info
    msg = f"Return exactly ONE emoji suitable for '{word}' meaning '{definition}'."
    res = gigachat_request(msg, temperature=0.2)
    if not res:
        return "🔹"
    emojis = [c for c in res if c != emoji.demojize(c)]
    return emojis[0] if emojis else "🔹"

# CORE LOGIC

def channel_wordpicker_func():
    dictionary = reader(DICTIONARY_FILE).splitlines()
    words = []

    attempts = 0
    while len(words) < 5 and attempts < MAX_ATTEMPTS:
        attempts += 1
        raw_word = random.choice(dictionary)

        basic = merriam_webster_pick(raw_word)
        if not basic:
            continue

        if not gigachat_word_CEFR_checker(basic):
            continue

        if not gigachat_categories_filter(basic):
            continue

        example = gigachat_sentence_examples(basic)
        translation = gigachat_translate(basic)
        emoji_symbol = gigachat_emoji(basic)

        if None in (example, translation, emoji_symbol):
            continue

        words.append(basic + [example, translation, emoji_symbol])
        logger.info(f"Accepted word: {raw_word}")

    if len(words) < 5:
        logger.error("Failed to collect enough words")
        return

    send_words(words)

def send_words(words):
    try:
        bot.send_message(CHAT_ID, "Пять слов на сегодня!\n")
        for w in words:
            text = (
                f"{w[6]} {w[0].upper()} /{w[2]}/ – {w[5]}\n"
                f"{w[1]}\n\n{w[4]}"
            )
            bot.send_message(CHAT_ID, text, disable_notification=True)
    except Exception:
        logger.exception("Telegram send failed")

# SCHEDULER

def mode_switcher():
    if datetime.datetime.now().weekday() == 6:
        logger.info("Sunday mode (idioms) skipped for now")
    else:
        channel_wordpicker_func()

def daily_grabber():
    sched.every().minute.at(":00").do(mode_switcher)
    while True:
        sched.run_pending()
        time.sleep(1)

# BOT

@bot.message_handler(commands=["start"])
def start(message: types.Message):
    bot.send_message(message.chat.id, "Подбираю слова…")
    channel_wordpicker_func()

if __name__ == "__main__":
    threading.Thread(target=daily_grabber, daemon=True).start()
    bot.polling(none_stop=True)
