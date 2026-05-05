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

# ===== CONFIG =====
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [7418454273, 7672413819]

bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ===== DB =====
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS users(user_id BIGINT PRIMARY KEY,points INT DEFAULT 2,ref_by BIGINT,last_bonus TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS store(id SERIAL PRIMARY KEY,username TEXT,gmail TEXT,year TEXT,price INT)")
c.execute("CREATE TABLE IF NOT EXISTS redeem_codes(code TEXT PRIMARY KEY,points INT,uses_left INT)")
c.execute("CREATE TABLE IF NOT EXISTS claimed_codes(user_id BIGINT,code TEXT,PRIMARY KEY(user_id,code))")
c.execute("CREATE TABLE IF NOT EXISTS channels(chat_id TEXT PRIMARY KEY)")

# ===== UI =====
def ui(t,b):
    return f"✨ <b>{t}</b>\n\n{b}\n━━━━━━━━━━━━━━━"

# ===== FORCE SUB =====
async def check_sub(uid):
    c.execute("SELECT chat_id FROM channels")
    for ch in c.fetchall():
        try:
            m = await bot.get_chat_member(ch[0], uid)
            if m.status in ["left","kicked"]:
                return False
        except:
            return False
    return True

# ===== STATES =====
class Broadcast(StatesGroup): msg = State()
class Redeem(StatesGroup): code = State()
class GenCode(StatesGroup): pts = State(); uses = State()
class AddChannel(StatesGroup): chat_id = State()
class DelChannel(StatesGroup): chat_id = State()
class AddItem(StatesGroup):
    username = State()
    gmail = State()
    year = State()
    price = State()

# ===== MENU =====
def menu(uid):
    kb = [
        [InlineKeyboardButton("🛍 STORE","store"),
         InlineKeyboardButton("🎁 BONUS","bonus")],
        [InlineKeyboardButton("🎟 REDEEM","redeem"),
         InlineKeyboardButton("💳 POINTS","points")],
        [InlineKeyboardButton("🏆 LEADERBOARD","leaderboard")]
    ]
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton("👑 ADMIN","admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ===== START (REF + FORCE SUB FIXED) =====
@dp.message(CommandStart())
async def start(msg: Message, command: CommandObject):

    uid = msg.from_user.id
    ref = command.args

    # ===== FORCE SUB CHECK =====
    if not await check_sub(uid):
        c.execute("SELECT chat_id FROM channels")
        ch = c.fetchall()

        kb = [[InlineKeyboardButton(
            text="📢 Join",
            url=f"https://t.me/{i[0].replace('@','')}"
        )] for i in ch]

        kb.append([InlineKeyboardButton(text="🔄 Check Again", callback_data="start_again")])

        await msg.answer(
            "❌ Join channels first",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        return

    # ===== REF SYSTEM =====
    ref_id = None
    if ref and ref.isdigit():
        ref_id = int(ref)
        if ref_id == uid:
            ref_id = None

    # insert user safely
    c.execute("""
        INSERT INTO users(user_id, ref_by)
        VALUES(%s,%s)
        ON CONFLICT DO NOTHING
    """, (uid, ref_id))

    # ===== LEVEL 1 =====
    if ref_id:
        c.execute("UPDATE users SET points = points + 5 WHERE user_id = %s", (ref_id,))

        # ===== LEVEL 2 =====
        c.execute("SELECT ref_by FROM users WHERE user_id=%s", (ref_id,))
        lvl2 = c.fetchone()

        if lvl2 and lvl2[0]:
            c.execute("UPDATE users SET points = points + 2 WHERE user_id = %s", (lvl2[0],))

    # ===== BALANCE =====
    c.execute("SELECT points FROM users WHERE user_id=%s", (uid,))
    bal = c.fetchone()[0]

    await msg.answer(
        ui("Welcome", f"💰 {bal} 🪙"),
        reply_markup=menu(uid)
    )

# ===== RECHECK =====
@dp.callback_query(F.data=="start_again")
async def r(call: CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Verified")
    else:
        await call.answer("❌ Still not joined",show_alert=True)

# ===== POINTS =====
@dp.callback_query(F.data=="points")
async def p(call: CallbackQuery):
    c.execute("SELECT points FROM users WHERE user_id=%s",(call.from_user.id,))
    await call.answer(f"{c.fetchone()[0]} 🪙",show_alert=True)

# ===== BONUS =====
@dp.callback_query(F.data=="bonus")
async def b(call: CallbackQuery):
    uid=call.from_user.id
    now=datetime.now()

    c.execute("SELECT points,last_bonus FROM users WHERE user_id=%s",(uid,))
    d=c.fetchone()

    if d and d[1] and now < d[1]+timedelta(hours=24):
        await call.answer("⏳ 24h wait",show_alert=True)
        return

    c.execute("UPDATE users SET points=points+2,last_bonus=%s WHERE user_id=%s",(now,uid))
    await call.message.edit_text(ui("🎁 Bonus","+2 🪙"),reply_markup=menu(uid))

# ===== ADMIN PANEL =====
@dp.callback_query(F.data=="admin")
async def admin(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    kb = [
        [InlineKeyboardButton("🎟 GEN CODE","gen")],
        [InlineKeyboardButton("📢 BROADCAST","bc")],
        [InlineKeyboardButton("📊 STATS","stats")],
        [InlineKeyboardButton("➕ ADD CHANNEL","add_ch")],
        [InlineKeyboardButton("❌ DELETE CHANNEL","del_ch")],
        [InlineKeyboardButton("➕ ADD ITEM","add_item")],
        [InlineKeyboardButton("🏆 LEADERBOARD","leaderboard")]
    ]

    await call.message.edit_text("👑 ADMIN PANEL",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ===== ADD CHANNEL =====
@dp.callback_query(F.data=="add_ch")
async def add_ch(call: CallbackQuery,state:FSMContext):
    await state.set_state(AddChannel.chat_id)
    await call.message.edit_text("Send channel @username")

@dp.message(AddChannel.chat_id)
async def save_ch(msg: Message,state:FSMContext):
    c.execute("INSERT INTO channels(chat_id) VALUES(%s)",(msg.text,))
    await msg.reply("✅ Added")
    await state.clear()

# ===== DELETE CHANNEL =====
@dp.callback_query(F.data=="del_ch")
async def del_ch(call: CallbackQuery,state:FSMContext):
    await state.set_state(DelChannel.chat_id)
    await call.message.edit_text("Send channel @username")

@dp.message(DelChannel.chat_id)
async def rem_ch(msg: Message,state:FSMContext):
    c.execute("DELETE FROM channels WHERE chat_id=%s",(msg.text,))
    await msg.reply("❌ Deleted")
    await state.clear()

# ===== LEADERBOARD =====
@dp.callback_query(F.data=="leaderboard")
async def lb(call: CallbackQuery):
    c.execute("SELECT user_id,points FROM users ORDER BY points DESC LIMIT 10")
    data=c.fetchall()

    text="🏆 TOP USERS\n\n"
    for i,x in enumerate(data,1):
        text+=f"{i}. {x[0]} → {x[1]} 🪙\n"

    await call.message.edit_text(text)

# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
