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

from pymongo import MongoClient
from bson import ObjectId

# ================= CONFIG =================
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

ADMIN_IDS = [7616065999, 7672413819]
SUPPORT_LINK = 'https://t.me/somani_07x'

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE =================
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]

users_col = db["users"]
store_col = db["store"]
channels_col = db["channels"]
redeem_col = db["redeem_codes"]
claimed_col = db["claimed_codes"]

# ================= STATES =================
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

# ================= FUNCTIONS =================
async def check_joined(user_id: int):
    chs = list(channels_col.find())
    if not chs:
        return True, []

    not_joined = []
    for ch in chs:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except:
            not_joined.append(ch)

    return len(not_joined) == 0, not_joined

def main_menu_kb(user_id: int):
    kb = [
        [InlineKeyboardButton(text="🛍️ STORE", callback_data="menu_store"),
         InlineKeyboardButton(text="🎁 DAILY BONUS", callback_data="menu_daily")],
        [InlineKeyboardButton(text="🎟️ REDEEM", callback_data="menu_redeem"),
         InlineKeyboardButton(text="💳 POINTS", callback_data="menu_points")],
        [InlineKeyboardButton(text="🔗 REFER", callback_data="menu_refer"),
         InlineKeyboardButton(text="📞 SUPPORT", url=SUPPORT_LINK)]
    ]

    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="👑 ADMIN PANEL", callback_data="ignore")])
        kb.append([InlineKeyboardButton(text="➕ ADD ACCOUNT", callback_data="admin_add")])
        kb.append([InlineKeyboardButton(text="🎟️ GEN CODE", callback_data="admin_gen")])
        kb.append([InlineKeyboardButton(text="📢 BROADCAST", callback_data="admin_cast")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= START =================
@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject):
    user_id = message.from_user.id
    args = command.args

    user = users_col.find_one({"user_id": user_id})

    if not user:
        users_col.insert_one({
            "user_id": user_id,
            "points": 2,
            "last_bonus": None
        })

        if args and args.isdigit() and int(args) != user_id:
            users_col.update_one({"user_id": int(args)}, {"$inc": {"points": 5}})

    bal = users_col.find_one({"user_id": user_id})["points"]

    await message.reply(f"Welcome!\nBalance: {bal} 🪙", reply_markup=main_menu_kb(user_id))

# ================= MENU =================
@dp.callback_query(F.data.startswith("menu_"))
async def menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    action = call.data.split("_")[1]

    if action == "points":
        bal = users_col.find_one({"user_id": user_id})["points"]
        await call.answer(f"{bal} 🪙", show_alert=True)

    elif action == "daily":
        user = users_col.find_one({"user_id": user_id})
        now = datetime.now()

        if user.get("last_bonus"):
            last = datetime.fromisoformat(user["last_bonus"])
            if now < last + timedelta(hours=24):
                await call.answer("Wait 24h", show_alert=True)
                return

        users_col.update_one({"user_id": user_id},
                             {"$set": {"last_bonus": now.isoformat()},
                              "$inc": {"points": 2}})

        await call.message.edit_text("Bonus added!", reply_markup=main_menu_kb(user_id))

    elif action == "store":
        items = list(store_col.find())
        if not items:
            await call.answer("Store empty", show_alert=True)
            return

        kb = []
        for i in items:
            kb.append([InlineKeyboardButton(
                text=f"{i['username']} [{i['year']}] - {i['price']}",
                callback_data=f"buy_{str(i['_id'])}"
            )])

        await call.message.edit_text("Store:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    elif action == "refer":
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        await call.message.edit_text(link, reply_markup=main_menu_kb(user_id))

    elif action == "redeem":
        await state.set_state(UserRedeem.waiting_for_code)
        await call.message.edit_text("Send code")

# ================= BUY =================
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    user_id = call.from_user.id
    item_id = call.data.split("_")[1]

    item = store_col.find_one({"_id": ObjectId(item_id)})
    user = users_col.find_one({"user_id": user_id})

    if not item:
        await call.answer("Sold", show_alert=True)
        return

    if user["points"] < item["price"]:
        await call.answer("Not enough points", show_alert=True)
        return

    users_col.update_one({"user_id": user_id}, {"$inc": {"points": -item["price"]}})
    store_col.delete_one({"_id": item["_id"]})

    await call.message.edit_text(
        f"Bought!\nUser: {item['username']}\nGmail: {item['gmail']}\nYear: {item['year']}"
    )

# ================= REDEEM =================
@dp.message(UserRedeem.waiting_for_code)
async def redeem_func(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    data = redeem_col.find_one({"code": code})

    if not data or data["uses_left"] <= 0:
        await message.reply("Invalid code")
        return

    already = claimed_col.find_one({"user_id": user_id, "code": code})
    if already:
        await message.reply("Already used")
        return

    redeem_col.update_one({"code": code}, {"$inc": {"uses_left": -1}})
    claimed_col.insert_one({"user_id": user_id, "code": code})
    users_col.update_one({"user_id": user_id}, {"$inc": {"points": data["points"]}})

    await message.reply("Redeemed!")
    await state.clear()

# ================= ADMIN ADD =================
@dp.callback_query(F.data == "admin_add")
async def admin_add(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminAddProduct.waiting_for_user)
    await call.message.edit_text("Send username")

@dp.message(AdminAddProduct.waiting_for_user)
async def a1(message: Message, state: FSMContext):
    await state.update_data(username=message.text)
    await state.set_state(AdminAddProduct.waiting_for_gmail)
    await message.reply("Send gmail")

@dp.message(AdminAddProduct.waiting_for_gmail)
async def a2(message: Message, state: FSMContext):
    await state.update_data(gmail=message.text)
    await state.set_state(AdminAddProduct.waiting_for_year)
    await message.reply("Send year")

@dp.message(AdminAddProduct.waiting_for_year)
async def a3(message: Message, state: FSMContext):
    await state.update_data(year=message.text)
    await state.set_state(AdminAddProduct.waiting_for_price)
    await message.reply("Send price")

@dp.message(AdminAddProduct.waiting_for_price)
async def a4(message: Message, state: FSMContext):
    data = await state.get_data()

    store_col.insert_one({
        "username": data["username"],
        "gmail": data["gmail"],
        "year": data["year"],
        "price": int(message.text)
    })

    await message.reply("Added!")
    await state.clear()

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
