import os
import asyncio
import traceback
import psycopg2 # Используем библиотеку для Postgres
from flask import Flask, request
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, Bot, error

# === Глобальная область: только создание Flask-приложения ===
app = Flask(__name__)


# --- Функции для работы с базой данных ---
def save_user_sync_postgres(postgres_url, user_id: int, username: str):
    """СИНХРОННО сохраняет или обновляет пользователя в Vercel Postgres."""
    try:
        # ON CONFLICT (chat_id) DO UPDATE... - это команда "upsert" для Postgres
        sql = """
        INSERT INTO users (chat_id, username)
        VALUES (%s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET
        username = EXCLUDED.username;
        """
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor()
        cur.execute(sql, (user_id, username))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Пользователь {user_id} ({username}) успешно сохранен в Vercel Postgres.")
    except Exception as e:
        print(f"--- !!! ОШИБКА при сохранении в Postgres: {e} !!! ---")
        print(traceback.format_exc())

def get_all_user_ids(postgres_url):
    """СИНХРОННО получает список всех chat_id из базы."""
    user_ids = []
    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM users;")
        # fetchall() возвращает список кортежей, например [(123,), (456,)]
        # Мы извлекаем из них только первые элементы (сами ID)
        user_ids = [item[0] for item in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        print(f"--- !!! ОШИБКА при получении списка ID из Postgres: {e} !!! ---")
    return user_ids
    
def remove_user_sync_postgres(postgres_url, user_id: int):
    """СИНХРОННО удаляет пользователя (например, если он заблокировал бота)."""
    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE chat_id = %s;", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Пользователь {user_id} удален из базы (заблокировал бота).")
    except Exception as e:
        print(f"--- !!! ОШИБКА при удалении пользователя {user_id} из Postgres: {e} !!! ---")

# --- Асинхронные обработчики команд ---
async def handle_start_async(bot, postgres_url, update: Update):
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else ""
    
    save_user_sync_postgres(postgres_url, user_id, username)
    
    keyboard = [
        [KeyboardButton("База знаний", web_app=WebAppInfo(url="https://aleksei23122012.teamly.ru/space/00647e86-cd4b-46ef-9903-0af63964ad43/article/17e16e2a-92ff-463c-8bf4-eaaf202c0bc7"))],
        [KeyboardButton("Отработка возражений", web_app=WebAppInfo(url="https://baza-znaniy-app.vercel.app/"))],
        [KeyboardButton("Отзывы и предложения", web_app=WebAppInfo(url="https://docs.google.com/forms/d/e/1FAIpQLSedAPNqKkoJxer4lISLVsQgmu6QpPagoWreyvYOz7DbFuanFw/viewform?usp=header"))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! 😊\n\n"
        "Чтобы открыть главный дашборд, нажми на кнопку **Дашборд** слева от поля ввода.\n\n"
        "А с помощью кнопок ниже ты можешь открыть другие полезные разделы.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
async def handle_admin_command_async(bot, postgres_url, update: Update):
    """Обрабатывает все команды администратора."""
    text_parts = update.message.text.split(' ', 1)
    command = text_parts[0]
    admin_id = update.message.chat_id

    if command == '/stats':
        try:
            conn = psycopg2.connect(postgres_url)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users;")
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            await update.message.reply_text(f"Всего пользователей в базе: {count}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка получения статистики: {e}")
    
    # --- НОВЫЙ ПОЛНОЦЕННЫЙ БЛОК ДЛЯ /broadcast ---
    elif command == '/broadcast' and len(text_parts) > 1:
        message_to_send = text_parts[1]
        await update.message.reply_text("Начинаю рассылку...")

        user_ids = get_all_user_ids(postgres_url)
        
        success_count = 0
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, text=message_to_send, parse_mode='Markdown')
                success_count += 1
                await asyncio.sleep(0.05) # Небольшая задержка
            except error.Forbidden:
                remove_user_sync_postgres(postgres_url, user_id)
            except error.TelegramError as e:
                print(f"Не удалось отправить сообщение {user_id}: {e}")
        
        await update.message.reply_text(f"Рассылка завершена. Отправлено: {success_count} из {len(user_ids)}.")

    else:
        await update.message.reply_text(
            "Неизвестная команда или неверный формат.\n"
            "Доступные команды:\n`/broadcast <текст>`\n`/stats`",
            parse_mode='Markdown'
        )


# === ГЛАВНЫЙ ВЕБХУК ===
@app.route('/', methods=['POST'])
def webhook():
    try:
        BOT_TOKEN = os.environ['BOT_TOKEN']
        POSTGRES_URL = os.environ['POSTGRES_URL']
        ADMIN_IDS_STR = os.environ.get('ADMIN_IDS', '')
        ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]

        bot = Bot(token=BOT_TOKEN)
        update_data = request.get_json()
        update = Update.de_json(update_data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            user_id = update.message.chat_id

            if text == '/start':
                asyncio.run(handle_start_async(bot, POSTGRES_URL, update))
            elif text.startswith('/') and user_id in ADMIN_IDS:
                asyncio.run(handle_admin_command_async(bot, POSTGRES_URL, update))

    except Exception as e:
        print(f"--- !!! КРИТИЧЕСКАЯ ОШИБКА В ВЕБХУКЕ !!! ---")
        print(traceback.format_exc())
                
    return 'ok', 200
