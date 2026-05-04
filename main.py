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
from bson import ObjectId

# ================= CONFIG =================
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

ADMIN_IDS = [7418454273, 7672413819]
SUPPORT_LINK = "https://t.me/somani_07x"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ================= DB =================
client = AsyncIOMotorClient(MONGO_URL)
db = client["bot_db"]

users = db.users
store = db.store
channels = db.channels
redeem_codes = db.redeem_codes
claimed_codes = db.claimed_codes

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
        [InlineKeyboardButton(text="🛍️ STORE", callback_data="menu_store"),
         InlineKeyboardButton(text="🎁 DAILY", callback_data="menu_daily")],
        [InlineKeyboardButton(text="🎟️ REDEEM", callback_data="menu_redeem"),
         InlineKeyboardButton(text="💳 POINTS", callback_data="menu_points")],
        [InlineKeyboardButton(text="🔗 REFER", callback_data="menu_refer"),
         InlineKeyboardButton(text="📞 SUPPORT", url=SUPPORT_LINK)]
    ]

    if uid in ADMIN_IDS:
        kb += [
            [InlineKeyboardButton(text="👑 ADMIN", callback_data="ignore")],
            [InlineKeyboardButton(text="➕ ADD ACC", callback_data="admin_add"),
             InlineKeyboardButton(text="🎟️ GEN CODE", callback_data="admin_gen")],
            [InlineKeyboardButton(text="➕ ADD CH", callback_data="admin_addch"),
             InlineKeyboardButton(text="➖ DEL CH", callback_data="admin_delch")],
            [InlineKeyboardButton(text="📢 BROADCAST", callback_data="admin_cast"),
             InlineKeyboardButton(text="📊 STATS", callback_data="admin_stats")]
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

    user = await users.find_one({"user_id": uid})
    await m.answer(f"<b>Welcome</b>\nPoints: {user['points']}", reply_markup=main_kb(uid))

# ================= MENU =================
@dp.callback_query(F.data.startswith("menu_"))
async def menu(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    action = call.data.split("_")[1]

    if action == "points":
        user = await users.find_one({"user_id": uid})
        await call.answer(f"{user['points']} 🪙", show_alert=True)

    elif action == "daily":
        user = await users.find_one({"user_id": uid})
        now = datetime.now()

        if user.get("last_bonus"):
            if now < user["last_bonus"] + timedelta(hours=24):
                await call.answer("Wait 24h", show_alert=True)
                return

        await users.update_one({"user_id": uid},
            {"$set": {"last_bonus": now}, "$inc": {"points": 2}})

        await call.message.edit_text("🎁 Bonus Claimed", reply_markup=main_kb(uid))

    elif action == "store":
        items = []
        async for i in store.find():
            items.append(i)

        if not items:
            await call.answer("Store empty", show_alert=True)
            return

        kb = []
        for i in items:
            kb.append([InlineKeyboardButton(
                text=f"{i['username']} [{i['year']}] - {i['price']}",
                callback_data=f"buy_{str(i['_id'])}"
            )])

        await call.message.edit_text("🛍️ Store", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    elif action == "refer":
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={uid}"
        await call.message.edit_text(link, reply_markup=main_kb(uid))

    elif action == "redeem":
        await state.set_state(UserRedeem.code)
        await call.message.edit_text("Send code")

# ================= BUY =================
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    uid = call.from_user.id
    item_id = call.data.split("_")[1]

    item = await store.find_one({"_id": ObjectId(item_id)})
    user = await users.find_one({"user_id": uid})

    if not item:
        await call.answer("Sold", show_alert=True)
        return

    if user["points"] < item["price"]:
        await call.answer("Not enough points", show_alert=True)
        return

    await users.update_one({"user_id": uid}, {"$inc": {"points": -item["price"]}})
    await store.delete_one({"_id": ObjectId(item_id)})

    await call.message.edit_text("✅ Purchased", reply_markup=main_kb(uid))

# ================= ADMIN =================
@dp.callback_query(F.data.startswith("admin_"))
async def admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    action = call.data.split("_")[1]

    if action == "stats":
        u = await users.count_documents({})
        s = await store.count_documents({})
        await call.message.edit_text(f"Users: {u}\nItems: {s}", reply_markup=main_kb(call.from_user.id))

    elif action == "add":
        await state.set_state(AdminAddProduct.user)
        await call.message.edit_text("Username?")

    elif action == "gen":
        await state.set_state(AdminGenCode.points)
        await call.message.edit_text("Points?")

    elif action == "addch":
        await state.set_state(AdminAddChannel.chat_id)
        await call.message.edit_text("Channel ID?")

    elif action == "delch":
        await state.set_state(AdminDelChannel.chat_id)
        await call.message.edit_text("Channel ID to delete?")

    elif action == "cast":
        await state.set_state(AdminBroadcast.msg)
        await call.message.edit_text("Send broadcast msg")

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
         
