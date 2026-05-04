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

# ================= CONFIG =================
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
ADMIN_IDS = [7418454273, 7672413819]
SUPPORT_LINK = "https://t.me/somani_07x"

MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

client = AsyncIOMotorClient(MONGO_URL)
db = client["ig_bot"]

users = db.users
store = db.store
channels = db.channels
redeem_codes = db.redeem_codes
claimed_codes = db.claimed_codes

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

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

# ================= FORCE JOIN =================
async def check_joined(user_id):
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

    return len(not_joined)==0, not_joined

# ================= MENU =================
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
        kb.append([InlineKeyboardButton(text="👑 ——— 𝘼𝘿𝙈𝙄𝙉 ——— 👑", callback_data="ignore")])
        kb.append([InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘼𝘾𝘾", callback_data="admin_add"),
                   InlineKeyboardButton(text="🎟️ 𝙂𝙀𝙉 𝘾𝙊𝘿𝙀", callback_data="admin_gen")])
        kb.append([InlineKeyboardButton(text="➕ 𝘼𝘿𝘿 𝘾𝙃", callback_data="admin_addch"),
                   InlineKeyboardButton(text="➖ 𝘿𝙀𝙇 𝘾𝙃", callback_data="admin_delch")])
        kb.append([InlineKeyboardButton(text="📢 𝘽𝙍𝙊𝘼𝘿𝘾𝘼𝙎𝙏", callback_data="admin_cast"),
                   InlineKeyboardButton(text="📊 𝙎𝙏𝘼𝙏𝙎", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, command: CommandObject):
    uid = message.from_user.id
    args = command.args

    ok, notj = await check_joined(uid)
    if not ok:
        kb = []
        for i,ch in enumerate(notj):
            kb.append([InlineKeyboardButton(text=f"Join {i+1}", url=ch[1])])
        kb.append([InlineKeyboardButton(text="Check", callback_data=f"check_{args or 0}")])
        await message.reply("Join channels first", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    user = await users.find_one({"user_id": uid})
    if not user:
        await users.insert_one({"user_id": uid, "points": 2, "last_bonus": None})

        if args and args.isdigit() and int(args)!=uid:
            await users.update_one({"user_id": int(args)}, {"$inc":{"points":5}})

    user = await users.find_one({"user_id": uid})
    await message.reply(f"<b>Balance:</b> {user['points']} 🪙", reply_markup=main_menu_kb(uid))

# ================= MENU HANDLER =================
@dp.callback_query(F.data.startswith("menu_"))
async def menu(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    action = call.data.split("_")[1]

    user = await users.find_one({"user_id": uid})

    if action=="points":
        await call.answer(f"{user['points']} 🪙", show_alert=True)

    elif action=="daily":
        now = datetime.now()
        if user.get("last_bonus"):
            last = datetime.fromisoformat(user["last_bonus"])
            if now < last + timedelta(hours=24):
                await call.answer("Wait 24h", show_alert=True)
                return

        await users.update_one({"user_id": uid},
                               {"$set":{"last_bonus": now.isoformat()},
                                "$inc":{"points":2}})
        await call.message.edit_text("Bonus claimed", reply_markup=main_menu_kb(uid))

    elif action=="refer":
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={uid}"
        await call.message.edit_text(f"<code>{link}</code>", reply_markup=main_menu_kb(uid))

    elif action=="store":
        items=[]
        async for i in store.find():
            items.append(i)

        if not items:
            await call.answer("Store empty", show_alert=True)
            return

        kb=[]
        for i in items:
            kb.append([InlineKeyboardButton(
                text=f"👤 {i['username']} [{i['year']}] - {i['price']}",
                callback_data=f"buy_{i['_id']}"
            )])

        await call.message.edit_text("Store:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    elif action=="redeem":
        await state.set_state(UserRedeem.waiting_for_code)
        await call.message.edit_text("Send code")

# ================= BUY =================
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    item = await store.find_one({"_id": ObjectId(call.data.split("_")[1])})
    user = await users.find_one({"user_id": call.from_user.id})

    if user["points"] < item["price"]:
        await call.answer("Not enough", show_alert=True)
        return

    await users.update_one({"user_id": call.from_user.id},
                           {"$inc":{"points": -item["price"]}})
    await store.delete_one({"_id": item["_id"]})

    await call.message.edit_text(f"{item['username']}\n{item['gmail']}")

# ================= REDEEM =================
@dp.message(UserRedeem.waiting_for_code)
async def redeem(message: Message, state: FSMContext):
    code = message.text.strip()
    uid = message.from_user.id

    c = await redeem_codes.find_one({"code": code})
    if not c or c["uses_left"]<=0:
        await message.reply("Invalid")
        return

    if await claimed_codes.find_one({"user_id":uid,"code":code}):
        await message.reply("Already used")
        return

    await redeem_codes.update_one({"code":code},{"$inc":{"uses_left":-1}})
    await claimed_codes.insert_one({"user_id":uid,"code":code})
    await users.update_one({"user_id":uid},{"$inc":{"points":c["points"]}})

    await message.reply("Redeemed")
    await state.clear()

# ================= ADMIN =================
@dp.callback_query(F.data.startswith("admin_"))
async def admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    action = call.data.split("_")[1]

    if action=="add":
        await state.set_state(AdminAddProduct.waiting_for_user)
        await call.message.edit_text("Send username")

    elif action=="stats":
        u = await users.count_documents({})
        s = await store.count_documents({})
        await call.message.edit_text(f"Users:{u}\nItems:{s}", reply_markup=main_menu_kb(call.from_user.id))

# ADD PRODUCT FLOW SAME AS ABOVE (ALREADY INCLUDED)
@dp.message(AdminAddProduct.waiting_for_user)
async def a1(m:Message,s:FSMContext):
    await s.update_data(username=m.text)
    await s.set_state(AdminAddProduct.waiting_for_gmail)
    await m.reply("gmail")

@dp.message(AdminAddProduct.waiting_for_gmail)
async def a2(m:Message,s:FSMContext):
    await s.update_data(gmail=m.text)
    await s.set_state(AdminAddProduct.waiting_for_year)
    await m.reply("year")

@dp.message(AdminAddProduct.waiting_for_year)
async def a3(m:Message,s:FSMContext):
    await s.update_data(year=m.text)
    await s.set_state(AdminAddProduct.waiting_for_price)
    await m.reply("price")

@dp.message(AdminAddProduct.waiting_for_price)
async def a4(m:Message,s:FSMContext):
    d=await s.get_data()
    await store.insert_one({
        "username":d["username"],
        "gmail":d["gmail"],
        "year":d["year"],
        "price":int(m.text)
    })
    await m.reply("Added", reply_markup=main_menu_kb(m.from_user.id))
    await s.clear()

# ================= RUN =================
async def main():
    print("RUNNING")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())

            
