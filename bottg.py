import asyncio
import re
import aiosqlite
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ------------------ НАСТРОЙКИ ------------------
API_ID = 25319214
API_HASH = "dfccc6579aa1e0e25e5b59b02c1210f3"

SOURCE_CHANNELS = [
    "@serch",
    "@b_retail",
    "@ndnews24",
    "@moscowach",
    "@techatex",
    "@testvrggdju"
]

TARGET_CHANNEL = "@newsruchannel"
DB_PATH = "forwarded_posts.db"
SESSION_NAME = "my_account.session"

BOT_TOKEN = "6518436315:AAH1A7_hiPig-TkEXzqfCaLqRv_LhJfUfow"
# ------------------------------------------------

# ---------- Глобальные переменные авторизации ----------
auth_phone = None
auth_code = None
auth_event = asyncio.Event()  # событие синхронизации

# ---------- Клиент юзербота ----------
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ---------- Клиент бота для авторизации ----------
bot = TelegramClient(StringSession(), API_ID, API_HASH)

# ------------------ ФУНКЦИИ БД ------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forwarded (
                message_id INTEGER,
                chat_id INTEGER,
                PRIMARY KEY (message_id, chat_id)
            )
        """)
        await db.commit()

async def is_forwarded(message_id, chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM forwarded WHERE message_id = ? AND chat_id = ?",
            (message_id, chat_id)
        ) as cursor:
            return await cursor.fetchone() is not None

async def mark_forwarded(message_id, chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO forwarded (message_id, chat_id) VALUES (?, ?)",
            (message_id, chat_id)
        )
        await db.commit()

# ------------------ ОЧИСТКА ТЕКСТА ------------------
def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    lines = text.splitlines()
    cleaned_lines = [line for line in lines if not re.search(r"(t\.me/|@)\S+", line)]
    result = "\n".join(cleaned_lines).strip()
    return result if result else None

# ------------------ ОБРАБОТЧИК СОБЫТИЙ ЮЗЕРБОТА ------------------
@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    chat_id = event.chat_id
    msg_id = event.message.id
    if await is_forwarded(msg_id, chat_id):
        return

    caption = clean_text(event.message.message or event.message.text)

    try:
        if event.message.media:
            await client.send_file(TARGET_CHANNEL, event.message.media, caption=caption)
            print(f"✅ Переслано медиа из {event.chat.username or chat_id}")
        elif caption:
            await client.send_message(TARGET_CHANNEL, caption)
            print(f"✅ Переслан текст: {caption[:50]}...")
        else:
            print("⚠️ Сообщение пустое после очистки, пропущено.")
    except Exception as e:
        print(f"⚠️ Ошибка при пересылке: {e}")

    await mark_forwarded(msg_id, chat_id)

# ------------------ ОБРАБОТЧИК БОТА ------------------
@bot.on(events.NewMessage(pattern='/start_auth'))
async def start_auth(event):
    await event.respond("Отправьте ваш номер телефона:")
    bot.current_step = "phone"

@bot.on(events.NewMessage)
async def handle_message(event):
    global auth_phone, auth_code
    if getattr(bot, 'current_step', None) == "phone":
        auth_phone = event.message.text.strip()
        await event.respond(f"Номер получен: {auth_phone}\nОтправьте код подтверждения:")
        bot.current_step = "code"
    elif getattr(bot, 'current_step', None) == "code":
        auth_code = event.message.text.strip()
        await event.respond("Код получен. Продолжаем авторизацию...")
        bot.current_step = None
        auth_event.set()

# ------------------ ГЛАВНАЯ ФУНКЦИЯ ------------------
async def main():
    await init_db()
    print("🚀 База данных готова.")
    
    # Стартуем бота для авторизации
    await bot.start(bot_token=BOT_TOKEN)
    print("💬 Бот для авторизации запущен. Отправьте /start_auth в Telegram.")

    # Ждем ввода номера телефона
    while auth_phone is None:
        await asyncio.sleep(1)

    # Авторизация Telethon через номер и код
    async with client:
        await client.start(
            phone=lambda: auth_phone,
            code_callback=lambda: (asyncio.create_task(auth_event.wait()), auth_code)[1]
        )
        print("✅ Юзербот авторизован через Telegram-бот.")
        print("🚀 Ожидание новых сообщений...")

        # Запуск юзербота и бота параллельно
        await asyncio.gather(
            client.run_until_disconnected(),
            bot.run_until_disconnected()
        )

if __name__ == "__main__":
    asyncio.run(main())