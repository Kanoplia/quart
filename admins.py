from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
import sqlite3
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config
import logging
from datetime import datetime, timedelta
import asyncio
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.token)
router_adm = Router()

adm_chat_id = config.adm_chat_id

async def get_username_by_id(user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        if user.username:
            return f"@{user.username}"
        elif user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        else:
            return user.first_name or f"ID: {user_id}"
    except Exception:
        return f"ID: {user_id}"
    
async def display_results(session_id: int):
    conn = sqlite3.connect('admins.db')
    cursor = conn.cursor()

    try:
        # Получаем конфигурацию ролей
        cursor.execute('SELECT roles_config FROM voting_sessions WHERE id = ?', (session_id,))
        config_row = cursor.fetchone()
        if not config_row or not config_row[0]:
            await bot.send_message(adm_chat_id, "Не удалось загрузить конфигурацию голосования.")
            return

        roles_config = json.loads(config_row[0])

        # Получаем все голоса
        cursor.execute('''
            SELECT role_type, candidate_id, COUNT(*) as votes 
            FROM votes 
            WHERE session_id = ? 
            GROUP BY role_type, candidate_id
        ''', (session_id,))
        raw_results = cursor.fetchall()

        # Группируем голоса по ролям
        results_by_role = {}
        for role_type, cand_id, vote_count in raw_results:
            if role_type not in results_by_role:
                results_by_role[role_type] = []
            results_by_role[role_type].append((cand_id, vote_count))

        # Формируем сообщение
        message_lines = ["📊 Результаты голосования:\n"]

        for role_name in roles_config.keys():  # Используем роли, которые были в голосовании
            if role_name not in results_by_role:
                message_lines.append(f"🔹 {role_name}: нет голосов")
                continue

            votes = results_by_role[role_name]
            # Сортируем по количеству голосов (по убыванию)
            votes.sort(key=lambda x: x[1], reverse=True)

            winner_id, max_votes = votes[0]
            if winner_id is None:
                winner_text = "❌ Никто (голосовали против всех)"
            else:
                username = await get_username_by_id(winner_id)
                winner_text = f"👑 {username}"

            message_lines.append(f"🔹 {role_name}:")
            message_lines.append(f"   Победитель: {winner_text} ({max_votes} голосов)")
            message_lines.append("")

        await bot.send_message(adm_chat_id, "\n".join(message_lines))

    except Exception as e:
        logger.error(f"Ошибка при выводе результатов: {e}")
        await bot.send_message(adm_chat_id, "❌ Ошибка при подсчёте результатов.")
    finally:
        conn.close()
    
    
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

# Команда для обновления списка админов (работает только в админ чате)
@router_adm.message(Command('update_admins'))
async def cmd_update_admins(message: types.Message):
    logger.info(f"Получена команда /update_admins от пользователя {message.from_user.id}")
    if message.chat.id != adm_chat_id:
        logger.info("Команда /update_admins вызвана не в админ чате, игнорируем")
        return
    
    await save_all_current_admins(adm_chat_id)
    await message.answer("Список администраторов обновлен.")

# Хендлер для команды /admin - выводит список админов и их ролей (работает только в админ чате)
@router_adm.message(Command('admin'))
async def cmd_admin_list(message: types.Message):
    logger.info(f"Получена команда /admin от пользователя {message.from_user.id}")
    if message.chat.id != adm_chat_id:
        logger.info("Команда /admin вызвана не в админ чате, игнорируем")
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

@router_adm.message(Command('get'))
async def cmd_create_voting(message: types.Message):
    logger.info(f"Получена команда /get от пользователя {message.from_user.id}")

    if message.chat.id != adm_chat_id:
        logger.info("Команда /get вызвана не в админ чате, игнорируем")
        return

    await save_all_current_admins(adm_chat_id)

    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            await message.answer("Используйте: /get <время> <длительность в часах>")
            return

        target_time_str = args[0]  # например, "11:00"
        duration_hours = int(args[1])

        # Вычисляем дату и время начала голосования
        now = datetime.now()
        hour, minute = map(int, target_time_str.split(':')[:2]) if ':' in target_time_str else (int(target_time_str), 0)

        start_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start_datetime <= now:
            start_datetime += timedelta(days=1)

        end_datetime = start_datetime + timedelta(hours=duration_hours)

        # Получаем список админов
        conn = sqlite3.connect('admins.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, role_name FROM admins WHERE chat_id = ?', (adm_chat_id,))
        admins = cursor.fetchall()
        conn.close()

        if not admins:
            await message.answer("Нет администраторов для голосования.")
            return

        # Иерархия ролей
        role_hierarchy = [
            "Око Совета",
            "Клинок Совета",
            "Дозор Совета",
            "Тень Совета"
        ]

        # Правила повышения
        promotion_path = {
            "Око Совета": "Клинок Совета",
            "Клинок Совета": "Дозор Совета",
            "Дозор Совета": "Тень Совета"
        }

        admin_roles = {user_id: role for user_id, role in admins}
        roles_config = {}

        # Заполняем кандидатов для повышаемых ролей
        for target_role, required_role in promotion_path.items():
            candidates = [
                uid for uid, current_role in admin_roles.items()
                if current_role == required_role
            ]
            roles_config[target_role] = candidates

        # Премия — все могут быть кандидатами
        all_admin_ids = [uid for uid, _ in admins]
        roles_config["Премия"] = all_admin_ids

        # Исключаем роли без кандидатов
        available_roles = {role: candidates for role, candidates in roles_config.items() if candidates}

        if not available_roles:
            await message.answer("Нет подходящих кандидатов для голосования.")
            return

        conn = sqlite3.connect('admins.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO voting_sessions 
            (session_type, target_date, duration_hours, start_time, end_time, status, roles_config)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "role_assignment",
            target_time_str,
            duration_hours,
            start_datetime,
            end_datetime,
            "pending",  
            json.dumps(available_roles)
        ))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await message.answer(f"Сессия голосования запланирована. ID: <code>{session_id}</code>", parse_mode="HTML")

        voting_message_id = None

        # начало голосования
        async def start_voting_task():
            nonlocal voting_message_id
            time_to_wait = (start_datetime - datetime.now()).total_seconds()
            await asyncio.sleep(max(0, time_to_wait))

            # Переподключаемся к БД
            conn = sqlite3.connect('admins.db')
            cursor = conn.cursor()
            cursor.execute('SELECT roles_config FROM voting_sessions WHERE id = ?', (session_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                logger.error("Сессия голосования не найдена при старте")
                return

            roles_config = json.loads(row[0])

            # Создаём клавиатуру
            keyboard_builder = InlineKeyboardBuilder()
            for role_name in roles_config.keys():
                callback_data = f"select_role_{role_name.replace(' ', '_')}"
                keyboard_builder.button(
                    text=f"Голосовать за {role_name}",
                    callback_data=callback_data
                )
            keyboard_builder.adjust(1)
            keyboard = keyboard_builder.as_markup()

            # Отправляем сообщение
            try:
                voting_message = await message.bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"✅ <b>Голосование началось!</b>\n\n"
                        f"🕒 Начало: <b>{start_datetime.strftime('%H:%M %d.%m.%Y')}</b>\n"
                        f"🔚 Завершение: <b>{end_datetime.strftime('%H:%M %d.%m.%Y')}</b>\n"
                        f"⏱️ Длительность: <b>{duration_hours} часа(ов)</b>\n\n"
                        "Выберите роль, за которую хотите проголосовать:"
                    ),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                # Закрепляем сообщение
                await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=voting_message.message_id)

                # Обновляем статус
                conn = sqlite3.connect('admins.db')
                cursor = conn.cursor()
                cursor.execute('UPDATE voting_sessions SET status = ? WHERE id = ?', ('active', session_id))
                conn.commit()
                conn.close()

                # Сохраняем ID в память
                voting_message_id = voting_message.message_id

            except Exception as e:
                logger.error(f"Не удалось отправить или закрепить сообщение: {e}")

        # Завершение голосования
        async def end_voting_task():
            time_to_wait = (end_datetime - datetime.now()).total_seconds()
            await asyncio.sleep(max(0, time_to_wait))

            # Обновляем статус
            conn = sqlite3.connect('admins.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE voting_sessions SET status = ? WHERE id = ?', ('finished', session_id))
            conn.commit()
            conn.close()

            # Открепляем сообщение, если оно есть
            if voting_message_id:
                try:
                    await message.bot.unpin_chat_message(chat_id=message.chat.id, message_id=voting_message_id)
                except Exception as e:
                    logger.warning(f"Не удалось открепить сообщение: {e}")

            # Уведомление о завершении
            await message.bot.send_message(
                chat_id=message.chat.id,
                text="🏁 <b>Голосование завершено!</b>",
                parse_mode="HTML"
            )
            # Вызов подсчёта результатов
            await display_results(session_id)

        # Запускаем задачи
        asyncio.create_task(start_voting_task())
        asyncio.create_task(end_voting_task())

    except Exception as e:
        logger.error(f"Ошибка при создании голосования: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


# Заглушка для функции display_results
async def display_results(session_id: int):
    try:
        conn = sqlite3.connect('admins.db')
        cursor = conn.cursor()
        cursor.execute('SELECT vote_data FROM votes WHERE session_id = ?', (session_id,))
        votes = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при отображении результатов: {e}")
        
        
# Команда для удаления голосования
@router_adm.message(Command('del_voting'))
async def cmd_delete_voting(message: types.Message):
    logger.info(f"Получена команда /del_voting от пользователя {message.from_user.id}")
    if message.chat.id != adm_chat_id:
        logger.info("Команда /del_voting вызвана не в админ чате, игнорируем")
        return
    
    try:
        args = message.text.split()[1:]
        if not args:
            await message.answer("Используйте: /del_voting <ID_сессии>")
            return
        
        session_id = int(args[0])
        
        # Удаляем сессию голосования и связанные голоса
        conn = sqlite3.connect('admins.db')
        cursor = conn.cursor()
        
        # Удаляем голоса, связанные с сессией
        cursor.execute('DELETE FROM votes WHERE session_id = ?', (session_id,))
        # Удаляем саму сессию
        cursor.execute('DELETE FROM voting_sessions WHERE id = ?', (session_id,))
        
        conn.commit()
        conn.close()
        
        await message.answer(f"Голосование с ID {session_id} удалено.")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении голосования: {e}")
        await message.answer(f"Ошибка при удалении голосования: {str(e)}")