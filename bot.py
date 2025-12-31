import time
import random
import re
import os
import logging
import requests
import emoji
import schedule as sched

from dotenv import load_dotenv
from telebot import TeleBot
from gigachat import GigaChat

# ================== INIT ==================

load_dotenv()

AUTH_KEY = os.getenv('AUTH_KEY')
CERTIFICATE_PATH = os.getenv('CERTIFICATE_PATH')
MW_API_KEY = os.getenv('api_merriam_webster')

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

DICTIONARY_FILE = 'dictionary.txt'

bot = TeleBot(BOT_TOKEN)
os.makedirs('logs', exist_ok=True)

# ================== LOGGING ==================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
)

logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL == "DEBUG" else logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ================== UTILS ==================

def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()

# ================== MERRIAM-WEBSTER ==================

def mw_request(word):
    url = (
        "https://www.dictionaryapi.com/api/v3/references/"
        f"learners/json/{word}?key={MW_API_KEY}"
    )

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        if not data or isinstance(data[0], str):
            return None

        return data

    except Exception:
        logger.exception("MW request failed")
        return None


def mw_parse(data):
    try:
        entry = data[0]

        word = re.sub(r'\W|\d', '', entry['meta']['id']).capitalize()
        pos = entry['fl']
        ipa = entry['hwi']['prs'][0]['ipa']

        definition = entry['def'][0]['sseq'][0][0][1]['dt'][0][1]
        definition = re.sub(r'\{.*?\}', '', definition).capitalize()

        return word, definition, ipa, pos

    except Exception:
        logger.exception("MW parse failed")
        return None

# ================== GIGACHAT ==================

def gigachat(prompt, temperature=0.4):
    try:
        with GigaChat(
            credentials=AUTH_KEY,
            ca_bundle_file=CERTIFICATE_PATH
        ) as giga:
            r = giga.chat({
                "model": "GigaChat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            })
            return r.choices[0].message.content.strip()
    except Exception:
        logger.exception("GigaChat failed")
        return None


def get_emoji(word, definition, pos):
    prompt = (
        f"Return exactly one suitable emoji for the word "
        f"{word} ({definition}, {pos}). No text."
    )
    res = gigachat(prompt, 0.2)
    chars = ''.join(c for c in (res or '') if c != emoji.demojize(c))
    return chars[0] if chars else '🔹'


def translate(word, definition, pos):
    prompt = (
        "Translate into Russian. Lowercase. One or two words only.\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}"
    )
    res = gigachat(prompt, 0.3)
    if not res:
        return None

    res = res.lower().strip()
    return res if 1 <= len(res.split()) <= 2 else None


def example_sentence(word, definition, pos):
    prompt = (
        "Generate ONE example sentence (max 13 words).\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}\n"
        "Return only the sentence wrapped in *."
    )
    res = gigachat(prompt, 0.8)
    m = re.findall(r'\*(.*?)\*', res or '')
    return m[0] if m else None

# ================== WORD PICKER ==================

def pick_words(count=5):
    dictionary = read_lines(DICTIONARY_FILE)
    result = []

    while len(result) < count:
        raw = random.choice(dictionary)

        data = mw_request(raw)
        if not data:
            continue

        parsed = mw_parse(data)
        if not parsed:
            continue

        word, definition, ipa, pos = parsed

        example = example_sentence(word, definition, pos)
        translation = translate(word, definition, pos)
        emoji_symbol = get_emoji(word, definition, pos)

        if None in (example, translation):
            continue

        result.append(
            (word, definition, ipa, pos, example, translation, emoji_symbol)
        )

    return result

# ================== SENDER ==================

def send_daily_words():
    logger.info("Sending daily words")

    words = pick_words()

    bot.send_message(CHAT_ID, "Пять слов на сегодня!\n")

    for w in words:
        text = (
            f"{w[6]} {w[0].upper()} /{w[2]}/ – {w[5]}\n"
            f"{w[1]}\n\n{w[4]}"
        )
        bot.send_message(CHAT_ID, text, disable_notification=True)

    logger.info("Words sent")

# ================== SCHEDULER ==================

def run_scheduler():
    logger.info("Scheduler started")
    sched.every().day.at("09:00").do(send_daily_words)

    while True:
        sched.run_pending()
        time.sleep(1)

# ================== ENTRY ==================

if __name__ == "__main__":
    logger.info("Bot started")
    run_scheduler()
