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

load_dotenv()

AUTH_KEY = os.getenv('AUTH_KEY')
CERTIFICATE_PATH = os.getenv('CERTIFICATE_PATH')
api_merriam_webster = os.getenv('api_merriam_webster')

CHAT_ID = os.getenv('main_CHAT_ID')
# CHAT_ID = os.getenv('test_CHAT_ID')

BOT_TOKEN = os.getenv('BOT_TOKEN')
# BOT_TOKEN = os.getenv('test_BOT_TOKEN')

bot = telebot.TeleBot(BOT_TOKEN)

dictionary_filename = 'dictionary.txt'

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# .txt reader
def reader(filepath, encoding='utf-8'):
    with open(filepath, 'r', encoding=encoding) as f:
        return f.read()


def gigachat_idiom_emoji(idiom_information):
    """
    Finder of suitable 3-emoji sequence for a selected idiom

    :param idiom_information: [idiom, definition, example]
    :return: str(three emojis)
    """
    idiom, definition, example = idiom_information
    message = (f"Return only the most suitable three-emojis sequence for the idiom {idiom}"
               f"with the definition {definition}"
               f"Do not include any text explanation punctuation quotation marks or additional symbols "
               f"If the word has strong emotional meaning express it through the emoji "
               f"DO NOT say anything else."
               f"Be respectful with idioms associated with diseases"
               f" or with death and choose appropriate emojis."
               f"The output should be exatly THREE non-repeated emojis. If you return more emojis or less emojis,"
               f" this is going to be a huge problem")

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.2
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        emojis = [char for char in response if char != emoji.demojize(char)]
        emojis = "".join(emojis)

        if len(emojis) == 3:
            return emojis
        elif 0 < len(emojis) < 3:
            emojis += '🔹' * (3 - len(emojis))
            return emojis
        elif len(emojis) > 3:
            return emojis[:4]
        else:
            return '🔹🔹🔹'


def gigachat_idioms_explanation(idiom_information):
    """
    Russian explanation-provider for an English idiom

    :param idiom_information: [idiom, definition, example]
    :return: str(explanation) or None
    """
    idiom, definition, example = idiom_information
    message = (
        "##TASK"
        "You are a professional English teacher. CONCISELY explain this idiom in Russian."
        "##FORMATTING"
        "The output must be ONE short Russian sentence (no longer than 13 words)."
        "Write the explanation in **neutral infinitive form** (глагол в неопределённой форме)."
        "Do NOT address the reader in any way."
        "Do NOT use «ты», «вы», «кто-то», «кто-либо», or any pronouns referring to the reader."
        "Do NOT provide examples—just the explanation."
        "##TONE"
        "Academic."
        "##Example"
        "Input:"
        "'were you born in a barn': {'definition': 'an expression chiding someone who has left a door open or who is "
        "ill-mannered or messy'}"
        "Output:"
        "Упрекать за неаккуратность или невоспитанность из-за незакрытой двери."
        "##REAL SITUATION"
        f"{idiom}, {definition}"
    )

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.4
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content
        response = response.strip(". ")
        response = response.capitalize()

        if response == 'None' or response == '' or response == ' ':
            return None

        if len(response) > 0:
            return response
        else:
            return None


def gigachat_categories_filter(word_information):
    """
    Word filter for certain categories.

    :param word_information: [word, definition, pronunciation, POS]
    :return: str(word) if it passed the filter; else – None
    """

    word, definition, pronunciation, POS = word_information
    message = (
        'You are an expert English linguist and lexical classifier.'
        'Task:'
        '1. Decide whether the given English word belongs to ANY of the following categories:'
        '- narrow scientific or medical terminology (anatomy, chemistry, physics, biology, botany, etc.)'
        '- professional jargon (legal, financial, military, engineering, IT)'
        '- rare or obscure technical terms'
        '- archaic or poetic words no longer common in modern English'
        '- slang or strongly region-specific dialect words'
        '- niche culinary or gastronomic terms (rare dishes or ingredients)'
        '- proper names, trademarks, or brand names'
        '- rare artistic or musical theory terms'
        '- highly specific sports terminology'
        '- names of countries, cities, regions, any toponyms'
        '2. If the word belongs to ANY of these categories, output ONLY the string:'
        'None'
        '3. If the word does NOT belong to any of these categories, output ONLY the exact word itself'
        '(without quotes, without explanation).'
        f'Word: {word}, definition: {definition}'
    )

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.4
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        if response == 'None' or response == '' or response == ' ':
            return None

        if len(response) > 0:
            return response
        else:
            return None


def gigachat_word_CEFR_checker(word_information):
    """
    Checker of a word's CEFR level

    :param word_information: [word, definition, pronunciation, POS]
    :return: str(word) if it passed the checker; else – None
    """
    word, definition, pronunciation, POS = word_information
    message = ('You are an expert English linguist and CEFR assessor.'
               'Task:'
               '1. Decide whether the given English word belongs to CEFR level C1, or C2.'
               '2. If it does, output ONLY the exact word (unchanged).'
               '3. If it does not, output ONLY the string None.'
               'Formating: DO NOT add any additional analysis or information, DO NOT explain your reasoning; return '
               'either the word or None; if you add anything else, this will lead to a catastrophe'
               'Examples:'
               'Input:'
               'Word: meticulous'
               'Output:'
               'meticulous'
               'Input:'
               'Word: dog'
               'Output:'
               'None'
               'Now do this in a real case:'
               f'Word: {word}, definition {definition}, part of speech {POS}')

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.4
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        if response == 'None' or response == '' or response == ' ':
            return None

        if len(response) > 0:
            return response
        else:
            return None


def gigachat_idiom_CEFR_checker(idiom_information):
    """
    Checker of an idiom's CEFR level

    :param idiom_information: [word, definition, pronunciation, POS]
    :return: str(idiom) if it passed the checker; else – None
    """
    idiom, definition, example = idiom_information
    message = ('You are an expert English linguist and CEFR assessor.'
               'Task:'
               '1. Decide whether the given English idiom belongs to CEFR level B2, C1, or C2.'
               '2. If it does, output ONLY the exact idiom (unchanged).'
               '3. If it does not, output ONLY the string None.'
               'Formating: DO NOT add any additional analysis or information, DO NOT explain your reasoning; return '
               'either the idiom or None; if you add anything else, this will lead to a catastrophe'
               "Input: pull out all the stops; Output: pull out all the stops"
               "Input: hit the nail on the head; Output: hit the nail on the head"
               "Input: good morning; Output: None"
               "Input: throw caution to the wind; Output: throw caution to the wind"
               "Input: cost an arm and a leg; Output: None"
               f'Idiom: {idiom}, definition {definition}')

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.4
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        if response == 'None' or response == '' or response == ' ':
            return None

        if len(response) > 0:
            return response
        else:
            return None


# creating sentence examples of the picked word
def gigachat_sentence_examples(word_information):
    """
    Provider of usage-examples for words

    :param word_information: [word, definition, pronunciation, POS]
    :return: str(sentence-examples for a word); else – None
    """
    word, definition, pronunciation, POS = word_information
    message = ('Generate an example sentence that demonstrates a real-life context in which the given '
               'vocabulary word can be used.\n\n'
               'Use the following inputs:\n'
               f'- Word: {word}\n'
               f'- Definition: {definition}\n'
               f'- Part of Speech: {POS}\n\n'
               'The sentence should clearly reflect the meaning '
               'of the word and be suitable for helping students understand its use. '
               'At the same time it should not be loo long (try to be concise and use around 10-15 words)\n\n'
               'Format the response as follows:\n'
               '\'Example sentence showing realistic usage.\'\n\n'
               'Formatting rules:\n'
               '- Enclose the example sentence with asterisks on both sides (*).\n'
               '- Do not surround the vocabulary word with bold, or any other special formatting.\n'
               '- Do not address the requester or provide explanations—only output '
               'the formatted example as specified.'
               'The output should consist of ONE simple sentence (no longer than 13 words; any sentence with more words'
               'is STRICTLY PROHIBITED).\n\n'
               'Example:\n'
               'Request is: adversary\n'
               'Response is: *In the heated political climate, the opposition'
               'party often becomes an adversary, fighting against the ruling government on every issue.*')

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.87
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        # deleting all the information that is not surrounded by the * punctuation mark
        matches = re.findall(r'\*([^\*]+)\*', response)
        response = ' '.join(matches)
        response = response.strip(". ")

        if response == 'None' or response == '' or response == ' ':
            return None

        if len(response) > 0:
            return response
        else:
            return None


# emoji finder function
def gigachat_emoji(word_information):
    """
    Finder of one suitable emoji for the selected word

    :param word_information: [word, definition, pronunciation, POS]
    :return: str(1 emoji); else – None
    """
    word, definition, pronunciation, POS = word_information
    message = (f"Return only the most suitable emoji for the word {word} "
               f"with the definition {definition} and part of speech {POS} "
               f"Output must be exactly one emoji "
               f"Do not include any text explanation punctuation quotation marks or additional symbols "
               f"If the word has strong emotional meaning express it through the emoji "
               f"Do not say anything else."
               f"Be respectful words associated with diseases"
               f" or with death and choose an appropriate emoji")

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.2
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content

        emojis = [char for char in response if char != emoji.demojize(char)]
        emojis = "".join(emojis)

        if len(emojis) >= 1:
            return emojis[0]
        else:
            return '🔹'


# translation finder
def gigachat_translate(word_information):
    """
    Word translation

    :param word_information: [word, definition, pronunciation, POS]
    :return: str(translation); else – None
    """
    word, definition, pronunciation, POS = word_information
    message = ('You are a professional English-to-Russian translator.'
               'Translate the given English word into natural Russian using the provided definition and part of '
               'speech.'
               'Input:'
               f'- Word: {word}'
               f'- Definition: {definition}'
               f'- Part of Speech: {POS}'
               'Instructions:'
               '- Output ONLY the correct Russian translation of the word or phrase.'
               '- Use **lowercase letters**.'
               '- It should contain normal spaces between Russian words if the natural translation is a phrase.'
               '- Do NOT include the English word.'
               '- Do NOT add explanations, comments, examples, greetings.'
               '- Return only the translation itself as plain text.')

    request = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.3
    }

    with GigaChat(credentials=AUTH_KEY,
                  ca_bundle_file=CERTIFICATE_PATH) as giga:
        response = giga.chat(request)
        response = response.choices[0].message.content
        response = response.lower()
        response = response.strip(". ")
        sentence_length = len(response.split())

        if response == 'None':
            return None

        if sentence_length <= 2 and sentence_length != 0:
            return response
        else:
            return None


def fetch_dictionary_result(res):
    if res and isinstance(res, list) and len(res) > 0:
        try:
            # the word value is added in order to prevent the API from returning lemmatized words
            # or words with the same stems
            word = res[0]['meta']['id']
            definition = res[0]['def'][0]['sseq'][0][0][1]['dt'][0][1].replace("{bc}", "")
            pronunciation = res[0]['hwi']['prs'][0]['ipa']
            POS = res[0]['fl']

            cleaned_definition = re.sub(r'\{dx\}.*?\{\/dx\}', '', definition, flags=re.DOTALL)
            cleaned_definition = re.sub(r'\{sx\|.*?\}', '', cleaned_definition)
            cleaned_definition = re.sub(r'\{it\}.*?\{\/it\}', "", cleaned_definition)
            cleaned_definition = cleaned_definition.replace('{bc}', '')
            cleaned_definition = cleaned_definition.capitalize()

            cleaned_word = re.sub(r'\{dx\}.*?\{\/dx\}', '', word, flags=re.DOTALL)
            cleaned_word = re.sub(r'\{sx\|.*?\}', '', cleaned_word)
            cleaned_word = re.sub(r'\{it\}.*?\{\/it\}', "", cleaned_word)
            cleaned_word = cleaned_word.replace('{bc}', '')
            cleaned_word = re.sub(r"[^\w\sа-яА-ЯёЁ]", "", cleaned_word)
            cleaned_word = re.sub(r"\d+", "", cleaned_word)

            cleaned_word = cleaned_word.capitalize()

            if cleaned_word == 'None':
                return None
            elif cleaned_definition == 'None':
                return None
            elif pronunciation == 'None':
                return None
            elif POS == 'None':
                return None

            return [cleaned_word, cleaned_definition, pronunciation, POS]
        except Exception:
            return None
    else:
        # logging.warning("Result parsing failed.")
        return None


def connect_mw_dictionary(api_key, word):
    URL = f'https://www.dictionaryapi.com/api/v3/references/learners/json/{word}?key={api_key}'
    r = requests.get(URL)
    r.encoding = 'utf-8'

    if r.status_code != 200:
        logging.error(f"Request failed with status code {r.status_code}: {r.text}")
        return None

    try:
        data = r.json()
    except ValueError as e:
        return None

    if len(data) > 0:
        return data
    else:
        return None


def merriam_webster_pick(word, api_key):
    result = connect_mw_dictionary(api_key, word)

    if result is not None:
        word_information = fetch_dictionary_result(result)
        return word_information
    else:
        return None


def channel_wordpicker_func():
    dictionary = reader(dictionary_filename).split('\n')
    amount_of_words = 5
    counter = 0

    wordpick = []
    while counter != amount_of_words:
        word = random.choice(dictionary)

        basic_word_info = merriam_webster_pick(word, api_merriam_webster)
        if basic_word_info is None or None in basic_word_info:
            logging.warning(f'channel_wordpicker_func() – unsuccessful attempt to fetch merriam-webster info '
                            f'for the word {word}')
            continue
        if gigachat_word_CEFR_checker(basic_word_info) is None:
            logging.warning(f'channel_wordpicker_func() – gigachat_word_CEFR_checker returned negative evaluation'
                            f'for the word {word}')
            continue
        if gigachat_categories_filter(basic_word_info) is None:
            logging.warning(f'channel_wordpicker_func() – gigachat_word_CEFR_checker returned negative evaluation'
                            f'for the word {word}')
            continue
        logging.info(f'channel_wordpicker_func() – successful attempt to fetch merriam-webster info '
                     f'for the word {word}')

        extended_word_info = []
        usage_example = gigachat_sentence_examples(basic_word_info)
        translation = gigachat_translate(basic_word_info)
        emoji_symbol = gigachat_emoji(basic_word_info)

        extended_word_info.append(usage_example)
        extended_word_info.append(translation)
        extended_word_info.append(emoji_symbol)

        if None in extended_word_info:
            logging.warning(f'channel_wordpicker_func() – unsuccessful attempt to access GigaChat'
                            f'for the word {word}')
            continue

        word_info = basic_word_info + extended_word_info
        wordpick.append(word_info)
        counter += 1

    header_text = 'Пять слов на сегодня!\n\n'
    main_body_text = []
    for word in wordpick:
        word_picked = word[0].upper()
        definition = word[1]
        translation = word[5]
        transcription = word[2]
        example = word[4]
        emoji_symbol = word[6]

        # sometimes merriam-webster api contains an empty string for definition; this is the handler of such situations
        if definition is None or definition == '' or definition == ' ':
            word_text = f'{emoji_symbol} {word_picked} /{transcription}/ – {translation}\n\n{example}'
        else:
            word_text = f'{emoji_symbol} {word_picked} /{transcription}/ – {translation}\n{definition}\n\n{example}'
        main_body_text.append(word_text)

    if CHAT_ID is not None:
        # sending a message with a notification
        try:
            bot.send_message(CHAT_ID, header_text)
            for element in main_body_text:
                # sending a message without a notification
                bot.send_message(CHAT_ID, element, disable_notification=True)
        except Exception:
            logging.error("channel_wordpicker_func() – couldn't connect to TELEGRAM")


def bot_wordpicker_func():
    try:
        dictionary = reader(dictionary_filename).split('\n')
        amount_of_words = 5
        counter = 0

        wordpick = []
        while counter != amount_of_words:
            word = random.choice(dictionary)
            word_info = merriam_webster_pick(word, api_merriam_webster)

            if word_info is None:
                continue

            wordpick.append(word_info)
            counter += 1

        main_body_text = []
        for word in wordpick:
            word_picked = word[0].upper()
            definition = word[1]
            transcription = word[2]

            word_text = f'{word_picked} /{transcription}/\n\n{definition}'
            main_body_text.append(word_text)

        return main_body_text
    except Exception:
        logging.error('Error in bot_wordpicker_func()')
        pass


def idiompicker_func():
    with open('idioms.json', 'r') as f:
        idioms = json.load(f)
    amount_of_idioms = 1
    counter = 0

    idiompick = []
    while counter != amount_of_idioms:
        idiom = random.choice(list(idioms))
        definition = idioms.get(idiom).get('definition')
        example = idioms.get(idiom).get('example')

        idiom_checker = gigachat_idiom_CEFR_checker([idiom, definition, example])
        if idiom_checker is None:
            logging.warning(f'channel_wordpicker_func() – unsuccessful attempt to fetch merriam-webster info '
                            f'for the word {idiom}')
            continue

        explanation_ru = gigachat_idioms_explanation([idiom, definition, example])
        emojis = gigachat_idiom_emoji([idiom, definition, example])

        idiompick.append([idiom, definition, example, explanation_ru, emojis])
        counter += 1

    header_text = 'Воскресная идиома!\n\n'
    main_body_text = []
    for idiom in idiompick:
        idiom_picked = idiom[0].upper()
        example = idiom[2]
        explanation_ru = idiom[3]
        emojis = idiom[4]

        word_text = f'{emojis}\n{idiom_picked}\n{explanation_ru}\n\n{example}'
        main_body_text.append(word_text)

    if CHAT_ID is not None:
        # sending a message with a notification
        try:
            bot.send_message(CHAT_ID, header_text)
            for element in main_body_text:
                # sending a message without a notification
                bot.send_message(CHAT_ID, element, disable_notification=True)
        except Exception:
            logging.error("idiompicker_func() – couldn't connect to TELEGRAM")


def mode_switcher():
    """
    Decides, what mode to choose: idioms or words

    :return: None
    """
    date = datetime.datetime.now()
    if date.weekday() == 6:
        idiompicker_func()
    else:
        channel_wordpicker_func()


def daily_grabber():
    sched.every().day.at("09:00").do(mode_switcher)
    while True:
        sched.run_pending()
        time.sleep(1)


@bot.message_handler(commands=['start'])
def start(message: types.Message):
    bot.send_message(message.chat.id, 'Уже подбираю пять новых слов для вас!'
                                      '\nОбычно это занимает у меня пару секунд.')
    info = bot_wordpicker_func()
    for word in info:
        bot.send_message(message.chat.id, word)


if __name__ == '__main__':
    thread = threading.Thread(target=daily_grabber)
    thread.start()
    bot.polling(none_stop=True)
