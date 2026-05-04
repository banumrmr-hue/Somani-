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
SUPPORT_LINK = 'https://t.me/somani_07x'

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

# ========= FORCE JOIN =========
async def check_joined(user_id: int):
    chs = []
    async for ch in channels.find():
        chs.append(ch)

    if not chs:
        return True, []

    not_joined = []
    for ch in chs:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status not in ['member','administrator','creator']:
                not_joined.append((ch["chat_id"], ch["url"]))
        except:
            not_joined.append((ch["chat_id"], ch["url"]))

    return len(not_joined) == 0, not_joined

# ========= MENU =========
def main_menu_kb(user_id: int):
    kb_rows = [
        [InlineKeyboardButton(text="🛍️ 𝙎𝙏𝙊𝙍𝙀", callback_data="menu_store"),
         InlineKeyboardButton(text="🎁 𝘿𝘼𝙄𝙇𝙔 𝘽𝙊𝙉𝙐𝙎", callback_data="menu_daily")],
        [InlineKeyboardButton(text="🎟️ 𝙍𝙀𝘿𝙀𝙀𝙈", callback_data="menu_redeem"),
         InlineKeyboardButton(text="💳 𝙈𝙔 𝙋𝙊𝙄𝙉𝙏𝙎", callback_data="menu_points")],
        [InlineKeyboardButton(text="🔗 𝙍𝙀𝙁𝙀𝙍", callback_data="menu_refer"),
         InlineKeyboardButton(text="📞 𝙎𝙐𝙋𝙋𝙊𝙍𝙏", url=SUPPORT_LINK)]
    ]

    if user_id in ADMIN_IDS:
        kb_rows.append([InlineKeyboardButton(text="👑 ——— 𝘼𝘿𝙈𝙄𝙉 𝘾𝙊𝙉𝙏𝙍𝙊𝙇𝙎 ——— 👑", callback_data="ignore_click")])
        kb_rows.append([InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘼𝘾𝘾𝙊𝙐𝙉𝙏", callback_data="admin_add"),
                        InlineKeyboardButton(text="🎟️ 𝙂𝙀𝙉𝙀𝙍𝘼𝙏𝙀 𝘾𝙊𝘿𝙀", callback_data="admin_gen")])
        kb_rows.append([InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘾𝙃𝙉𝙇", callback_data="admin_addch"),
                        InlineKeyboardButton(text="➖ 𝘿𝙀𝙇 𝘾𝙃𝙉𝙇", callback_data="admin_delch")])
        kb_rows.append([InlineKeyboardButton(text="📢 𝘽𝙍𝙊𝘼𝘿𝘾𝘼𝙎𝙏", callback_data="admin_cast"),
                        InlineKeyboardButton(text="📊 𝙎𝙏𝘼𝙏𝙎", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=kb_rows)

# ========= START =========
@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject):
    user_id = message.from_user.id
    args = command.args

    is_joined, not_joined = await check_joined(user_id)

    if not is_joined:
        kb = []
        for i, ch in enumerate(not_joined):
            kb.append([InlineKeyboardButton(text=f"Join {i+1}", url=ch[1])])
        await message.reply("Join all channels first", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    user = await users.find_one({"user_id": user_id})
    if not user:
        await users.insert_one({"user_id": user_id, "points": 2, "last_bonus": None})

    user = await users.find_one({"user_id": user_id})
    await message.reply(f"Balance: {user['points']} 🪙", reply_markup=main_menu_kb(user_id))

# ========= STORE =========
@dp.callback_query(F.data == "menu_store")
async def store_menu(call: CallbackQuery):
    items = []
    async for i in store.find():
        items.append(i)

    if not items:
        await call.answer("Store empty", show_alert=True)
        return

    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(
            text=f"👤 {i['username']} [Yr:{i['year']}] - {i['price']}",
            callback_data=f"buy_{i['_id']}"
        )])

    await call.message.edit_text("🛍️ Store", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========= ADD ACCOUNT =========
@dp.callback_query(F.data == "admin_add")
async def add_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminAddProduct.waiting_for_user)
    await call.message.edit_text("Send Username")

@dp.message(AdminAddProduct.waiting_for_user)
async def add_user(message: Message, state: FSMContext):
    await state.update_data(username=message.text)
    await state.set_state(AdminAddProduct.waiting_for_gmail)
    await message.reply("Send Gmail")

@dp.message(AdminAddProduct.waiting_for_gmail)
async def add_gmail(message: Message, state: FSMContext):
    await state.update_data(gmail=message.text)
    await state.set_state(AdminAddProduct.waiting_for_year)
    await message.reply("Send Year")

@dp.message(AdminAddProduct.waiting_for_year)
async def add_year(message: Message, state: FSMContext):
    await state.update_data(year=message.text)
    await state.set_state(AdminAddProduct.waiting_for_price)
    await message.reply("Send Price")

@dp.message(AdminAddProduct.waiting_for_price)
async def add_price(message: Message, state: FSMContext):
    data = await state.get_data()

    await store.insert_one({
        "username": data["username"],
        "gmail": data["gmail"],
        "year": data["year"],
        "price": int(message.text)
    })

    await message.reply("✅ Added", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

# ========= BUY =========
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    item = await store.find_one({"_id": ObjectId(call.data.split("_")[1])})
    user = await users.find_one({"user_id": call.from_user.id})

    if user["points"] < item["price"]:
        await call.answer("Not enough", show_alert=True)
        return

    await users.update_one({"user_id": call.from_user.id}, {"$inc": {"points": -item["price"]}})
    await store.delete_one({"_id": item["_id"]})

    await call.message.edit_text(f"Purchased\n{item['username']}\n{item['gmail']}")

# ========= RUN =========
async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

