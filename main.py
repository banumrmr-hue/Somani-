import os 
os.system("pip install motor")
os.system("pip install bson")
import asyncio
import random
import string
import html
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from motor.motor_asyncio import AsyncIOMotorClient

# ================= CONFIG =================
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

ADMIN_IDS = [7418454273, 7672413819]
SUPPORT_LINK = "https://t.me/somani_07x"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ================= MONGO =================
client = AsyncIOMotorClient(MONGO_URL)
db = client["telegram_bot"]

users = db["users"]
store = db["store"]
channels = db["channels"]
redeem_codes = db["redeem_codes"]
claimed_codes = db["claimed_codes"]

# ================= STATES =================
class AdminAddProduct(StatesGroup):
    user = State()
    gmail = State()
    year = State()
    price = State()

class AdminAddChannel(StatesGroup):
    chat_id = State()
    url = State()

class AdminDelChannel(StatesGroup):
    chat_id = State()

class AdminGenCode(StatesGroup):
    points = State()
    uses = State()

class AdminBroadcast(StatesGroup):
    msg = State()

class UserRedeem(StatesGroup):
    code = State()

# ================= KEYBOARD =================
def main_kb(uid):
    kb = [
        [InlineKeyboardButton(text="🛍️ STORE", callback_data="store"),
         InlineKeyboardButton(text="🎁 DAILY", callback_data="daily")],
        [InlineKeyboardButton(text="🎟️ REDEEM", callback_data="redeem"),
         InlineKeyboardButton(text="💳 POINTS", callback_data="points")],
        [InlineKeyboardButton(text="🔗 REFER", callback_data="refer"),
         InlineKeyboardButton(text="📞 SUPPORT", url=SUPPORT_LINK)]
    ]

    if uid in ADMIN_IDS:
        kb += [
            [InlineKeyboardButton(text="👑 ADMIN", callback_data="ignore")],
            [InlineKeyboardButton(text="➕ ADD ACC", callback_data="add"),
             InlineKeyboardButton(text="🎟️ GEN CODE", callback_data="gen")],
            [InlineKeyboardButton(text="➕ ADD CH", callback_data="addch"),
             InlineKeyboardButton(text="➖ DEL CH", callback_data="delch")],
            [InlineKeyboardButton(text="📢 BROADCAST", callback_data="bc"),
             InlineKeyboardButton(text="📊 STATS", callback_data="stats")]
        ]

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id

    if not await users.find_one({"user_id": uid}):
        await users.insert_one({
            "user_id": uid,
            "points": 2,
            "last_bonus": None
        })

    u = await users.find_one({"user_id": uid})

    await m.answer(f"Welcome!\nPoints: {u['points']}", reply_markup=main_kb(uid))

# ================= USER =================
@dp.callback_query(F.data == "points")
async def points(c: CallbackQuery):
    u = await users.find_one({"user_id": c.from_user.id})
    await c.answer(f"{u['points']} points", show_alert=True)

@dp.callback_query(F.data == "daily")
async def daily(c: CallbackQuery):
    uid = c.from_user.id
    u = await users.find_one({"user_id": uid})
    now = datetime.now()

    if u["last_bonus"]:
        if now < u["last_bonus"] + timedelta(hours=24):
            await c.answer("Come later", show_alert=True)
            return

    await users.update_one({"user_id": uid}, {"$set": {"last_bonus": now}, "$inc": {"points": 2}})
    await c.message.edit_text("Daily claimed", reply_markup=main_kb(uid))

# ================= STORE =================
@dp.callback_query(F.data == "store")
async def store_view(c: CallbackQuery):
    items = []
    async for i in store.find():
        items.append(i)

    if not items:
        await c.answer("Empty", show_alert=True)
        return

    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(
            text=f"{i['username']} [{i['year']}] - {i['price']}",
            callback_data=f"buy_{str(i['_id'])}"
        )])

    await c.message.edit_text("Store:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_"))
async def buy(c: CallbackQuery):
    uid = c.from_user.id
    item_id = c.data.split("_")[1]

    item = await store.find_one({"_id": item_id})
    u = await users.find_one({"user_id": uid})

    if not item:
        await c.answer("Sold", show_alert=True)
        return

    if u["points"] < item["price"]:
        await c.answer("No points", show_alert=True)
        return

    await users.update_one({"user_id": uid}, {"$inc": {"points": -item["price"]}})
    await store.delete_one({"_id": item_id})

    await c.message.edit_text(f"Bought:\n{item['username']}")

# ================= ADMIN =================
@dp.callback_query(F.data == "add")
async def add(c: CallbackQuery, state: FSMContext):
    await state.set_state(AdminAddProduct.user)
    await c.message.edit_text("Username?")

@dp.message(AdminAddProduct.user)
async def add1(m: Message, state: FSMContext):
    await state.update_data(user=m.text)
    await state.set_state(AdminAddProduct.gmail)
    await m.answer("Gmail?")

@dp.message(AdminAddProduct.gmail)
async def add2(m: Message, state: FSMContext):
    await state.update_data(gmail=m.text)
    await state.set_state(AdminAddProduct.year)
    await m.answer("Year?")

@dp.message(AdminAddProduct.year)
async def add3(m: Message, state: FSMContext):
    await state.update_data(year=m.text)
    await state.set_state(AdminAddProduct.price)
    await m.answer("Price?")

@dp.message(AdminAddProduct.price)
async def add4(m: Message, state: FSMContext):
    d = await state.get_data()

    await store.insert_one({
        "username": d["user"],
        "gmail": d["gmail"],
        "year": d["year"],
        "price": int(m.text)
    })

    await m.answer("Added", reply_markup=main_kb(m.from_user.id))
    await state.clear()

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

        
