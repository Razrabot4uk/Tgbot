import re
import asyncio
import aiosqlite
from telethon import TelegramClient, events

# ------------------ НАСТРОЙКИ ------------------
API_ID = 25319214
API_HASH = "dfccc6579aa1e0e25e5b59b02c1210f3"

# список каналов-источников (юзербот должен быть подписан!)
SOURCE_CHANNELS = [
    "@serch",
    "@b_retail",
    "@ndnews24",
    "@moscowach",
    "@techatex",
    "@testvrggdju"
]

# канал-цель, куда пересылать посты
TARGET_CHANNEL = "@newsruchannel"

DB_PATH = "forwarded_posts.db"
SESSION_NAME = "my_account"  # файл сессии для Telethon
# ------------------------------------------------

# Создаем клиент Telethon
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ------------------ БАЗА ------------------
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
    cleaned_lines = [
        line for line in lines
        if not re.search(r"(t\.me/|@)\S+", line)
    ]
    result = "\n".join(cleaned_lines).strip()
    return result if result else None


# ------------------ ОБРАБОТЧИК ------------------
@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    chat_id = event.chat_id
    msg_id = event.message.id

    if await is_forwarded(msg_id, chat_id):
        return  # уже пересылали

    caption = clean_text(event.message.message or event.message.text)

    try:
        if event.message.media:
            await client.send_file(
                TARGET_CHANNEL,
                event.message.media,
                caption=caption
            )
            print(f"✅ Переслано медиа из {event.chat.username or chat_id}")
        elif caption:
            await client.send_message(TARGET_CHANNEL, caption)
            print(f"✅ Переслан текст: {caption[:50]}...")
        else:
            print("⚠️ Сообщение пустое после очистки, пропущено.")
    except Exception as e:
        print(f"⚠️ Ошибка при пересылке: {e}")

    await mark_forwarded(msg_id, chat_id)


# ------------------ ГЛАВНЫЙ ЦИКЛ ------------------
async def main():
    await init_db()
    print("🚀 Юзербот запущен. Ожидание новых сообщений...")

    while True:  # вечный цикл
        try:
            await client.run_until_disconnected()
        except Exception as e:
            print(f"⚠️ Ошибка соединения: {e}. Перезапуск через 5 сек...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())