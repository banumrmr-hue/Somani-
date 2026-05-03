import sqlite3
import time
import logging

from aiogram import Bot, Dispatcher, executor, types


# ================= CONFIG =================

BOT_TOKEN = "8628992445:AAFn4ElPXRa6-8huefzzIFcC3OMecIDXXUM"

ADMINS = [
    7672413819,
    7418454273
]

SUPPORT = "@somani_07x"

FORCE_CHANNEL = "@somanieraa"

BONUS = 25
REF_POINTS = 10


# ================= INIT =================

logging.basicConfig(
    level=logging.INFO
)

bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot)


# ================= DATABASE =================

db = sqlite3.connect(
    "bot.db",
    check_same_thread=False
)

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    last_bonus INTEGER DEFAULT 0
)
""")

db.commit()


# ================= FUNCTIONS =================

def user_exists(uid):

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (uid,)
    )

    return cursor.fetchone()


def add_user(uid):

    cursor.execute(
        """
        INSERT OR IGNORE
        INTO users(user_id)
        VALUES(?)
        """,
        (uid,)
    )

    db.commit()


def get_points(uid):

    cursor.execute(
        """
        SELECT points
        FROM users
        WHERE user_id=?
        """,
        (uid,)
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return 0


def add_points(uid, pts):

    if not user_exists(uid):
        add_user(uid)

    cursor.execute(
        """
        UPDATE users
        SET points=points+?
        WHERE user_id=?
        """,
        (
            pts,
            uid
        )
    )

    db.commit()


async def check_force_join(uid):

    try:

        member = await bot.get_chat_member(
            FORCE_CHANNEL,
            uid
        )

        if member.status in [
            "creator",
            "administrator",
            "member"
        ]:
            return True

        return False

    except:
        return False


# ================= UI =================

def main_menu():

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(
        types.InlineKeyboardButton(
            "🛍 STORE",
            callback_data="store"
        ),

        types.InlineKeyboardButton(
            "🎁 DAILY BONUS",
            callback_data="bonus"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "💳 MY POINTS",
            callback_data="points"
        ),

        types.InlineKeyboardButton(
            "🔗 REFER",
            callback_data="refer"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "📞 SUPPORT",
            url="https://t.me/somani_07x"
        )
    )

    return kb


# ================= START =================

@dp.message_handler(
    commands=["start"]
)
async def start(msg):

    uid = msg.from_user.id


    joined = await check_force_join(uid)

    if not joined:

        kb = types.InlineKeyboardMarkup()

        kb.add(
            types.InlineKeyboardButton(
                "📢 JOIN CHANNEL",
                url="https://t.me/somanieraa"
            )
        )

        await msg.answer(
            """
⚠️ First join channel

📢 @somanieraa

Then press /start
            """,
            reply_markup=kb
        )

        return


    args = msg.get_args()


    if not user_exists(uid):

        add_user(uid)

        if args:

            try:

                inviter = int(args)

                if inviter != uid:

                    add_points(
                        inviter,
                        REF_POINTS
                    )

            except:
                pass


    me = await bot.get_me()

    ref_link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start={uid}"
    )


    text = f"""
╔════════════════════╗
🔥 SOMANI ERA FREE UNC

👤 User ID: {uid}
⭐ Points: {get_points(uid)}

📞 {SUPPORT}
╚════════════════════╝

🔗 Referral:
{ref_link}
"""


    await msg.answer(
        text,
        reply_markup=main_menu()
    )


# ================= BUTTONS =================

@dp.callback_query_handler(
    lambda c: c.data == "points"
)
async def points(call):

    await call.message.answer(
        f"""
⭐ Your Points:

{get_points(call.from_user.id)}
        """
    )


@dp.callback_query_handler(
    lambda c: c.data == "refer"
)
async def refer(call):

    me = await bot.get_me()

    link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start="
        f"{call.from_user.id}"
    )

    await call.message.answer(
        f"""
🔗 Your Link:

{link}

👥 +10 per referral
        """
    )


@dp.callback_query_handler(
    lambda c: c.data == "bonus"
)
async def bonus(call):

    uid = call.from_user.id


    if not user_exists(uid):
        add_user(uid)


    cursor.execute(
        """
        SELECT last_bonus
        FROM users
        WHERE user_id=?
        """,
        (uid,)
    )

    row = cursor.fetchone()


    if row:
        last = row[0]
    else:
        last = 0


    now = int(
        time.time()
    )


    remaining = 86400 - (
        now - last
    )


    if remaining > 0:

        hours = remaining // 3600
        mins = (
            remaining % 3600
        ) // 60

        await call.message.answer(
            f"""
❌ Already claimed

⏳ Wait:

{hours}h {mins}m
            """
        )

        return


    add_points(
        uid,
        BONUS
    )


    cursor.execute(
        """
        UPDATE users
        SET last_bonus=?
        WHERE user_id=?
        """,
        (
            now,
            uid
        )
    )

    db.commit()


    await call.message.answer(
        f"""
🎁 Bonus Claimed

⭐ +{BONUS}
        """
    )


@dp.callback_query_handler(
    lambda c: c.data == "store"
)
async def store(call):

    await call.message.answer(
        """
🛍 STORE

10 → 2019
20 → 2018
30 → 2017
40 → 2016
50 → 2015
60 → 2014
70 → 2013
80 → 2012
        """
    )


# ================= ADMIN =================

@dp.message_handler(
    commands=["panel"]
)
async def panel(msg):

    if msg.from_user.id not in ADMINS:
        return

    await msg.answer(
        "👑 Admin Panel Active"
    )


@dp.message_handler(
    commands=["addbonus"]
)
async def addbonus(msg):

    if msg.from_user.id not in ADMINS:
        return


    try:

        data = msg.get_args().split()

        user_id = int(
            data[0]
        )

        points = int(
            data[1]
        )

    except:

        await msg.answer(
            """
Usage:

/addbonus user_id points

Example:

/addbonus 7418454273 500
            """
        )

        return


    add_points(
        user_id,
        points
    )


    await msg.answer(
        f"""
✅ Bonus Added

👤 {user_id}
⭐ +{points}
        """
    )


# ================= RUN =================

if __name__ == "__main__":

    executor.start_polling(
        dp,
        skip_updates=True
    )