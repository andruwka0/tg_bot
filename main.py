import sqlite3
import asyncio
import time
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import json
import random

TOKEN = "MY_TOKEN"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Подключение к базе данных
conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute(
    '''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, name TEXT, category TEXT, level TEXT)''')
conn.commit()

# Основные клавиатуры
main_keyboard = InlineKeyboardMarkup()
main_keyboard.add(InlineKeyboardButton("Сгенерировать текст", callback_data="generate_text"))
main_keyboard.add(InlineKeyboardButton("Провести практику по словам", callback_data="practice_words"))

category_keyboard = InlineKeyboardMarkup(row_width=1)
category_keyboard.add(InlineKeyboardButton("Медицина", callback_data="category_medicine"))
category_keyboard.add(InlineKeyboardButton("Бизнес", callback_data="category_business"))
category_keyboard.add(InlineKeyboardButton("Общее", callback_data="category_general"))

level_keyboard = InlineKeyboardMarkup(row_width=2)
level_keyboard.add(InlineKeyboardButton("B1", callback_data="level_B1"),
                   InlineKeyboardButton("B2", callback_data="level_B2"))
level_keyboard.add(InlineKeyboardButton("C1", callback_data="level_C1"),
                   InlineKeyboardButton("C2", callback_data="level_C2"))


class UserState(StatesGroup):
    waiting_for_name = State()


async def add_user(user_id):
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()


def get_user_name(user_id):
    c.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result and result[0] else None


def get_user_category(user_id):
    c.execute("SELECT category FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result and result[0] else "general"


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = get_user_name(user_id)
    if name:
        await message.answer(f"Привет, {name}!", reply_markup=main_keyboard)
    else:
        await add_user(user_id)
        sent_message = await message.answer("Привет! Как тебя называть?")
        await state.update_data(last_message_id=sent_message.message_id)
        await UserState.waiting_for_name.set()


@dp.message_handler(state=UserState.waiting_for_name)
async def set_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    c.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    await message.delete()
    await message.answer(f"Отлично! Привет, {name}!", reply_markup=main_keyboard)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data in ["generate_text", "practice_words"])
async def handle_buttons(callback_query: CallbackQuery, state: FSMContext):
    if callback_query.data == "generate_text":
        new_text = "Выберите тему текста"
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=new_text, reply_markup=category_keyboard)
        await bot.answer_callback_query(callback_query.id)
    else:
        new_text = "Практика пока не реализована)))"



@dp.callback_query_handler(lambda c: c.data.startswith("category_"))
async def select_category(callback_query: CallbackQuery, state: FSMContext):
    category = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    c.execute("UPDATE users SET category = ? WHERE user_id = ?", (category, user_id))
    conn.commit()
    await state.update_data(category=category)
    await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id,
                                text=f"Вы выбрали категорию: {category.capitalize()}! Теперь выберите уровень.",
                                reply_markup=level_keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith("level_"))
async def select_level(callback_query: CallbackQuery, state: FSMContext):
    level = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    c.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    user_data = await state.get_data()
    category = user_data.get("category", get_user_category(user_id))
    print(category)
    folder_id = 'b1gug7c74crq38i2spt2'
    api_key = 'AQVN2VdnEpiYARjmZXK4bO4GYyeeIdPqcNba3pGY'
    gpt_model = "yandexgpt-lite"

    if category == 'business':
        with open('terms.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        random_terms = random.sample(data["terms"], 15)
    elif category == 'medicine':
        with open('med.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        random_terms = random.sample(data["terms"], 15)
    else:
        print(12)
        with open('baza.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
        random_terms = random.sample(data['terms'], 15)

    final = [term['en'] for term in random_terms]
    system_prompt = f"Ты должен составить текст на английском языке на уровне {level} по теме {category}" \
                    f" по данным словам. Текст длинной 8 предложений. Текст длинной не более 150 слов."
    user_prompt = ' '.join(final)
    body = {
        'modelUri': f'gpt://{folder_id}/{gpt_model}',
        'completionOptions': {'stream': False, 'temperature': 0.3, 'maxTokens': 2000},
        'messages': [
            {'role': 'system', 'text': system_prompt},
            {'role': 'user', 'text': user_prompt},
        ],
    }
    url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completionAsync'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Api-Key {api_key}'
    }
    response = requests.post(url, headers=headers, json=body)
    operation_id = response.json().get('id')
    url = f"https://llm.api.cloud.yandex.net:443/operations/{operation_id}"
    while True:
        response = requests.get(url, headers=headers)
        if response.json()["done"]:
            break
        time.sleep(2)
    data = response.json()
    answer = data['response']['alternatives'][0]['message']['text']
    await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id,
                                text=f"{answer}\n\nИспользовались слова:\n{' '.join(final)}",
                                reply_markup=main_keyboard)
    await state.finish()


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
