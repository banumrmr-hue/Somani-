import random, string, asyncio, os
from datetime import datetime, timedelta
import psycopg2
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [7418454273, 7672413819]

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ===== UI =====
def ui(title, body):
    return f"✨ <b>{title}</b>\n\n{body}\n\n━━━━━━━━━━━━━━━"

# ===== DATABASE =====
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS users(user_id BIGINT PRIMARY KEY,points INT DEFAULT 2,ref_by BIGINT,last_bonus TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS store(id SERIAL PRIMARY KEY,username TEXT,gmail TEXT,year TEXT,price INT)")
c.execute("CREATE TABLE IF NOT EXISTS redeem_codes(code TEXT PRIMARY KEY,points INT,uses_left INT)")
c.execute("CREATE TABLE IF NOT EXISTS claimed_codes(user_id BIGINT,code TEXT,PRIMARY KEY(user_id,code))")
c.execute("CREATE TABLE IF NOT EXISTS channels(chat_id TEXT PRIMARY KEY)")

# ===== STATES =====

class Redeem(StatesGroup):
    code = State()

class Broadcast(StatesGroup):
    msg = State()

class GenCode(StatesGroup):
    pts = State()
    uses = State()

class AddChannel(StatesGroup):
    chat_id = State()

class DelChannel(StatesGroup):
    chat_id = State()

# 👇 YEH YAHI ADD KARNA HAI
class AddItem(StatesGroup):
    username = State()
    gmail = State()
    year = State()
    price = State()

# ===== MENU =====
def menu(uid):
    kb=[
        [InlineKeyboardButton(text="🛍 STORE",callback_data="store"),
         InlineKeyboardButton(text="🎁 BONUS",callback_data="bonus")],
        [InlineKeyboardButton(text="🎟 REDEEM",callback_data="redeem"),
         InlineKeyboardButton(text="💳 POINTS",callback_data="points")],
        [InlineKeyboardButton(text="🔗 REFER",callback_data="refer")]
    ]
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="👑 ADMIN",callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ===== START =====
@dp.message(CommandStart())
async def start(msg:Message,command:CommandObject):
    uid=msg.from_user.id
    ref=command.args

    c.execute("SELECT * FROM users WHERE user_id=%s",(uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users(user_id,ref_by) VALUES(%s,%s)",(uid,ref if ref else None))
        if ref and ref.isdigit():
            c.execute("UPDATE users SET points=points+5 WHERE user_id=%s",(int(ref),))

    c.execute("SELECT points FROM users WHERE user_id=%s",(uid,))
    bal=c.fetchone()[0]

    await msg.reply(ui("Welcome",f"💰 Balance: {bal} 🪙"),reply_markup=menu(uid))

# ===== POINTS =====
@dp.callback_query(F.data=="points")
async def points(call:CallbackQuery):
    c.execute("SELECT points FROM users WHERE user_id=%s",(call.from_user.id,))
    await call.answer(f"{c.fetchone()[0]} 🪙",show_alert=True)

# ===== BONUS =====
@dp.callback_query(F.data=="bonus")
async def bonus(call:CallbackQuery):
    uid=call.from_user.id
    now=datetime.now()
    c.execute("SELECT points,last_bonus FROM users WHERE user_id=%s",(uid,))
    pts,last=c.fetchone()

    if last and now < last + timedelta(hours=24):
        await call.answer("⏳ Come later",show_alert=True)
        return

    c.execute("UPDATE users SET points=points+2,last_bonus=%s WHERE user_id=%s",(now,uid))
    await call.message.edit_text(ui("🎁 Bonus",f"+2 🪙\nTotal: {pts+2}"),reply_markup=menu(uid))

# ===== REFER =====
@dp.callback_query(F.data=="refer")
async def refer(call:CallbackQuery):
    bot_info=await bot.get_me()
    link=f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    await call.message.edit_text(ui("🔗 Referral Link",link),reply_markup=menu(call.from_user.id))

# ===== STORE =====
@dp.callback_query(F.data=="store")
async def store(call:CallbackQuery):
    c.execute("SELECT id,username,price FROM store")
    items=c.fetchall()
    if not items:
        await call.answer("Empty",show_alert=True); return

    kb=[[InlineKeyboardButton(text=f"{i[1]} - {i[2]} 🪙",callback_data=f"buy_{i[0]}")] for i in items]
    await call.message.edit_text(ui("🛍 Store","Choose item"),reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ===== BUY =====
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call:CallbackQuery):
    uid=call.from_user.id
    item_id=int(call.data.split("_")[1])

    c.execute("SELECT points FROM users WHERE user_id=%s",(uid,))
    bal=c.fetchone()[0]

    c.execute("SELECT username,gmail,year,price FROM store WHERE id=%s",(item_id,))
    item=c.fetchone()

    if not item:
        await call.answer("Sold",show_alert=True); return

    if bal<item[3]:
        await call.answer("Not enough",show_alert=True); return

    c.execute("UPDATE users SET points=points-%s WHERE user_id=%s",(item[3],uid))
    c.execute("DELETE FROM store WHERE id=%s",(item_id,))

    await call.message.edit_text(ui("✅ Purchased",f"{item[0]}\n{item[1]}\n{item[2]}"),reply_markup=menu(uid))

# ===== REDEEM =====
@dp.callback_query(F.data=="redeem")
async def rbtn(call:CallbackQuery,state:FSMContext):
    await state.set_state(Redeem.code)
    await call.message.edit_text(ui("🎟 Redeem","Send code"))

@dp.message(Redeem.code)
async def redeem(msg:Message,state:FSMContext):
    code=msg.text.strip().upper()
    uid=msg.from_user.id

    c.execute("SELECT points,uses_left FROM redeem_codes WHERE code=%s",(code,))
    res=c.fetchone()

    if not res:
        await msg.reply("❌ Invalid"); return

    pts,uses=res
    if uses<=0:
        await msg.reply("❌ Expired"); return

    c.execute("SELECT 1 FROM claimed_codes WHERE user_id=%s AND code=%s",(uid,code))
    if c.fetchone():
        await msg.reply("❌ Used"); return

    c.execute("UPDATE redeem_codes SET uses_left=uses_left-1 WHERE code=%s",(code,))
    c.execute("INSERT INTO claimed_codes VALUES(%s,%s)",(uid,code))
    c.execute("UPDATE users SET points=points+%s WHERE user_id=%s",(pts,uid))

    await msg.reply(ui("✅ Success",f"+{pts} 🪙"))
    await state.clear()

# ===== ADMIN =====
@dp.callback_query(F.data=="admin")
async def admin(call:CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return

    kb = [
    [InlineKeyboardButton(text="🎟 GEN CODE", callback_data="gen")],
    [InlineKeyboardButton(text="📢 BROADCAST", callback_data="bc")],
    [InlineKeyboardButton(text="📊 STATS", callback_data="stats")],
    [InlineKeyboardButton(text="➕ ADD ITEM", callback_data="add_item")],
    [InlineKeyboardButton(text="➕ ADD CHANNEL", callback_data="add_ch")],
    [InlineKeyboardButton(text="❌ DELETE CHANNEL", callback_data="del_ch")]
]

    await call.message.edit_text(ui("👑 Admin Panel","Manage bot"),
    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    
# ===== ADD ITEM =====
@dp.callback_query(F.data=="add_item")
async def add_item_start(call:CallbackQuery, state:FSMContext):
    await state.set_state(AddItem.username)
    await call.message.edit_text("👤 Send Username")

@dp.message(AddItem.username)
async def add_item_user(msg:Message, state:FSMContext):
    await state.update_data(username=msg.text)
    await state.set_state(AddItem.gmail)
    await msg.reply("📧 Send Gmail")

@dp.message(AddItem.gmail)
async def add_item_gmail(msg:Message, state:FSMContext):
    await state.update_data(gmail=msg.text)
    await state.set_state(AddItem.year)
    await msg.reply("📅 Send Year")

@dp.message(AddItem.year)
async def add_item_year(msg:Message, state:FSMContext):
    await state.update_data(year=msg.text)
    await state.set_state(AddItem.price)
    await msg.reply("💰 Send Price")

@dp.message(AddItem.price)
async def add_item_price(msg:Message, state:FSMContext):
    data = await state.get_data()

    c.execute(
        "INSERT INTO store(username, gmail, year, price) VALUES(%s,%s,%s,%s)",
        (data['username'], data['gmail'], data['year'], int(msg.text))
    )

    await msg.reply("✅ Item Added Successfully")
    await state.clear()
    
# ===== ADD CHANNEL =====
@dp.callback_query(F.data=="add_ch")
async def add_channel(call:CallbackQuery, state:FSMContext):
    await state.set_state(AddChannel.chat_id)
    await call.message.edit_text("📥 Send Channel ID")

@dp.message(AddChannel.chat_id)
async def save_channel(msg:Message, state:FSMContext):
    try:
        c.execute("INSERT INTO channels(chat_id) VALUES(%s)", (msg.text,))
        await msg.reply("✅ Channel Added")
    except:
        await msg.reply("⚠️ Already added or error")
    await state.clear()

# ===== DELETE CHANNEL =====
@dp.callback_query(F.data=="del_ch")
async def del_channel(call:CallbackQuery, state:FSMContext):
    await state.set_state(DelChannel.chat_id)
    await call.message.edit_text("❌ Send Channel ID")

@dp.message(DelChannel.chat_id)
async def remove_channel(msg:Message, state:FSMContext):
    c.execute("DELETE FROM channels WHERE chat_id=%s", (msg.text,))
    await msg.reply("✅ Channel Deleted")
    await state.clear()

# ===== GEN CODE =====
@dp.callback_query(F.data=="gen")
async def g1(call:CallbackQuery,state:FSMContext):
    await state.set_state(GenCode.pts)
    await call.message.edit_text("Points?")

@dp.message(GenCode.pts)
async def g2(msg:Message,state:FSMContext):
    await state.update_data(pts=int(msg.text))
    await state.set_state(GenCode.uses)
    await msg.reply("Uses?")

@dp.message(GenCode.uses)
async def g3(msg:Message,state:FSMContext):
    data=await state.get_data()
    code=''.join(random.choices(string.ascii_uppercase+string.digits,k=8))
    c.execute("INSERT INTO redeem_codes VALUES(%s,%s,%s)",(code,data['pts'],int(msg.text)))
    await msg.reply(ui("🎟 Code Generated",code))
    await state.clear()

# ===== STATS =====
@dp.callback_query(F.data=="stats")
async def stats(call:CallbackQuery):
    c.execute("SELECT COUNT(*) FROM users")
    users=c.fetchone()[0]
    await call.message.edit_text(ui("📊 Stats",f"👥 Users: {users}"))

# ===== BROADCAST =====
@dp.callback_query(F.data=="bc")
async def bc1(call:CallbackQuery,state:FSMContext):
    await state.set_state(Broadcast.msg)
    await call.message.edit_text("Send message")

@dp.message(Broadcast.msg)
async def bc2(msg:Message,state:FSMContext):
    c.execute("SELECT user_id FROM users")
    for u in c.fetchall():
        try: await bot.send_message(u[0],msg.text)
        except: pass
    await msg.reply("Done")
    await state.clear()

# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
