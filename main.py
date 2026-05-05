import random
import string
import html
import asyncio
import os
from datetime import datetime, timedelta

import psycopg2
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_TOKEN = '8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY'  # ⚠️ BotFather se naya token lo
ADMIN_IDS = [7418454273, 7672413819]
SUPPORT_LINK = 'https://t.me/somani_07x'

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ==========================================
# 🗄️ DATABASE (PostgreSQL)
# ==========================================
DATABASE_URL = os.getenv("postgresql://bot_db_1qks_user:wNPMfVFaWMnlXvNtGgQcqikeFp2z8akp@dpg-d7srll6gvqtc739vtvjg-a/bot_db_1qks")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True  # commits auto
c = conn.cursor()

# Tables (PostgreSQL syntax)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    points INTEGER DEFAULT 2,
    last_bonus TIMESTAMP
);
''')

c.execute('''
CREATE TABLE IF NOT EXISTS store (
    id SERIAL PRIMARY KEY,
    username TEXT,
    gmail TEXT,
    year TEXT,
    price INTEGER
);
''')

c.execute('''
CREATE TABLE IF NOT EXISTS channels (
    chat_id TEXT PRIMARY KEY,
    url TEXT
);
''')

c.execute('''
CREATE TABLE IF NOT EXISTS redeem_codes (
    code TEXT PRIMARY KEY,
    points INTEGER,
    uses_left INTEGER
);
''')

c.execute('''
CREATE TABLE IF NOT EXISTS claimed_codes (
    user_id BIGINT,
    code TEXT,
    PRIMARY KEY (user_id, code)
);
''')

# ==========================================
# 🧠 STATES
# ==========================================
class AdminAddProduct(StatesGroup):
    waiting_for_user = State()
    waiting_for_gmail = State()
    waiting_for_year = State()
    waiting_for_price = State()

class UserRedeem(StatesGroup):
    waiting_for_code = State()

# ==========================================
# 🛡️ KEYBOARD
# ==========================================
def main_menu_kb(user_id: int):
    kb = [
        [InlineKeyboardButton(text="🛍️ STORE", callback_data="menu_store"),
         InlineKeyboardButton(text="🎁 BONUS", callback_data="menu_daily")],
        [InlineKeyboardButton(text="🎟️ REDEEM", callback_data="menu_redeem"),
         InlineKeyboardButton(text="💳 POINTS", callback_data="menu_points")]
    ]

    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="➕ ADD ITEM", callback_data="admin_add")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==========================================
# 🚀 START
# ==========================================
@dp.message(CommandStart())
async def start(message: Message, command: CommandObject):
    user_id = message.from_user.id

    c.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = c.fetchone()

    if not user:
        c.execute("INSERT INTO users (user_id, points) VALUES (%s, %s)", (user_id, 2))

    c.execute("SELECT points FROM users WHERE user_id=%s", (user_id,))
    bal = c.fetchone()[0]

    await message.reply(f"Welcome! Balance: {bal} 🪙", reply_markup=main_menu_kb(user_id))

# ==========================================
# 👤 USER MENU
# ==========================================
@dp.callback_query(F.data.startswith("menu_"))
async def menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    action = call.data.split("_")[1]

    if action == "points":
        c.execute("SELECT points FROM users WHERE user_id=%s", (user_id,))
        bal = c.fetchone()[0]
        await call.answer(f"{bal} 🪙", show_alert=True)

    elif action == "store":
        c.execute("SELECT id, username, year, price FROM store")
        items = c.fetchall()

        if not items:
            await call.answer("Store empty", show_alert=True)
            return

        kb = []
        for i in items:
            kb.append([InlineKeyboardButton(
                text=f"{i[1]} ({i[2]}) - {i[3]}",
                callback_data=f"buy_{i[0]}"
            )])

        await call.message.edit_text("Select item:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    elif action == "daily":
        now = datetime.now()
        c.execute("SELECT points, last_bonus FROM users WHERE user_id=%s", (user_id,))
        pts, last = c.fetchone()

        if last:
            last = last
            if now < last + timedelta(hours=24):
                await call.answer("Come later", show_alert=True)
                return

        c.execute("UPDATE users SET points=%s, last_bonus=%s WHERE user_id=%s",
                  (pts+2, now, user_id))
        await call.message.edit_text(f"+2 bonus! Total: {pts+2}")

    @dp.message(UserRedeem.waiting_for_code)
async def redeem(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id

    c.execute("SELECT points, uses_left FROM redeem_codes WHERE code=%s", (code,))
    res = c.fetchone()

    if not res:
        await message.reply("❌ Invalid code")
        await state.clear()
        return

    pts, uses = res

    if uses <= 0:
        await message.reply("❌ Code expired")
        await state.clear()
        return

    c.execute("SELECT 1 FROM claimed_codes WHERE user_id=%s AND code=%s", (user_id, code))
    if c.fetchone():
        await message.reply("❌ Already claimed")
        await state.clear()
        return

    c.execute("UPDATE redeem_codes SET uses_left = uses_left - 1 WHERE code=%s", (code,))
    c.execute("INSERT INTO claimed_codes (user_id, code) VALUES (%s, %s)", (user_id, code))
    c.execute("UPDATE users SET points = points + %s WHERE user_id=%s", (pts, user_id))

    await message.reply(f"✅ Redeemed! +{pts} 🪙")
    await state.clear()

# ==========================================
# 🛒 BUY
# ==========================================
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    user_id = call.from_user.id
    item_id = int(call.data.split("_")[1])

    c.execute("SELECT points FROM users WHERE user_id=%s", (user_id,))
    bal = c.fetchone()[0]

    c.execute("SELECT username, gmail, year, price FROM store WHERE id=%s", (item_id,))
    item = c.fetchone()

    if not item:
        await call.answer("Sold!", show_alert=True)
        return

    username, gmail, year, price = item

    if bal < price:
        await call.answer("Not enough points", show_alert=True)
        return

    c.execute("UPDATE users SET points = points - %s WHERE user_id=%s", (price, user_id))
    c.execute("DELETE FROM store WHERE id=%s", (item_id,))

    await call.message.edit_text(
        f"Bought!\n{username}\n{gmail}\n{year}",
        reply_markup=main_menu_kb(user_id)
    )

# ==========================================
# 🎟️ REDEEM
# ==========================================
@dp.message(UserRedeem.waiting_for_code)
async def redeem(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    c.execute("SELECT points, uses_left FROM redeem_codes WHERE code=%s", (code,))
    res = c.fetchone()

    if not res or res[1] <= 0:
        await message.reply("Invalid")
        await state.clear()
        return

    pts, uses = res

    c.execute("UPDATE redeem_codes SET uses_left = uses_left - 1 WHERE code=%s", (code,))
    c.execute("UPDATE users SET points = points + %s WHERE user_id=%s", (pts, user_id))

    await message.reply(f"+{pts} 🪙")
    await state.clear()

# ==========================================
# 👑 ADMIN ADD ITEM
# ==========================================
@dp.callback_query(F.data == "admin_add")
async def admin_add(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminAddProduct.waiting_for_user)
    await call.message.edit_text("Username:")

@dp.message(AdminAddProduct.waiting_for_user)
async def add_user(message: Message, state: FSMContext):
    await state.update_data(username=message.text)
    await state.set_state(AdminAddProduct.waiting_for_gmail)
    await message.reply("Gmail:")

@dp.message(AdminAddProduct.waiting_for_gmail)
async def add_gmail(message: Message, state: FSMContext):
    await state.update_data(gmail=message.text)
    await state.set_state(AdminAddProduct.waiting_for_year)
    await message.reply("Year:")

@dp.message(AdminAddProduct.waiting_for_year)
async def add_year(message: Message, state: FSMContext):
    await state.update_data(year=message.text)
    await state.set_state(AdminAddProduct.waiting_for_price)
    await message.reply("Price:")

@dp.message(AdminAddProduct.waiting_for_price)
async def add_price(message: Message, state: FSMContext):
    data = await state.get_data()

    c.execute(
        "INSERT INTO store (username, gmail, year, price) VALUES (%s, %s, %s, %s)",
        (data['username'], data['gmail'], data['year'], int(message.text))
    )

    await message.reply("Added!", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

# ==========================================
# 🚀 RUN
# ==========================================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
