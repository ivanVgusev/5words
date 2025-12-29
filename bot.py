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
logging.basicConfig(
    filename='logs/bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ================== UTILS ==================

def reader(path, encoding='utf-8'):
    with open(path, encoding=encoding) as f:
        return f.read().splitlines()


# ================== MERRIAM-WEBSTER ==================

def connect_mw(word):
    url = f'https://www.dictionaryapi.com/api/v3/references/learners/json/{word}?key={MW_API_KEY}'
    r = requests.get(url)
    if r.status_code != 200:
        return None

    data = r.json()
    if not data or isinstance(data[0], str):
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
        return [word, definition, ipa, pos]
    except Exception:
        return None


# ================== GIGACHAT HELPERS ==================

def gigachat_request(prompt, temperature=0.4):
    with GigaChat(credentials=AUTH_KEY, ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat({
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        })
        return response.choices[0].message.content.strip()


def emoji_for_word(word, definition, pos):
    prompt = (
        f"Return exactly one suitable emoji for the word {word} "
        f"({definition}, {pos}). No text."
    )
    res = gigachat_request(prompt, 0.2)
    emojis = ''.join(c for c in res if c != emoji.demojize(c))
    return emojis[0] if emojis else '🔹'


def translate(word, definition, pos):
    prompt = (
        "Translate into Russian. Lowercase. One or two words only.\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}"
    )
    res = gigachat_request(prompt, 0.3)
    res = res.lower().strip('').lstrip()
    return res if 0 < len(res.split()) <= 2 else None


def example_sentence(word, definition, pos):
    print("example_sentence")
    prompt = (
        "Generate ONE example sentence (max 13 words).\n"
        f"Word: {word}\nDefinition: {definition}\nPOS: {pos}\n"
        "Return only the sentence wrapped in *."
    )
    res = gigachat_request(prompt, 0.8)
    match = re.findall(r'\*(.*?)\*', res)
    return match[0] if match else None


# ================== WORD PICKER ==================

def pick_words(amount=5):
    print("pick words")
    dictionary = reader(DICTIONARY_FILE)
    picked = []

    while len(picked) < amount:
        word_raw = random.choice(dictionary)
        print(word_raw)
        mw_data = connect_mw(word_raw)
        if not mw_data:
            continue

        base = parse_mw(mw_data)
        print(base)
        if not base:
            continue

        example = example_sentence(base[0], base[1], base[3])
        translation = translate(base[0], base[1], base[3])
        emoji_symbol = emoji_for_word(base[0], base[1], base[3])

        if None in (example, translation):
            continue

        picked.append(base + [example, translation, emoji_symbol])
        print(picked)

    return picked


# ================== SENDER ==================

def send_daily_words():
    print("send_daily_words")
    try:
        words = pick_words()
        bot.send_message(CHAT_ID, 'Пять слов на сегодня!\n')

        for w in words:
            text = (
                f"{w[6]} {w[0].upper()} /{w[2]}/ – {w[5]}\n"
                f"{w[1]}\n\n{w[4]}"
            )
            bot.send_message(CHAT_ID, text, disable_notification=True)

        logging.info("Daily words sent successfully")

    except Exception as e:
        logging.error(f"Sending failed: {e}")


# ================== SCHEDULER ==================

def scheduler():
    sched.every().day.at("09:00").do(send_daily_words)

    while True:
        sched.run_pending()
        time.sleep(1)


# ================== ENTRY ==================

if __name__ == '__main__':
    threading.Thread(target=scheduler, daemon=True).start()
    while True:
        time.sleep(60)
