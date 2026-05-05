import random
import string
import asyncio
import os
from datetime import datetime, timedelta

import psycopg2
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# CONFIG
API_TOKEN = os.getenv("8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY")
ADMIN_IDS = [7418454273,7672413819]

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# DATABASE
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
c = conn.cursor()

# TABLES
c.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, points INT DEFAULT 2, last_bonus TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS store (id SERIAL PRIMARY KEY, username TEXT, gmail TEXT, year TEXT, price INT)")
c.execute("CREATE TABLE IF NOT EXISTS redeem_codes (code TEXT PRIMARY KEY, points INT, uses_left INT)")
c.execute("CREATE TABLE IF NOT EXISTS claimed_codes (user_id BIGINT, code TEXT, PRIMARY KEY(user_id, code))")

# STATES
class AddItem(StatesGroup):
    user = State()
    gmail = State()
    year = State()
    price = State()

class Redeem(StatesGroup):
    code = State()

# START
@dp.message(CommandStart())
async def start(msg: Message):
    uid = msg.from_user.id

    c.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id) VALUES (%s)", (uid,))

    c.execute("SELECT points FROM users WHERE user_id=%s", (uid,))
    bal = c.fetchone()[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="STORE", callback_data="store")],
        [InlineKeyboardButton(text="REDEEM", callback_data="redeem")]
    ])

    await msg.reply(f"Balance: {bal}", reply_markup=kb)

# STORE
@dp.callback_query(F.data == "store")
async def store(call: CallbackQuery):
    c.execute("SELECT id, username, price FROM store")
    items = c.fetchall()

    if not items:
        await call.answer("Empty", show_alert=True)
        return

    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(text=f"{i[1]} - {i[2]}", callback_data=f"buy_{i[0]}")])

    await call.message.edit_text("Store:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# BUY
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    uid = call.from_user.id
    item_id = int(call.data.split("_")[1])

    c.execute("SELECT points FROM users WHERE user_id=%s", (uid,))
    bal = c.fetchone()[0]

    c.execute("SELECT username, gmail, year, price FROM store WHERE id=%s", (item_id,))
    item = c.fetchone()

    if not item:
        await call.answer("Sold", show_alert=True)
        return

    if bal < item[3]:
        await call.answer("Not enough points", show_alert=True)
        return

    c.execute("UPDATE users SET points = points - %s WHERE user_id=%s", (item[3], uid))
    c.execute("DELETE FROM store WHERE id=%s", (item_id,))

    await call.message.edit_text(f"Bought:\n{item[0]}\n{item[1]}\n{item[2]}")

# REDEEM BUTTON
@dp.callback_query(F.data == "redeem")
async def redeem_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(Redeem.code)
    await call.message.edit_text("Send code")

# ✅ FIXED REDEEM
@dp.message(Redeem.code)
async def redeem_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    uid = msg.from_user.id

    c.execute("SELECT points, uses_left FROM redeem_codes WHERE code=%s", (code,))
    res = c.fetchone()

    if not res:
        await msg.reply("Invalid code")
        await state.clear()
        return

    pts, uses = res

    if uses <= 0:
        await msg.reply("Expired")
        await state.clear()
        return

    c.execute("SELECT 1 FROM claimed_codes WHERE user_id=%s AND code=%s", (uid, code))
    if c.fetchone():
        await msg.reply("Already used")
        await state.clear()
        return

    c.execute("UPDATE redeem_codes SET uses_left = uses_left - 1 WHERE code=%s", (code,))
    c.execute("INSERT INTO claimed_codes (user_id, code) VALUES (%s, %s)", (uid, code))
    c.execute("UPDATE users SET points = points + %s WHERE user_id=%s", (pts, uid))

    await msg.reply(f"+{pts} points")
    await state.clear()

# RUN
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
