from .keyboart import *
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup
from config import config, support_chat_id  
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import sqlite3 
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_help = Router()
ADMIN_USER_IDS = config.admin_ids
SUPPORT_CHAT_ID = support_chat_id

def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"

@router_help.message(CommandStart())
async def cmd_start(message: Message, bot):
    if not is_private_chat(message):
        return
        
    welcome_text = "Привет! Добро пожаловать в бота и бла бла бла"
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_start,
        resize_keyboard=True
    )
    await message.answer(welcome_text, reply_markup=keyboard)

@router_help.message(F.text.lower() == "обратная связь")    
async def cmd_obr(message: Message, bot):
    if not is_private_chat(message):
        return
        
    welcome_text = "а ты чето ждал"
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_help,
        resize_keyboard=True
    )
    await message.answer(welcome_text, reply_markup=keyboard)
    

class ComplaintStates(StatesGroup):
    waiting_for_complaint = State()
    waiting_for_confirmation = State()

def save_complaint_to_db(user_id: int, complaint_text: str, tag: str = "жалоба") -> int:
    """Save complaint to database and return ticket ID"""
    try:
        connection = sqlite3.connect('my_database.db')
        cursor = connection.cursor()
        
        # Insert user if not exists (with default status)
        cursor.execute("INSERT OR IGNORE INTO Users (id, status) VALUES (?, 10)", (user_id,))
        
        # Проверка на существование активного тикета с таким же тегом
        cursor.execute("""
            SELECT id FROM Tickets 
            WHERE user_id = ? AND teg = ? AND is_closed = 0
            LIMIT 1
        """, (user_id, tag))
        existing_ticket = cursor.fetchone()
        
        if existing_ticket:
            return -1  # Сигнализируем, что тикет уже существует
            
        # Insert complaint ticket
        cursor.execute(
            "INSERT INTO Tickets (teg, tiket, user_id) VALUES (?, ?, ?)",
            (tag, complaint_text, user_id)
        )
        
        ticket_id = cursor.lastrowid
        connection.commit()
        return ticket_id
    except sqlite3.Error as e:
        logger.error(f"Database error in save_complaint_to_db: {e}")
        return 0
    finally:
        if connection:
            connection.close()

@router_help.message(F.text.lower() == "обжалование")
async def cmd_obh(message: Message, state: FSMContext, bot):
    if not is_private_chat(message):
        return
    
    await state.set_state(ComplaintStates.waiting_for_complaint)
    welcome_text = "опиши свою проблему"
    await message.answer(welcome_text)

@router_help.message(ComplaintStates.waiting_for_complaint)
async def get_complaint_text(message: Message, state: FSMContext, bot):
    complaint_text = message.text
    user_id = message.from_user.id
    
    await state.update_data(complaint_text=complaint_text)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{user_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_{user_id}")
    )
    
    await message.answer(f"Вы написали:\n{complaint_text}\n\nПодтвердите отправку:", reply_markup=keyboard.as_markup())
    await state.set_state(ComplaintStates.waiting_for_confirmation)

@router_help.callback_query(F.data.startswith("confirm_"))
async def confirm_complaint(callback_query: CallbackQuery, state: FSMContext, bot):
    user_data = await state.get_data()
    complaint_text = user_data.get("complaint_text")
    user_id = int(callback_query.data.split("_")[1])
    
    # Проверка на существование активного тикета с таким же тегом
    tag = "жалоба"  # В текущей реализации тег фиксированный
    try:
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM Tickets 
            WHERE user_id = ? AND teg = ? AND is_closed = 0
            LIMIT 1
        """, (user_id, tag))
        existing_ticket = cursor.fetchone()
        conn.close()
        
        if existing_ticket:
            existing_id = existing_ticket[0]
            await bot.send_message(
                user_id, 
                f"CloseOperation\nУ вас уже есть открытый тикет #{existing_id} с этим тегом. "
                "Закройте его перед созданием нового."
            )
            await state.clear()
            await callback_query.answer()
            return
    except sqlite3.Error as e:
        logger.error(f"Database error checking existing ticket: {e}")
    
    # Сохраняем жалобу и получаем ID тикета
    ticket_id = save_complaint_to_db(user_id, complaint_text, tag)
    
    if ticket_id == 0:
        await bot.send_message(user_id, "Произошла ошибка при создании тикета. Попробуйте позже.")
        await state.clear()
        await callback_query.answer()
        return
    
    # Создаем топик в чате поддержки
    try:
        forum_topic = await bot.create_forum_topic(
            chat_id=SUPPORT_CHAT_ID,
            name=f"{tag} • #{ticket_id}"
        )
        topic_id = forum_topic.message_thread_id
        
        # Сохраняем ID топика в БД
        try:
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE Tickets SET topic_id = ? WHERE id = ?", (topic_id, ticket_id))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database error updating topic_id: {e}")
        
        # Формируем информацию о жалобе с командой удаления
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        info_message = (
            f"👤 Пользователь: {user_id}\n"
            f"🕒 Время: {current_time}\n"
            f"🏷 Тег: {tag}\n"
            f"🆔 ID тикета: #{ticket_id}\n"
            f"❌ Для удаления: /delete_{ticket_id}"
        )
        
        # Отправляем информацию и жалобу в топик
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=topic_id,
            text=info_message
        )
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=topic_id,
            text=f"📝 Текст жалобы:\n{complaint_text}"
        )
        
        # Добавляем кнопку закрытия тикета
        close_kb = InlineKeyboardBuilder()
        close_kb.add(
            InlineKeyboardButton(text="CloseOperation", callback_data=f"close_ticket_{ticket_id}")
        )
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=topic_id,
            text="Тикет активен. Нажмите кнопку ниже для закрытия:",
            reply_markup=close_kb.as_markup()
        )
        
        await bot.send_message(user_id, "жалоба отправлена")
    except Exception as e:
        logger.error(f"Error creating topic for user {user_id}: {e}")
        await bot.send_message(user_id, "Произошла ошибка при отправке жалобы. Попробуйте позже.")
    
    await state.clear()
    await callback_query.answer()

@router_help.callback_query(F.data.startswith("cancel_"))
async def cancel_complaint(callback_query: CallbackQuery, state: FSMContext, bot):
    user_id = int(callback_query.data.split("_")[1])
    await bot.send_message(user_id, "жалоба отменена")
    await state.clear()
    await callback_query.answer()

# ================ ОБРАБОТЧИКИ ДЛЯ ДВУСТОРОННЕЙ ПЕРЕСЫЛКИ ================

@router_help.message(F.chat.id == SUPPORT_CHAT_ID)
async def handle_support_response(message: Message, bot):
    """Обработка ответов из чата поддержки"""
    # Игнорируем сообщения не из топиков
    if not message.message_thread_id:
        return
    
    # Находим пользователя по ID топика
    try:
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.user_id, t.is_closed 
            FROM Tickets t 
            WHERE t.topic_id = ?
            ORDER BY t.id DESC 
            LIMIT 1
        """, (message.message_thread_id,))
        result = cursor.fetchone()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in handle_support_response: {e}")
        return
    
    if not result:
        logger.warning(f"Topic {message.message_thread_id} not found in database")
        return
    
    user_id, is_closed = result
    
    # Проверяем, не закрыт ли тикет
    if is_closed:
        try:
            await bot.send_message(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=message.message_thread_id,
                text="⚠️ Этот тикет уже закрыт. Новое сообщение не будет доставлено пользователю."
            )
        except Exception as e:
            logger.error(f"Error sending closed ticket warning: {e}")
        return
    
    # Пересылаем ответ пользователю
    try:
        # Если сообщение содержит медиа
        if message.photo:
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=f"✉️ Ответ от поддержки:\n\n{message.caption or ''}",
                parse_mode="HTML"
            )
        elif message.video:
            await bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=f"✉️ Ответ от поддержки:\n\n{message.caption or ''}",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=f"✉️ Ответ от поддержки:\n\n{message.text}",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error forwarding message to user {user_id}: {e}")

@router_help.message(F.chat.type == "private")
async def handle_user_message(message: Message, bot):
    """Обработка новых сообщений от пользователя"""
    # Игнорируем служебные сообщения и команды
    if message.text and message.text.lower() in ["обратная связь", "обжалование","идеи и предложения","правила"]:
        return
    if message.text and message.text.startswith('/'):
        return

    # Проверяем, есть ли у пользователя активный тикет
    try:
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.topic_id, t.is_closed 
            FROM Tickets t 
            WHERE t.user_id = ? AND t.is_closed = 0
            ORDER BY t.id DESC 
            LIMIT 1
        """, (message.from_user.id,))
        result = cursor.fetchone()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Database error in handle_user_message: {e}")
        return
    
    if not result:
        # Проверяем, есть ли закрытые тикеты
        try:
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id 
                FROM Tickets 
                WHERE user_id = ? AND is_closed = 1
                ORDER BY id DESC 
                LIMIT 1
            """, (message.from_user.id,))
            closed_ticket = cursor.fetchone()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database error checking closed tickets: {e}")
            return
        
        if closed_ticket:
            await message.answer(
                "CloseOperation\nВаш предыдущий тикет закрыт. Для нового вопроса, пожалуйста, создайте новый тикет через меню."
            )
        return  # Нет активного тикета
    
    topic_id, is_closed = result
    
    # Пересылаем сообщение в соответствующий топик
    try:
        # Если сообщение содержит медиа
        if message.photo:
            await bot.send_photo(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=topic_id,
                photo=message.photo[-1].file_id,
                caption=f"💬 Новое сообщение от пользователя ({message.from_user.id}):\n{message.caption or ''}",
                parse_mode="HTML"
            )
        elif message.video:
            await bot.send_video(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=topic_id,
                video=message.video.file_id,
                caption=f"💬 Новое сообщение от пользователя ({message.from_user.id}):\n{message.caption or ''}",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=topic_id,
                text=f"💬 Новое сообщение от пользователя ({message.from_user.id}):\n{message.text}",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error forwarding user message to support chat: {e}")
        await bot.send_message(
            chat_id=message.from_user.id,
            text="Не удалось отправить сообщение. Попробуйте позже."
        )

# ================ ОБРАБОТЧИК ЗАКРЫТИЯ ТИКЕТОВ ================

@router_help.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(callback_query: CallbackQuery, bot):
    """Закрытие тикета администратором с добавлением кнопки удаления топика"""
    # Проверка прав администратора
    if callback_query.from_user.id not in ADMIN_USER_IDS:
        await callback_query.answer("CloseOperation", show_alert=True)
        return
    
    try:
        ticket_id = int(callback_query.data.split("_")[2])
        
        # Обновляем статус тикета в БД
        try:
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE Tickets SET is_closed = 1 WHERE id = ?", (ticket_id,))
            conn.commit()
            
            # Получаем информацию о тикете
            cursor.execute("""
                SELECT user_id, teg, topic_id 
                FROM Tickets 
                WHERE id = ?
            """, (ticket_id,))
            ticket_info = cursor.fetchone()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database error in close_ticket: {e}")
            await callback_query.answer("CloseOperation", show_alert=True)
            return
        
        if not ticket_info:
            await callback_query.answer("CloseOperation", show_alert=True)
            return
        
        user_id, tag, topic_id = ticket_info
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                f"CloseOperation\nВаш тикет #{ticket_id} ({tag}) был закрыт.\nЕсли у вас остались вопросы, создайте новый тикет."
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id} about closed ticket: {e}")
        
        # === ДОБАВЛЕНИЕ КНОПКИ УДАЛЕНИЯ ТОПИКА ===
        delete_button = InlineKeyboardButton(
            text="🗑️ Удалить топик",
            callback_data=f"delete_topic_{ticket_id}"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[delete_button]])
        # ======================================
        
        # Редактируем сообщение с КНОПКОЙ УДАЛЕНИЯ
        try:
            await bot.edit_message_text(
                chat_id=SUPPORT_CHAT_ID,
                message_id=callback_query.message.message_id,
                text=f"CloseOperation\nТикет #{ticket_id} ({tag}) был закрыт администратором {callback_query.from_user.full_name}.",
                reply_markup=markup  # Теперь с кнопкой удаления
            )
            
            # Добавляем уведомление в топик
            await bot.send_message(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=topic_id,
                text=f"CloseOperation\nТикет закрыт. Больше сообщений от пользователя не будут доставляться."
            )
        except Exception as e:
            logger.error(f"Error editing support chat message: {e}")
        
        await callback_query.answer(f"CloseOperation #{ticket_id} закрыт")
        
    except Exception as e:
        logger.error(f"Error closing ticket: {e}")
        await callback_query.answer("CloseOperation", show_alert=True)
        

@router_help.callback_query(F.data.startswith("delete_topic_"))
async def delete_topic(callback_query: CallbackQuery, bot):
    """Удаление топика после закрытия тикета"""
    if callback_query.from_user.id not in ADMIN_USER_IDS:
        await callback_query.answer("Недостаточно прав", show_alert=True)
        return
    
    try:
        ticket_id = int(callback_query.data.split("_")[2])
        
        # Получаем topic_id из БД
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT topic_id FROM Tickets WHERE id = ?", (ticket_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            await callback_query.answer("Топик не найден", show_alert=True)
            return
        
        topic_id = result[0]
        
        # 1. Отправляем сообщение В КОНЕЦ топика
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=topic_id,
            text="🗑️ **Топик будет удален**\n\nВсе данные архивированы. Тема больше не будет принимать сообщения."
        )
        
        # 2. Закрываем форумную тему (аналог "удаления")
        await bot.close_forum_topic(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=topic_id
        )
        
        # 3. Убираем кнопку из основного сообщения
        await bot.edit_message_reply_markup(
            chat_id=SUPPORT_CHAT_ID,
            message_id=callback_query.message.message_id,
            reply_markup=None
        )
        
        await callback_query.answer(f"Топик #{ticket_id} удален и заархивирован")
        
    except Exception as e:
        logger.error(f"Error deleting topic: {e}")
        await callback_query.answer("Ошибка при удалении топика", show_alert=True)

# ================ ОБРАБОТЧИК УДАЛЕНИЯ ТИКЕТОВ ================

@router_help.message(
    F.chat.id == SUPPORT_CHAT_ID,
    F.text.startswith("/delete_")
)
async def delete_ticket_command(message: Message, bot):
    """Удаление тикета через команду в чате поддержки"""
    # Проверка прав администратора
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.reply("CloseOperation")
        return
    
    try:
        # Извлекаем ID тикета из команды
        ticket_id = int(message.text.split("_")[1])
        
        # Получаем информацию о тикете
        try:
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, teg, topic_id 
                FROM Tickets 
                WHERE id = ?
            """, (ticket_id,))
            ticket_info = cursor.fetchone()
            
            if not ticket_info:
                await message.reply("Тикет не найден в базе данных.")
                return
            
            user_id, tag, topic_id = ticket_info
            
            # Удаляем запись из базы данных
            cursor.execute("DELETE FROM Tickets WHERE id = ?", (ticket_id,))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Database error in delete_ticket_command: {e}")
            await message.reply("Произошла ошибка при работе с базой данных")
            return
        
        # Пытаемся закрыть топик
        try:
            await bot.close_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=topic_id
            )
        except Exception as e:
            logger.error(f"Error closing forum topic {topic_id}: {e}")
        
        # Уведомляем пользователя об удалении
        try:
            await bot.send_message(
                user_id,
                f"CloseOperation\nВаш тикет #{ticket_id} ({tag}) был удален.\n"
                "Если у вас остались вопросы, создайте новый тикет."
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id} about deleted ticket: {e}")
        
        # Отправляем подтверждение в чат поддержки
        await message.reply(
            f"CloseOperation #{ticket_id} удален.\n"
            f"Пользователь {user_id} уведомлен об удалении тикета."
        )
        
    except (IndexError, ValueError):
        await message.reply("Неверный формат команды. Используйте /delete_<ID>")
    except Exception as e:
        logger.error(f"Error deleting ticket: {e}")
        await message.reply("Произошла ошибка при удалении тикета")