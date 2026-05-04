import random
import string
import html
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_TOKEN = '8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY'
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

# ==========================================
# 🧠 STATES
# ==========================================
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

# ==========================================
# 🔒 FORCE JOIN
# ==========================================
async def check_joined(user_id: int):
    not_joined = []
    async for ch in channels.find():
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append((ch["chat_id"], ch["url"]))
        except:
            not_joined.append((ch["chat_id"], ch["url"]))
    return len(not_joined) == 0, not_joined

# ==========================================
# 🏠 MENU
# ==========================================
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
        kb_rows.append([InlineKeyboardButton(text="👑 ——— 𝘼𝘿𝙈𝙄𝙉 ——— 👑", callback_data="ignore_click")])
        kb_rows.append([InlineKeyboardButton(text="➕ ADD ACCOUNT", callback_data="admin_add"),
                        InlineKeyboardButton(text="🎟️ GEN CODE", callback_data="admin_gen")])
        kb_rows.append([InlineKeyboardButton(text="➕ ADD CHNL", callback_data="admin_addch"),
                        InlineKeyboardButton(text="➖ DEL CHNL", callback_data="admin_delch")])
        kb_rows.append([InlineKeyboardButton(text="📢 BROADCAST", callback_data="admin_cast"),
                        InlineKeyboardButton(text="📊 STATS", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=kb_rows)

# ==========================================
# 🚀 START + REFERRAL
# ==========================================
async def process_new_user_and_welcome(user_id, message_obj, args, is_callback=False):
    user = await users.find_one({"user_id": user_id})

    if not user:
        await users.insert_one({
            "user_id": user_id,
            "points": 2,
            "last_bonus": None
        })

        if args and args.isdigit() and int(args) != user_id:
            await users.update_one({"user_id": int(args)}, {"$inc": {"points": 5}})

    user = await users.find_one({"user_id": user_id})
    bal = user["points"]

    text = f"<b>𝙐𝙉𝘾 𝙄𝙂 𝘽𝙊𝙏✨❣️</b>\n\nBalance: <b>{bal} 🪙</b>"

    if is_callback:
        await message_obj.answer(text, reply_markup=main_menu_kb(user_id))
    else:
        await message_obj.reply(text, reply_markup=main_menu_kb(user_id))

@dp.message(CommandStart())
async def start_cmd(message: Message, command: CommandObject):
    user_id = message.from_user.id
    args = command.args

    is_joined, not_joined = await check_joined(user_id)

    if not is_joined:
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for idx, (_, url) in enumerate(not_joined):
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"Join {idx+1}", url=url)])
        kb.inline_keyboard.append([InlineKeyboardButton(text="Check", callback_data=f"check_join_{args or 0}")])
        await message.reply("Join channels first!", reply_markup=kb)
        return

    await process_new_user_and_welcome(user_id, message, args)

# ==========================================
# 🎁 DAILY BONUS
# ==========================================
@dp.callback_query(F.data == "menu_daily")
async def daily_bonus(call: CallbackQuery):
    user = await users.find_one({"user_id": call.from_user.id})
    now = datetime.now()

    if user.get("last_bonus"):
        if now < user["last_bonus"] + timedelta(hours=24):
            await call.answer("Come later", show_alert=True)
            return

    await users.update_one(
        {"user_id": call.from_user.id},
        {"$set": {"last_bonus": now}, "$inc": {"points": 2}}
    )

    await call.message.edit_text("Bonus Claimed!", reply_markup=main_menu_kb(call.from_user.id))

# ==========================================
# 🛍️ STORE
# ==========================================
@dp.callback_query(F.data == "menu_store")
async def store_menu(call: CallbackQuery):
    kb = []

    async for item in store.find():
        kb.append([
            InlineKeyboardButton(
                text=f"👤 {item['username']} [Yr:{item['year']}] - {item['price']}",
                callback_data=f"buy_{item['_id']}"
            )
        ])

    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_main")])

    await call.message.edit_text("Select account:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ==========================================
# 💰 BUY
# ==========================================
@dp.callback_query(F.data.startswith("buy_"))
async def buy_item(call: CallbackQuery):
    item_id = call.data.split("_")[1]
    item = await store.find_one({"_id": ObjectId(item_id)})
    user = await users.find_one({"user_id": call.from_user.id})

    if not item:
        await call.answer("Already sold", show_alert=True)
        return

    if user["points"] < item["price"]:
        await call.answer("Not enough points", show_alert=True)
        return

    await users.update_one({"user_id": call.from_user.id}, {"$inc": {"points": -item["price"]}})
    await store.delete_one({"_id": ObjectId(item_id)})

    await call.message.edit_text(
        f"🎉 Purchase Done!\n\n👤 {item['username']}\n📧 {item['gmail']}\n📅 {item['year']}",
        reply_markup=main_menu_kb(call.from_user.id)
    )

# ==========================================
# 🎟️ REDEEM
# ==========================================
@dp.message(UserRedeem.waiting_for_code)
async def redeem(message: Message, state: FSMContext):
    code = await redeem_codes.find_one({"code": message.text})

    if not code or code["uses_left"] <= 0:
        await message.reply("Invalid code")
        return

    already = await claimed_codes.find_one({
        "user_id": message.from_user.id,
        "code": message.text
    })

    if already:
        await message.reply("Already used")
        return

    await redeem_codes.update_one({"code": message.text}, {"$inc": {"uses_left": -1}})
    await claimed_codes.insert_one({"user_id": message.from_user.id, "code": message.text})
    await users.update_one({"user_id": message.from_user.id}, {"$inc": {"points": code["points"]}})

    await message.reply("Redeemed!")
    await state.clear()

# ==========================================
# 🚀 RUN
# ==========================================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
