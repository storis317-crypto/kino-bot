import os
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# =========================
# SOZLAMALAR
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL", "")  # masalan: @kino_kanal


# =========================
# DATABASE
# =========================

db = sqlite3.connect("kino.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    title TEXT,
    file_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

db.commit()


# =========================
# BOT
# =========================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================
# ADMIN HOLATLARI
# =========================

class AddMovie(StatesGroup):
    code = State()
    title = State()
    video = State()


class DeleteMovie(StatesGroup):
    code = State()


# =========================
# KEYBOARDLAR
# =========================

def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 Kino qo‘shish"),
                KeyboardButton(text="🗑 Kino o‘chirish")
            ],
            [
                KeyboardButton(text="📋 Kinolar"),
                KeyboardButton(text="📊 Statistika")
            ]
        ],
        resize_keyboard=True
    )


def subscribe_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalga obuna bo‘lish",
                    url=f"https://t.me/{FORCE_CHANNEL.replace('@', '')}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Obunani tekshirish",
                    callback_data="check_sub"
                )
            ]
        ]
    )


# =========================
# OBUNA TEKSHIRISH
# =========================

async def check_subscription(user_id: int):

    if not FORCE_CHANNEL:
        return True

    try:
        member = await bot.get_chat_member(
            chat_id=FORCE_CHANNEL,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception:
        return False


# =========================
# START
# =========================

@dp.message(Command("start"))
async def start(message: Message):

    user_id = message.from_user.id

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )
    db.commit()

    if not await check_subscription(user_id):

        await message.answer(
            "❗ Botdan foydalanish uchun kanalimizga obuna bo‘ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    await message.answer(
        "🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        "🔢 Kino kodini yuboring.",
        parse_mode="HTML"
    )


# =========================
# OBUNANI QAYTA TEKSHIRISH
# =========================

@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):

    if await check_subscription(callback.from_user.id):

        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "🎬 Endi kino kodini yuboring."
        )

    else:

        await callback.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz!",
            show_alert=True
        )


# =========================
# ADMIN PANEL
# =========================

@dp.message(Command("admin"))
async def admin(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "👑 <b>ADMIN PANEL</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# =========================
# KINO QO‘SHISH
# =========================

@dp.message(F.text == "🎬 Kino qo‘shish")
async def add_movie_start(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AddMovie.code)

    await message.answer(
        "🔢 Kino kodini yuboring.\n\n"
        "Masalan: <code>1001</code>",
        parse_mode="HTML"
    )


@dp.message(StateFilter(AddMovie.code))
async def add_movie_code(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()

    cursor.execute(
        "SELECT * FROM movies WHERE code = ?",
        (code,)
    )

    if cursor.fetchone():

        await message.answer(
            "❌ Bu kod allaqachon mavjud.\n"
            "Boshqa kod yuboring."
        )
        return

    await state.update_data(code=code)
    await state.set_state(AddMovie.title)

    await message.answer(
        "🎬 Kino nomini yuboring."
    )


@dp.message(StateFilter(AddMovie.title))
async def add_movie_title(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.update_data(title=message.text)
    await state.set_state(AddMovie.video)

    await message.answer(
        "🎥 Endi kino videosini yuboring."
    )


@dp.message(StateFilter(AddMovie.video), F.video)
async def add_movie_video(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()

    code = data["code"]
    title = data["title"]
    file_id = message.video.file_id

    cursor.execute(
        "INSERT INTO movies (code, title, file_id) VALUES (?, ?, ?)",
        (code, title, file_id)
    )

    db.commit()

    await state.clear()

    await message.answer(
        f"✅ <b>Kino qo‘shildi!</b>\n\n"
        f"🎬 Nomi: {title}\n"
        f"🔢 Kodi: <code>{code}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================
# KINO O‘CHIRISH
# =========================

@dp.message(F.text == "🗑 Kino o‘chirish")
async def delete_movie_start(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(DeleteMovie.code)

    await message.answer(
        "🗑 O‘chiriladigan kino kodini yuboring."
    )


@dp.message(StateFilter(DeleteMovie.code))
async def delete_movie(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()

    cursor.execute(
        "SELECT title FROM movies WHERE code = ?",
        (code,)
    )

    movie = cursor.fetchone()

    if not movie:

        await message.answer(
            "❌ Bunday kino topilmadi."
        )
        await state.clear()
        return

    cursor.execute(
        "DELETE FROM movies WHERE code = ?",
        (code,)
    )

    db.commit()
    await state.clear()

    await message.answer(
        f"✅ Kino o‘chirildi.\n\n"
        f"🎬 {movie[0]}\n"
        f"🔢 Kod: {code}",
        reply_markup=admin_keyboard()
    )


# =========================
# KINOLAR RO‘YXATI
# =========================

@dp.message(F.text == "📋 Kinolar")
async def movies_list(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "SELECT code, title FROM movies ORDER BY id DESC"
    )

    movies = cursor.fetchall()

    if not movies:

        await message.answer("📭 Hozircha kino yo‘q.")
        return

    text = "📋 <b>Kinolar:</b>\n\n"

    for code, title in movies:

        text += f"🔢 <code>{code}</code> — {title}\n"

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================
# STATISTIKA
# =========================

@dp.message(F.text == "📊 Statistika")
async def statistics(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM movies")
    movies = cursor.fetchone()[0]

    await message.answer(
        f"📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {movies}",
        parse_mode="HTML"
    )


# =========================
# KINO KODI
# =========================

@dp.message(F.text)
async def find_movie(message: Message):

    if message.from_user.id == ADMIN_ID:
        return

    if not await check_subscription(message.from_user.id):

        await message.answer(
            "❗ Avval kanalga obuna bo‘ling.",
            reply_markup=subscribe_keyboard()
        )
        return

    code = message.text.strip()

    cursor.execute(
        "SELECT title, file_id FROM movies WHERE code = ?",
        (code,)
    )

    movie = cursor.fetchone()

    if not movie:

        await message.answer(
            "❌ Bunday kino kodi topilmadi."
        )
        return

    title, file_id = movie

    await message.answer_video(
        video=file_id,
        caption=f"🎬 <b>{title}</b>\n\n"
                f"🔢 Kino kodi: <code>{code}</code>",
        parse_mode="HTML"
    )


# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

async def main():

    print("Bot ishga tushdi...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())