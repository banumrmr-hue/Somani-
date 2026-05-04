import os 
os.system("pip install motor")
os.system("pip install bson")
import random
import string
import html
import asyncio
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
from bson import ObjectId

# ========= CONFIG =========
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
ADMIN_IDS = [7418454273, 7672413819]
SUPPORT_LINK = "https://t.me/somani_07x"

MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

client = AsyncIOMotorClient(MONGO_URL)
db = client["ig_bot"]

users = db["users"]
store = db["store"]
channels = db["channels"]
redeem_codes = db["redeem_codes"]
claimed_codes = db["claimed_codes"]

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ========= STATES =========
class AdminAddProduct(StatesGroup):
    waiting_for_user = State()
    waiting_for_gmail = State()
    waiting_for_year = State()
    waiting_for_price = State()

class AdminAddChannel(StatesGroup):
    waiting_for_chat_id = State()
    waiting_for_url = State()

class AdminDelChannel(StatesGroup):
    waiting_for_chat_id = State()

class AdminGenCode(StatesGroup):
    waiting_for_points = State()
    waiting_for_uses = State()

class AdminBroadcast(StatesGroup):
    waiting_for_msg = State()

class UserRedeem(StatesGroup):
    waiting_for_code = State()

# ========= MENU =========
def main_menu_kb(user_id):
    kb = [
        [InlineKeyboardButton(text="🛍️ 𝙎𝙏𝙊𝙍𝙀", callback_data="menu_store"),
         InlineKeyboardButton(text="🎁 𝘿𝘼𝙄𝙇𝙔 𝘽𝙊𝙉𝙐𝙎", callback_data="menu_daily")],
        [InlineKeyboardButton(text="🎟️ 𝙍𝙀𝘿𝙀𝙀𝙈", callback_data="menu_redeem"),
         InlineKeyboardButton(text="💳 𝙈𝙔 𝙋𝙊𝙄𝙉𝙏𝙎", callback_data="menu_points")],
        [InlineKeyboardButton(text="🔗 𝙍𝙀𝙁𝙀𝙍", callback_data="menu_refer"),
         InlineKeyboardButton(text="📞 𝙎𝙐𝙋𝙋𝙊𝙍𝙏", url=SUPPORT_LINK)]
    ]

    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="👑 ——— 𝘼𝘿𝙈𝙄𝙉 𝘾𝙊𝙉𝙏𝙍𝙊𝙇𝙎 ——— 👑", callback_data="ignore")])
        kb.append([
            InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘼𝘾𝘾𝙊𝙐𝙉𝙏", callback_data="admin_add"),
            InlineKeyboardButton(text="🎟️ 𝙂𝙀𝙉 𝘾𝙊𝘿𝙀", callback_data="admin_gen")
        ])
        kb.append([
            InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘾𝙃𝘼𝙉𝙉𝙀𝙇", callback_data="admin_addch"),
            InlineKeyboardButton(text="➖ 𝘿𝙀𝙇𝙀𝙏𝙀 𝘾𝙃𝘼𝙉𝙉𝙀𝙇", callback_data="admin_delch")
        ])
        kb.append([
            InlineKeyboardButton(text="📢 𝘽𝙍𝙊𝘼𝘿𝘾𝘼𝙎𝙏", callback_data="admin_cast"),
            InlineKeyboardButton(text="📊 𝙎𝙏𝘼𝙏𝙎", callback_data="admin_stats")
        ])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ========= START =========
@dp.message(CommandStart())
async def start(message: Message):
    user = await users.find_one({"user_id": message.from_user.id})
    if not user:
        await users.insert_one({"user_id": message.from_user.id, "points": 2, "last_bonus": None})

    user = await users.find_one({"user_id": message.from_user.id})

    await message.reply(
        f"<b>WELCOME</b>\nBalance: {user['points']} 🪙",
        reply_markup=main_menu_kb(message.from_user.id)
    )

# ========= MENU =========
@dp.callback_query(F.data.startswith("menu_"))
async def menu(call: CallbackQuery, state: FSMContext):
    user = await users.find_one({"user_id": call.from_user.id})
    action = call.data.split("_")[1]

    if action == "store":
        kb = []
        async for item in store.find():
            kb.append([InlineKeyboardButton(
                text=f"👤 {item['username']} [Yr:{item['year']}] - {item['price']} 🪙",
                callback_data=f"buy_{item['_id']}"
            )])
        kb.append([InlineKeyboardButton(text="🔙 BACK", callback_data="back")])
        await call.message.edit_text("🛍️ STORE", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    elif action == "daily":
        now = datetime.now()
        if user.get("last_bonus") and now < user["last_bonus"] + timedelta(hours=24):
            await call.answer("Come later", show_alert=True)
            return

        await users.update_one({"user_id": call.from_user.id},
                               {"$set": {"last_bonus": now}, "$inc": {"points": 2}})
        await call.message.edit_text("🎁 BONUS CLAIMED", reply_markup=main_menu_kb(call.from_user.id))

    elif action == "points":
        await call.answer(f"{user['points']} 🪙", show_alert=True)

    elif action == "refer":
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={call.from_user.id}"
        await call.message.edit_text(link, reply_markup=main_menu_kb(call.from_user.id))

    elif action == "redeem":
        await state.set_state(UserRedeem.waiting_for_code)
        await call.message.edit_text("Send code")

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
        f"✅ PURCHASE SUCCESS\n\n👤 {item['username']}\n📧 {item['gmail']}",
        reply_markup=main_menu_kb(call.from_user.id)
    )

# ========= ADMIN =========
@dp.callback_query(F.data.startswith("admin_"))
async def admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    action = call.data.split("_")[1]

    if action == "add":
        await state.set_state(AdminAddProduct.waiting_for_user)
        await call.message.edit_text("Send username")

    elif action == "gen":
        await state.set_state(AdminGenCode.waiting_for_points)
        await call.message.edit_text("Send points")

    elif action == "addch":
        await state.set_state(AdminAddChannel.waiting_for_chat_id)
        await call.message.edit_text("Send chat id")

    elif action == "delch":
        await state.set_state(AdminDelChannel.waiting_for_chat_id)
        await call.message.edit_text("Send chat id to delete")

    elif action == "cast":
        await state.set_state(AdminBroadcast.waiting_for_msg)
        await call.message.edit_text("Send broadcast")

    elif action == "stats":
        u = await users.count_documents({})
        s = await store.count_documents({})
        await call.message.edit_text(f"Users: {u}\nStore: {s}",
                                     reply_markup=main_menu_kb(call.from_user.id))

# ========= ADD PRODUCT =========
@dp.message(AdminAddProduct.waiting_for_user)
async def add1(m: Message, s: FSMContext):
    await s.update_data(username=m.text)
    await s.set_state(AdminAddProduct.waiting_for_gmail)
    await m.reply("Send Gmail")

@dp.message(AdminAddProduct.waiting_for_gmail)
async def add2(m: Message, s: FSMContext):
    await s.update_data(gmail=m.text)
    await s.set_state(AdminAddProduct.waiting_for_year)
    await m.reply("Send Year")

@dp.message(AdminAddProduct.waiting_for_year)
async def add3(m: Message, s: FSMContext):
    await s.update_data(year=m.text)
    await s.set_state(AdminAddProduct.waiting_for_price)
    await m.reply("Send Price")

@dp.message(AdminAddProduct.waiting_for_price)
async def add4(m: Message, s: FSMContext):
    data = await s.get_data()
    await store.insert_one({
        "username": data["username"],
        "gmail": data["gmail"],
        "year": data["year"],
        "price": int(m.text)
    })
    await m.reply("✅ ADDED", reply_markup=main_menu_kb(m.from_user.id))
    await s.clear()

# ========= RUN =========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
