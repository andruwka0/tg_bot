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
