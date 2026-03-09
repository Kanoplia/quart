from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
import sqlite3
from aiogram.types import Message
from config import config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.token)
router_adm = Router()

adm_chat_id = config.adm_chat_id

def is_private_chat(message: Message) -> bool:
    chat_type = message.chat.type
    logger.info(f"Тип чата: {chat_type}, ID чата: {message.chat.id}")
    return chat_type == "private"

# Хендлер для команды /db (создание)
@router_adm.message(Command('db'))
async def cmd_start(message: types.Message):
    logger.info(f"Получена команда /db от пользователя {message.from_user.id}")
    if not is_private_chat(message):
        logger.info("Команда /db вызвана не в личке, игнорируем")
        return
    conn = sqlite3.connect('admins.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER,
            role_name TEXT,
            chat_id INTEGER,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    conn.commit()
    conn.close()
    await message.answer("База данных готова.")
    logger.info("База данных успешно создана")

# Функция для получения всех админов из чата и сохранения в базу
async def save_all_current_admins(chat_id):
    logger.info(f"Начинаем обновление админов для чата {chat_id}")
    conn = sqlite3.connect('admins.db')
    cursor = conn.cursor()
    
    try:
        # Получаем список всех администраторов чата
        administrators = await bot.get_chat_administrators(chat_id)
        
        # Очищаем старых админов для этого чата перед обновлением
        cursor.execute('DELETE FROM admins WHERE chat_id = ?', (chat_id,))
        
        for admin in administrators:
            user_id = admin.user.id
            # Для владельца чата устанавливаем соответствующую роль
            if admin.status == 'creator':
                role_name = "Creator"
            else:
                role_name = admin.custom_title or admin.status.title()  # "Administrator"
            
            # Добавляем в базу данных
            cursor.execute('''
                INSERT OR REPLACE INTO admins (user_id, role_name, chat_id)
                VALUES (?, ?, ?)
            ''', (user_id, role_name, chat_id))
        
        conn.commit()
        logger.info(f"Обновлен список админов для чата {chat_id}. Найдено: {len(administrators)}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении админов: {e}")
    finally:
        conn.close()

# Команда для обновления списка админов (работает только в личке)
@router_adm.message(Command('update_admins'))
async def cmd_update_admins(message: types.Message):
    logger.info(f"Получена команда /update_admins от пользователя {message.from_user.id}")
    if not is_private_chat(message):
        logger.info("Команда /update_admins вызвана не в личке, игнорируем")
        return
    
    await save_all_current_admins(adm_chat_id)
    await message.answer("Список администраторов обновлен.")


# Хендлер для команды /admin - выводит список админов и их ролей (работает только в личке)
@router_adm.message(Command('admin'))
async def cmd_admin_list(message: types.Message):
    logger.info(f"Получена команда /admin от пользователя {message.from_user.id}")
    if not is_private_chat(message):
        logger.info("Команда /admin вызвана не в личке, игнорируем")
        return
    conn = sqlite3.connect('admins.db')
    cursor = conn.cursor()
    
    try:
        # Получаем всех админов из нужного чата
        cursor.execute('SELECT user_id, role_name FROM admins WHERE chat_id = ?', (adm_chat_id,))
        results = cursor.fetchall()
        
        if results:
            admin_list = []
            for user_id, role_name in results:
                try:
                    user = await bot.get_chat_member(adm_chat_id, user_id)
                    username = user.user.username or f"{user.user.first_name} {user.user.last_name or ''}".strip()
                    admin_list.append(f"• @{username} - {role_name}" if user.user.username else f"• {username} - {role_name}")
                except Exception:
                    admin_list.append(f"• User ID: {user_id} - {role_name}")
            
            response = "Список администраторов:\n" + "\n".join(admin_list)
        else:
            response = "В этом чате нет сохраненных администраторов."
    finally:
        conn.close()
    
    await message.answer(response)
