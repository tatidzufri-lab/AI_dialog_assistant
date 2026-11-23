"""Тексты бота на двух языках и выбор языка.

Язык диалога: /start en|ru → /language, /en, /ru → язык Telegram
(ru, uk, be, kk → русский, иначе английский) → по ходу разговора:
кириллица → русский, 3+ латинских слова → английский.
"""

import re

LANGS = ("ru", "en")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def lang_from_telegram(language_code: str | None) -> str:
    if not language_code:
        return "ru"
    return "ru" if language_code.lower().startswith(("ru", "uk", "be", "kk")) else "en"


def lang_from_text(text: str) -> str | None:
    if _CYRILLIC.search(text):
        return "ru"
    if len(_LATIN_WORD.findall(text)) >= 3:
        return "en"
    return None


TEXTS = {
    "start": {
        "ru": (
            "Здравствуй. Рада, что ты заглянула в пространство ретрита «Познай себя».\n\n"
            "Я — твоя проводница в этом коротком разговоре. Мы не торопимся: "
            "я задам тебе несколько мягких вопросов, чтобы услышать, с чем ты пришла, "
            "и помочь выбрать формат, который откликнется именно тебе.\n\n"
            "Как мне к тебе обращаться?"
        ),
        "en": (
            "Hello. I'm glad you've stepped into the space of the Know Yourself retreat.\n\n"
            "I'll be your guide in this short conversation. There's no rush: "
            "I'll ask you a few gentle questions to hear what brings you here "
            "and help you choose the format that feels right for you.\n\n"
            "What should I call you?"
        ),
    },
    "not_in_dialog": {
        "ru": "Сейчас мы с тобой не в диалоге. Когда будешь готова — напиши /start.",
        "en": "We're not in a conversation right now. Whenever you're ready, send /start.",
    },
    "cancelled": {
        "ru": (
            "Спасибо, что заглянула. Пространство ретрита никуда не уходит — "
            "напиши /start, когда снова захочешь поговорить."
        ),
        "en": (
            "Thank you for stopping by. The retreat space isn't going anywhere. "
            "Send /start whenever you'd like to talk again."
        ),
    },
    "recommended": {
        "ru": (
            "Рекомендованный формат: {tariff}.\n\n"
            "Дальше тебя встретит {booking} — нажми кнопку ниже, она расскажет про даты, "
            "свободные места и забронирует их для тебя."
        ),
        "en": (
            "Recommended format: {tariff}.\n\n"
            "Next, {booking} will meet you. Tap the button below: she'll tell you about dates "
            "and free places and book one for you."
        ),
    },
    "error": {
        "ru": (
            "Что-то прервалось на моей стороне. Давай попробуем ещё раз — "
            "напиши своё сообщение снова или отправь /cancel."
        ),
        "en": (
            "Something broke on my side. Let's try again: "
            "send your message once more, or send /cancel."
        ),
    },
    "text_only_in_dialog": {
        "ru": "Давай останемся в словах — отправь, пожалуйста, текстовое сообщение.",
        "en": "Let's stay with words. Please send a text message.",
    },
    "start_hint": {
        "ru": "Чтобы начать разговор о ретрите «Познай себя», отправь /start.",
        "en": "To start a conversation about the Know Yourself retreat, send /start.",
    },
    "text_only": {
        "ru": "Я умею разговаривать только текстом. Отправь /start, чтобы начать.",
        "en": "I can only talk in text. Send /start to begin.",
    },
    "name_too_short": {
        "ru": "Пожалуйста, напиши имя хотя бы из двух символов.",
        "en": "Please write a name of at least two characters.",
    },
    "choose_language": {"ru": "Выбери язык разговора:", "en": "Choose the language:"},
    "language_set": {
        "ru": "Хорошо, дальше говорим по-русски 🌿",
        "en": "Great, let's continue in English 🌿",
    },
    "placeholder": {"ru": "Напиши ответ или /cancel", "en": "Type your answer or /cancel"},
    "booking_button": {"ru": "Перейти к {name} для записи", "en": "Continue with {name} to sign up"},
}

TARIFF_LABELS = {
    "ru": {
        "path_to_self": "Путь к Себе (25 000 ₽)",
        "rhythm_of_harmony": "Ритм Гармонии (50 000 ₽)",
        "own_peak": "Своя Вершина (75 000 ₽)",
    },
    "en": {
        "path_to_self": "Path to Self ($390)",
        "rhythm_of_harmony": "Rhythm of Harmony ($1,490)",
        "own_peak": "Your Own Summit ($2,290)",
    },
}

COMMANDS = {
    "ru": [("start", "Начать разговор"), ("cancel", "Завершить разговор"), ("language", "Сменить язык / Change language")],
    "en": [("start", "Start a conversation"), ("cancel", "End the conversation"), ("language", "Change language / Сменить язык")],
}
DESCRIPTION_EN = (
    "The AI guide of the Know Yourself retreat. A short, gentle conversation: "
    "a few reflective questions and a format recommendation that fits your request. "
    "Я говорю и по-русски: /language"
)
SHORT_DESCRIPTION_EN = "AI guide of the Know Yourself retreat: a few gentle questions and a format that fits you."


def t(key: str, lang: str, **kw) -> str:
    text = TEXTS[key].get(lang) or TEXTS[key]["ru"]
    return text.format(**kw) if kw else text
