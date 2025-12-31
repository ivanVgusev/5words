import time
import threading
import schedule as sched
import telebot
import random
import re
import os
import logging
import requests
import emoji
from dotenv import load_dotenv
from gigachat import GigaChat

# ================== INIT ==================

load_dotenv()

AUTH_KEY = os.getenv('AUTH_KEY')
CERTIFICATE_PATH = os.getenv('CERTIFICATE_PATH')
MW_API_KEY = os.getenv('api_merriam_webster')

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('main_CHAT_ID')

bot = telebot.TeleBot(BOT_TOKEN)

DICTIONARY_FILE = 'dictionary.txt'

os.makedirs('logs', exist_ok=True)

# ================== LOGGING ==================

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

LOG_LEVEL = os.getenv("LOG_LEVEL")
if LOG_LEVEL == "DEBUG":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.DEBUG)
    logging.getLogger("telebot").setLevel(logging.DEBUG)
    logging.getLogger("schedule").setLevel(logging.DEBUG)
    logging.getLogger("gigachat").setLevel(logging.DEBUG)
    
elif LOG_LEVEL == "INFO":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("telebot").setLevel(logging.INFO)
    logging.getLogger("schedule").setLevel(logging.INFO)
    logging.getLogger("gigachat").setLevel(logging.INFO)

# ================== UTILS ==================

def reader(path, encoding='utf-8'):
    logger.debug(f"Reading file: {path}")
    with open(path, encoding=encoding) as f:
        lines = f.read().splitlines()
    logger.debug(f"Loaded {len(lines)} lines")
    return lines

# ================== MERRIAM-WEBSTER ==================

def connect_mw(word):
    logger.debug(f"MW request for word: {word}")
    url = f'https://www.dictionaryapi.com/api/v3/references/learners/json/{word}?key={MW_API_KEY}'

    try:
        r = requests.get(url, timeout=10)
        logger.debug(f"MW status={r.status_code}, size={len(r.text)}")
    except Exception:
        logger.exception("MW request failed")
        return None

    if r.status_code != 200:
        logger.error("MW status != 200")
        return None

    data = r.json()
    if not data or isinstance(data[0], str):
        logger.warning("MW returned empty or suggestions")
        return None

    return data


def parse_mw(data):
    try:
        entry = data[0]
        word = re.sub(r'\W|\d', '', entry['meta']['id']).capitalize()
        definition = entry['def'][0]['sseq'][0][0][1]['dt'][0][1]
        definition = re.sub(r'\{.*?\}', '', definition).capitalize()
        ipa = entry['hwi']['prs'][0]['ipa']
        pos = entry['fl']
        logger.debug(f"Parsed MW: {word}, {pos}")
        return [word, definition, ipa, pos]
    except Exception:
        logger.exception("MW parse failed")
        return None

# ================== GIGACHAT ==================

def gigachat_request(prompt, temperature=0.4):
    logger.debug(f"GigaChat prompt: {prompt.replace(chr(10), ' ')}")
    try:
        with GigaChat(credentials=AUTH_KEY, ca_bundle_file=CERTIFICATE_PATH) as giga:
            response = giga.chat({
                "model": "GigaChat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            })
            content = response.choices[0].message.content.strip()
            logger.debug(f"GigaChat response: {content}")
            return content
    except Exception:
        logger.exception("GigaChat request failed")
        return None


def emoji_for_word(word, definition, pos):
    prompt = f"Return exactly one suitable emoji for the word {word} ({definition}, {pos}). No text."
    res = gigachat_request(prompt, 0.2)
    emojis = ''.join(c for c in res or '' if c != emoji.demojize(c))
    return emojis[0] if emojis else '🔹'


def translate(word, definition, pos):
    prompt = (
        "Translate into Russian. Lowercase. One or two words only.\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}"
    )
    res = gigachat_request(prompt, 0.3)
    if not res:
        return None
    res = res.lower().strip()
    return res if 0 < len(res.split()) <= 2 else None


def example_sentence(word, definition, pos):
    prompt = (
        "Generate ONE example sentence (max 13 words).\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}\n"
        "Return only the sentence wrapped in *."
    )
    res = gigachat_request(prompt, 0.8)
    match = re.findall(r'\*(.*?)\*', res or '')
    return match[0] if match else None

# ================== WORD PICKER ==================

def pick_words(amount=5):
    logger.debug(f"Picking {amount} words")
    dictionary = reader(DICTIONARY_FILE)
    picked = []
    attempts = 0

    while len(picked) < amount:
        attempts += 1
        word_raw = random.choice(dictionary)
        logger.debug(f"Attempt {attempts}: {word_raw}")

        mw_data = connect_mw(word_raw)
        if not mw_data:
            continue

        base = parse_mw(mw_data)
        if not base:
            continue

        example = example_sentence(base[0], base[1], base[3])
        translation = translate(base[0], base[1], base[3])
        emoji_symbol = emoji_for_word(base[0], base[1], base[3])

        if None in (example, translation):
            logger.debug("Rejected: missing example or translation")
            continue

        picked.append(base + [example, translation, emoji_symbol])
        logger.debug(f"Accepted word: {base[0]}")

    logger.debug(f"Picked {len(picked)} words in {attempts} attempts")
    return picked

# ================== SENDER ==================

def send_daily_words():
    logger.info("Sending daily words")
    try:
        words = pick_words()
        bot.send_message(CHAT_ID, 'Пять слов на сегодня!\n')

        for w in words:
            text = (
                f"{w[6]} {w[0].upper()} /{w[2]}/ – {w[5]}\n"
                f"{w[1]}\n\n{w[4]}"
            )
            bot.send_message(CHAT_ID, text, disable_notification=True)

        logger.info("Daily words sent successfully")

    except Exception:
        logger.exception("Sending failed")

# ================== SCHEDULER ==================

def scheduler():
    logger.info("Scheduler started")
    sched.every().day.at("09:00").do(send_daily_words)

    while True:
        sched.run_pending()
        time.sleep(1)

# ================== ENTRY ==================

if __name__ == '__main__':
    logger.info("Bot starting")
    threading.Thread(target=scheduler, daemon=True).start()
    while True:
        time.sleep(60)
