import os 
os.system("pip install motor")
os.system("pip install bson")
import asyncio
import random
import string
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# ========= CONFIG =========
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
ADMIN_IDS = [7418454273, 7672413819]

MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

client = AsyncIOMotorClient(MONGO_URL)
db = client["ig_bot"]

users = db["users"]
store = db["store"]
channels = db["channels"]
redeem_codes = db["redeem_codes"]
claimed_codes = db["claimed_codes"]

bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========= STATES =========
class AddProduct(StatesGroup):
    user = State()
    gmail = State()
    year = State()
    price = State()

class AddChannel(StatesGroup):
    chat_id = State()
    url = State()

class GenCode(StatesGroup):
    points = State()
    uses = State()

class Redeem(StatesGroup):
    code = State()

# ========= MENU =========
def menu(uid):
    kb = [
        [InlineKeyboardButton(text="🛍️ STORE", callback_data="store")],
        [InlineKeyboardButton(text="🎁 BONUS", callback_data="bonus")],
        [InlineKeyboardButton(text="🎟️ REDEEM", callback_data="redeem")],
        [InlineKeyboardButton(text="💳 POINTS", callback_data="points")]
    ]

    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="👑 ADMIN PANEL", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ========= START =========
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    uid = m.from_user.id

    user = await users.find_one({"user_id": uid})
    if not user:
        await users.insert_one({"user_id": uid, "points": 5, "last_bonus": None})

    user = await users.find_one({"user_id": uid})

    await m.reply(f"Welcome!\nBalance: {user['points']} 🪙", reply_markup=menu(uid))

# ========= STORE =========
@dp.callback_query(F.data == "store")
async def store_menu(call: CallbackQuery):
    kb = []

    async for item in store.find():
        kb.append([InlineKeyboardButton(
            text=f"{item['username']} ({item['year']}) - {item['price']}",
            callback_data=f"buy_{item['_id']}"
        )])

    if not kb:
        await call.answer("Store empty", show_alert=True)
        return

    await call.message.edit_text("STORE:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========= BUY =========
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    item = await store.find_one({"_id": ObjectId(call.data.split("_")[1])})
    user = await users.find_one({"user_id": call.from_user.id})

    if not item:
        await call.answer("Sold", show_alert=True)
        return

    if user["points"] < item["price"]:
        await call.answer("Not enough points", show_alert=True)
        return

    await users.update_one({"user_id": call.from_user.id}, {"$inc": {"points": -item["price"]}})
    await store.delete_one({"_id": item["_id"]})

    await call.message.edit_text(
        f"✅ Purchased\n\n👤 {item['username']}\n📧 {item['gmail']}",
        reply_markup=menu(call.from_user.id)
    )

# ========= BONUS =========
@dp.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    user = await users.find_one({"user_id": call.from_user.id})
    now = datetime.now()

    if user.get("last_bonus") and now < user["last_bonus"] + timedelta(hours=24):
        await call.answer("Come later", show_alert=True)
        return

    await users.update_one({"user_id": call.from_user.id},
                           {"$set": {"last_bonus": now}, "$inc": {"points": 2}})

    await call.answer("Bonus claimed!", show_alert=True)

# ========= POINTS =========
@dp.callback_query(F.data == "points")
async def points(call: CallbackQuery):
    user = await users.find_one({"user_id": call.from_user.id})
    await call.answer(f"{user['points']} 🪙", show_alert=True)

# ========= REDEEM =========
@dp.callback_query(F.data == "redeem")
async def redeem_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(Redeem.code)
    await call.message.edit_text("Send code")

@dp.message(Redeem.code)
async def redeem_code(m: Message, state: FSMContext):
    code = await redeem_codes.find_one({"code": m.text})

    if not code or code["uses_left"] <= 0:
        await m.reply("Invalid")
        return

    used = await claimed_codes.find_one({"user_id": m.from_user.id, "code": m.text})
    if used:
        await m.reply("Already used")
        return

    await redeem_codes.update_one({"code": m.text}, {"$inc": {"uses_left": -1}})
    await claimed_codes.insert_one({"user_id": m.from_user.id, "code": m.text})
    await users.update_one({"user_id": m.from_user.id}, {"$inc": {"points": code["points"]}})

    await m.reply("Redeemed!")
    await state.clear()

# ========= ADMIN =========
@dp.callback_query(F.data == "admin")
async def admin_panel(call: CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="➕ ADD ACCOUNT", callback_data="add_acc")],
        [InlineKeyboardButton(text="➕ ADD CHANNEL", callback_data="add_ch")],
        [InlineKeyboardButton(text="🎟️ GEN CODE", callback_data="gen_code")]
    ]
    await call.message.edit_text("ADMIN PANEL", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========= ADD ACCOUNT =========
@dp.callback_query(F.data == "add_acc")
async def add_acc(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddProduct.user)
    await call.message.edit_text("Send username")

@dp.message(AddProduct.user)
async def a1(m: Message, s: FSMContext):
    await s.update_data(username=m.text)
    await s.set_state(AddProduct.gmail)
    await m.reply("Send gmail")

@dp.message(AddProduct.gmail)
async def a2(m: Message, s: FSMContext):
    await s.update_data(gmail=m.text)
    await s.set_state(AddProduct.year)
    await m.reply("Send year")

@dp.message(AddProduct.year)
async def a3(m: Message, s: FSMContext):
    await s.update_data(year=m.text)
    await s.set_state(AddProduct.price)
    await m.reply("Send price")

@dp.message(AddProduct.price)
async def a4(m: Message, s: FSMContext):
    d = await s.get_data()
    await store.insert_one({
        "username": d["username"],
        "gmail": d["gmail"],
        "year": d["year"],
        "price": int(m.text)
    })
    await m.reply("Added!")
    await s.clear()

# ========= ADD CHANNEL =========
@dp.callback_query(F.data == "add_ch")
async def add_ch(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.chat_id)
    await call.message.edit_text("Send chat id")

@dp.message(AddChannel.chat_id)
async def ch1(m: Message, s: FSMContext):
    await s.update_data(chat_id=m.text)
    await s.set_state(AddChannel.url)
    await m.reply("Send URL")

@dp.message(AddChannel.url)
async def ch2(m: Message, s: FSMContext):
    d = await s.get_data()
    await channels.insert_one({"chat_id": d["chat_id"], "url": m.text})
    await m.reply("Channel added")
    await s.clear()

# ========= GEN CODE =========
@dp.callback_query(F.data == "gen_code")
async def gen_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(GenCode.points)
    await call.message.edit_text("Send points")

@dp.message(GenCode.points)
async def g1(m: Message, s: FSMContext):
    await s.update_data(points=int(m.text))
    await s.set_state(GenCode.uses)
    await m.reply("Send uses")

@dp.message(GenCode.uses)
async def g2(m: Message, s: FSMContext):
    d = await s.get_data()
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    await redeem_codes.insert_one({
        "code": code,
        "points": d["points"],
        "uses_left": int(m.text)
    })

    await m.reply(f"Code: {code}")
    await s.clear()

# ========= RUN =========
async def main():
    print("BOT RUNNING...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
