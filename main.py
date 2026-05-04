import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from pymongo import MongoClient
from bson import ObjectId

# ========= CONFIG =========
API_TOKEN = "8628992445:AAE_7n3Jjru_71_b9LKdfeMF01mc7wLS_YY"
MONGO_URL = "mongodb+srv://adminbot:admin123@cluster0.tnvj2pr.mongodb.net/?retryWrites=true&w=majority"

ADMIN_IDS = [7418454273,7672413819]

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ========= DB =========
client = MongoClient(MONGO_URL)
db = client["bot"]

users = db["users"]
store = db["store"]
channels = db["channels"]

# ========= FORCE JOIN =========
async def check_join(user_id):
    chs = list(channels.find())
    not_joined = []

    for ch in chs:
        try:
            member = await bot.get_chat_member(ch["chat_id"], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)

    return not_joined

def force_kb(chs):
    kb = []
    for ch in chs:
        kb.append([InlineKeyboardButton(text="🔔 𝐉𝐎𝐈𝐍", url=ch["url"])])
    kb.append([InlineKeyboardButton(text="✅ 𝐈 𝐉𝐎𝐈𝐍𝐄𝐃", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ========= MENU =========
def menu(uid):
    kb = [
        [InlineKeyboardButton(text="🛍 𝐒𝐓𝐎𝐑𝐄", callback_data="store"),
         InlineKeyboardButton(text="💳 𝐏𝐎𝐈𝐍𝐓𝐒", callback_data="points")]
    ]
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="➕ 𝐀𝐃𝐃", callback_data="add")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ========= START =========
@dp.message(CommandStart())
async def start(msg: Message):
    uid = msg.from_user.id

    if not users.find_one({"user_id": uid}):
        users.insert_one({"user_id": uid, "points": 2})

    not_joined = await check_join(uid)

    if not_joined:
        await msg.reply(
            "<b>🚫 𝐀𝐂𝐂𝐄𝐒𝐒 𝐃𝐄𝐍𝐈𝐄𝐃</b>\n\n"
            "👉 𝐀𝐥𝐥 𝐜𝐡𝐚𝐧𝐧𝐞𝐥𝐬 𝐣𝐨𝐢𝐧 𝐤𝐚𝐫𝐨",
            reply_markup=force_kb(not_joined)
        )
        return

    bal = users.find_one({"user_id": uid})["points"]

    await msg.reply(
        f"<b>👋 𝐖𝐄𝐋𝐂𝐎𝐌𝐄</b>\n💰 𝐁𝐚𝐥𝐚𝐧𝐜𝐞: {bal}",
        reply_markup=menu(uid)
    )

# ========= CHECK =========
@dp.callback_query(F.data == "check_join")
async def check(call: CallbackQuery):
    uid = call.from_user.id
    not_joined = await check_join(uid)

    if not_joined:
        await call.answer("❌ 𝐉𝐨𝐢𝐧 𝐚𝐥𝐥", show_alert=True)
    else:
        bal = users.find_one({"user_id": uid})["points"]
        await call.message.edit_text(
            f"<b>✅ 𝐀𝐂𝐂𝐄𝐒𝐒 𝐆𝐑𝐀𝐍𝐓𝐄𝐃</b>\n💰 {bal}",
            reply_markup=menu(uid)
        )

# ========= ADD CHANNEL =========
@dp.message(F.text.startswith("/addchannel"))
async def add_channel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        _, chat_id, url = msg.text.split()
        channels.insert_one({"chat_id": int(chat_id), "url": url})
        await msg.reply("✅ 𝐂𝐇𝐀𝐍𝐍𝐄𝐋 𝐀𝐃𝐃𝐄𝐃")
    except:
        await msg.reply("Use:\n/addchannel -100xxxx https://t.me/xxx")

# ========= STORE =========
@dp.callback_query(F.data == "store")
async def store_show(call: CallbackQuery):
    not_joined = await check_join(call.from_user.id)
    if not_joined:
        await call.message.answer("⚠️ 𝐉𝐨𝐢𝐧 𝐟𝐢𝐫𝐬𝐭", reply_markup=force_kb(not_joined))
        return

    items = list(store.find())
    if not items:
        await call.answer("𝐄𝐦𝐩𝐭𝐲", show_alert=True)
        return

    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(
            text=f"{i['name']} - {i['price']}",
            callback_data=f"buy_{i['_id']}"
        )])

    await call.message.edit_text("🛍 𝐒𝐓𝐎𝐑𝐄", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========= BUY =========
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    uid = call.from_user.id

    not_joined = await check_join(uid)
    if not_joined:
        await call.message.answer("⚠️ 𝐉𝐨𝐢𝐧 𝐟𝐢𝐫𝐬𝐭", reply_markup=force_kb(not_joined))
        return

    item = store.find_one({"_id": ObjectId(call.data.split("_")[1])})
    user = users.find_one({"user_id": uid})

    if user["points"] < item["price"]:
        await call.answer("❌ 𝐍𝐨 𝐏𝐨𝐢𝐧𝐭𝐬", show_alert=True)
        return

    users.update_one({"user_id": uid}, {"$inc": {"points": -item["price"]}})
    store.delete_one({"_id": item["_id"]})

    await call.message.edit_text(f"✅ 𝐁𝐎𝐔𝐆𝐇𝐓\n{item['name']}")

# ========= ADD ITEM =========
@dp.callback_query(F.data == "add")
async def add_item(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.answer("Send: name price")

@dp.message()
async def save_item(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    try:
        name, price = msg.text.split()
        store.insert_one({"name": name, "price": int(price)})
        await msg.reply("✅ 𝐀𝐃𝐃𝐄𝐃")
    except:
        pass

# ========= POINTS =========
@dp.callback_query(F.data == "points")
async def points(call: CallbackQuery):
    bal = users.find_one({"user_id": call.from_user.id})["points"]
    await call.answer(f"{bal} 𝐏𝐨𝐢𝐧𝐭𝐬", show_alert=True)

# ========= RUN =========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
