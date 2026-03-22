from aiogram import Bot, types, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery,InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from config import config
import logging
from datetime import datetime, timedelta
import asyncio
import json
import pytz
import re


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.token)
router_adm = Router()

adm_chat_id = config.adm_chat_id

USER_CACHE = {}

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
    conn = sqlite3.connect(config.db)
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
    conn = sqlite3.connect(config.db)
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
    conn = sqlite3.connect(config.db)
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


async def validate_and_calculate_times(time_str: str, duration_hours: int):
    try:
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        hour, minute = map(int, time_str.split(':'))
        start_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start_datetime <= now:
            start_datetime += timedelta(days=1)
        end_datetime = start_datetime + timedelta(hours=duration_hours)
        return start_datetime, end_datetime
    except ValueError:
        return None, None
    
    
async def build_roles_configuration(chat_id: int):
    conn = sqlite3.connect(config.db)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, role_name FROM admins WHERE chat_id = ?', (chat_id,))
    admins = cursor.fetchall()
    conn.close()

    if not admins:
        return {}

    role_hierarchy = ["Око Совета", "Клинок Совета", "Дозор Совета", "Тень Совета"]
    promotion_path = {
        "Око Совета": "Клинок Совета",
        "Клинок Совета": "Дозор Совета",
        "Дозор Совета": "Тень Совета"
    }

    admin_roles = {uid: role for uid, role in admins}
    roles_config = {}

    for target_role, required_role in promotion_path.items():
        candidates = [uid for uid, current_role in admin_roles.items() if current_role == required_role]
        roles_config[target_role] = candidates

    all_admin_ids = [uid for uid, _ in admins]
    roles_config["Премия"] = all_admin_ids

    return {role: candidates for role, candidates in roles_config.items() if candidates}


async def create_voting_session(target_time: str, duration: int, start_dt, end_dt, roles_config: dict):
    try:
        conn = sqlite3.connect(config.db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO voting_sessions 
            (session_type, target_date, duration_hours, start_time, end_time, status, roles_config, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "role_assignment",
            target_time,
            duration,
            start_dt,
            end_dt,
            "pending",
            json.dumps(roles_config),
            None
        ))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    except Exception as e:
        logger.error(f"Ошибка при сохранении сессии в БД: {e}")
        return None
    
    
async def start_voting_task(session_id: int, bot):
    # Получаем данные сессии
    conn = sqlite3.connect(config.db)
    cursor = conn.cursor()
    cursor.execute('SELECT start_time, end_time, duration_hours, roles_config FROM voting_sessions WHERE id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        logger.error("Сессия голосования не найдена при старте")
        return

    start_time, end_time, duration, roles_config_json = row
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    roles_config = json.loads(roles_config_json)

    # Ждём нужного времени
    delay = (start_dt - datetime.now(pytz.timezone('Europe/Moscow'))).total_seconds()
    await asyncio.sleep(max(0, delay))

    keyboard_builder = InlineKeyboardBuilder()
    for role_name in roles_config.keys():
        callback_data = f"select_role_{role_name.replace(' ', '_')}"
        keyboard_builder.button(
            text=f"Голосовать за {role_name}",
            callback_data=callback_data
        )
    keyboard_builder.adjust(1)
    keyboard = keyboard_builder.as_markup()

    try:
        voting_message = await bot.send_message(
            chat_id=adm_chat_id,
            text=(
                f"✅ <b>Голосование началось!</b>\n\n"
                f"🕒 Начало: <b>{start_dt.strftime('%H:%M %d.%m.%Y')}</b>\n"
                f"🔚 Завершение: <b>{end_dt.strftime('%H:%M %d.%m.%Y')}</b>\n"
                f"⏱️ Длительность: <b>{duration} часа(ов)</b>\n\n"
                "Выберите роль, за которую хотите проголосовать:"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await bot.pin_chat_message(chat_id=adm_chat_id, message_id=voting_message.message_id)

        conn = sqlite3.connect(config.db)
        cursor = conn.cursor()
        cursor.execute('UPDATE voting_sessions SET status = ?, message_id = ? WHERE id = ?',
                       ('active', voting_message.message_id, session_id))
        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Не удалось отправить или закрепить сообщение: {e}")        


async def end_voting_task(session_id: int, bot):
    conn = sqlite3.connect(config.db)
    cursor = conn.cursor()
    cursor.execute('SELECT end_time, message_id FROM voting_sessions WHERE id = ?', (session_id,))
    row = cursor.fetchone()

    if not row:
        logger.error("Сессия голосования не найдена при завершении")
        conn.close()
        return

    end_time_str, pinned_msg_id = row
    end_dt = datetime.fromisoformat(end_time_str)
    conn.close()

    delay = (end_dt - datetime.now(pytz.timezone('Europe/Moscow'))).total_seconds()
    await asyncio.sleep(max(0, delay))

    # Открепление сообщения
    if pinned_msg_id:
        try:
            await bot.unpin_chat_message(chat_id=adm_chat_id, message_id=pinned_msg_id)
        except Exception as e:
            logger.warning(f"Не удалось открепить сообщение: {e}")

    # Обновление статуса
    conn = sqlite3.connect(config.db)
    cursor = conn.cursor()
    cursor.execute('UPDATE voting_sessions SET status = ? WHERE id = ?', ('finished', session_id))
    conn.commit()
    conn.close()

    # Уведомление
    await bot.send_message(
        chat_id=adm_chat_id,
        text="🏁 <b>Голосование завершено!</b>",
        parse_mode="HTML"
    )

    # Вызов подсчёта результатов
    await display_results(session_id)


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

        target_time_str = args[0]
        duration_hours = int(args[1])

        # Валидация времени
        start_datetime, end_datetime = await validate_and_calculate_times(target_time_str, duration_hours)
        if not start_datetime:
            await message.answer("❌ Укажите время в формате ЧЧ:ММ, например 11:00.")
            return

        # Получение админов и конфигурации ролей
        roles_config = await build_roles_configuration(adm_chat_id)
        if not roles_config:
            await message.answer("Нет подходящих кандидатов для голосования.")
            return

        # Создание сессии в БД
        session_id = await create_voting_session(
            target_time=target_time_str,
            duration=duration_hours,
            start_dt=start_datetime,
            end_dt=end_datetime,
            roles_config=roles_config
        )
        if not session_id:
            await message.answer("❌ Не удалось создать сессию голосования.")
            return

        await message.answer(f"Сессия голосования запланирована. ID: <code>{session_id}</code>", parse_mode="HTML")

        # Запуск фоновых задач
        asyncio.create_task(start_voting_task(session_id, message.bot))
        asyncio.create_task(end_voting_task(session_id, message.bot))

    except Exception as e:
        logger.error(f"Ошибка при создании голосования: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


def escape_md(text: str) -> str:
    if not text:
        return ""
    for ch in '_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, '\\' + ch)
    return text

async def get_cached_user_info(user_id: int):
    """Получает информацию о пользователе, кэшируя её."""
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]

    try:
        user = await bot.get_chat(user_id)
        USER_CACHE[user_id] = {"full_name": user.full_name, "username": user.username}
        return USER_CACHE[user_id]
    except Exception:
        return None

@router_adm.callback_query(F.data.startswith("select_role_"))
async def handle_select_role_callback(callback: CallbackQuery):
    parts = callback.data.split("_", 2)
    if len(parts) != 3:
        await callback.answer("Неверные данные.")
        return

    promotion_path = {
        "Око Совета": "Клинок Совета",
        "Клинок Совета": "Дозор Совета",
        "Дозор Совета": "Тень Совета",
        "Премия": "Премия"
    }

    role_key = parts[2].replace('_', ' ')
    if role_key not in promotion_path:
        await callback.answer("Неизвестная роль.")
        return

    role_name = promotion_path[role_key]
    chat_id = callback.message.chat.id

    conn = None
    try:
        conn = sqlite3.connect(config.db)
        cursor = conn.cursor()

        if role_name != "Премия":
            cursor.execute('''
                SELECT user_id FROM admins WHERE chat_id = ? AND role_name = ?
            ''', (chat_id, role_name))
            admin_records = cursor.fetchall()
        else:
            cursor.execute('''SELECT user_id FROM admins WHERE chat_id = ?''', (chat_id,))
            admin_records = cursor.fetchall()

            # Фильтрация ботов
            filtered_admins = []
            for (user_id,) in admin_records:
                try:
                    chat = await bot.get_chat(user_id)
                    username = chat.username
                    if username and username.lower().endswith('bot'):
                        continue
                    else:
                        filtered_admins.append((user_id,))
                except Exception:
                    pass
            admin_records = filtered_admins

        keyboard = InlineKeyboardBuilder()

        if not admin_records:
            text = f"🚫 Нет администраторов с ролью *{escape_md(role_name)}*."
        else:
            async def fetch_user_info(user_id_tuple):
                user_id = user_id_tuple[0]
                try:
                    user_info = await get_cached_user_info(user_id)
                    if user_info:
                        full_name = escape_md(user_info["full_name"])
                        username = user_info["username"]
                        display_name = f"@{escape_md(username)}" if username else full_name
                        return user_id, display_name
                    else:
                        return user_id, f"Пользователь [ID: {user_id}]"
                except Exception:
                    return user_id, f"Пользователь [ID: {user_id}]"

            results = await asyncio.gather(*[fetch_user_info(record) for record in admin_records])

            # Добавляем кнопки для каждого админа
            for user_id, display_name in results:
                # Пример callback_data: admin_profile_123456789
                button = InlineKeyboardButton(
                    text=display_name,
                    callback_data=f"admin_profile_{user_id}"
                )
                keyboard.add(button)

            # Кнопка "Назад" — одна под всеми
            back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data="show_admin_roles")
            keyboard.add(back_button)
            keyboard.adjust(1)  # Каждая кнопка — в отдельной строке

            escaped_role_name = escape_md(role_name)
            text = f"👥 *Выберите администратора из роли «{escaped_role_name}»:*"

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard.as_markup(),
            parse_mode="MarkdownV2"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при отображении админов по роли: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)
    finally:
        if conn:
            conn.close()

@router_adm.callback_query(F.data == "show_admin_roles")
async def show_voting_roles(callback: CallbackQuery):
    # Получаем активную сессию голосования
    conn = sqlite3.connect(config.db)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT roles_config, end_time FROM voting_sessions 
        WHERE status = 'active' AND message_id = ?
    ''', (callback.message.message_id,))
    row = cursor.fetchone()

    if not row:
        await callback.answer("❌ Голосование завершено или не найдено.")
        await callback.message.delete()
        conn.close()
        return

    roles_config_json, end_time_str = row
    roles_config = json.loads(roles_config_json)
    end_dt = datetime.fromisoformat(end_time_str)

    conn.close()

    
    keyboard_builder = InlineKeyboardBuilder()
    for role_name in roles_config.keys():
        callback_data = f"select_role_{role_name.replace(' ', '_')}"
        keyboard_builder.button(
            text=f"Голосовать за {role_name}",
            callback_data=callback_data
        )
    keyboard_builder.adjust(1)
    

    keyboard = keyboard_builder.as_markup()

    try:
        await callback.message.edit_text(
            text=(
                f"✅ <b>Голосование активно!</b>\n\n"
                f"🔚 Завершение: <b>{end_dt.strftime('%H:%M %d.%m.%Y')}</b>\n\n"
                "Выберите роль, за которую хотите проголосовать:"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Не удалось обновить меню: {e}")
        await callback.answer("Ошибка при возврате к меню.")
        
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
        conn = sqlite3.connect(config.db)
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