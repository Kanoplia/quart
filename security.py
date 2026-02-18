# moderation_router.py
from datetime import timedelta
from aiogram import Router, types
from aiogram.filters import Command
from config import config
from datetime import datetime


router_security = Router()

async def send_report_to_admins(bot, text: str):
    """Отправляет репорт всем админам, кто подписан на бота."""
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass  # Игнорируем ошибки, если админ не подписан

# Парсер времени (например: 1h, 30m, 2d)
def parse_time(time_str: str) -> int | None:
    """
    Преобразует строку времени в секунды.
    Пример: '1h' -> 3600, '30m' -> 1800, '2d' -> 172800
    """
    if not time_str:
        return None

    units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400
    }

    try:
        num = int(time_str[:-1])
        unit = time_str[-1].lower()
        if unit in units:
            return num * units[unit]
    except (ValueError, IndexError):
        pass
    return None

@router_security.message(Command("mute"))
async def cmd_mute(message: types.Message):
    if message.from_user.id not in config.admin_ids: # type: ignore 
        await message.reply("❌ У вас нет прав!")
        return

    args = message.text.split()[1:] # type: ignore
    if not args:
        await message.reply("⚠️ Использование: /mute [время] [причина]")
        return

    time_str = args[0]
    duration = parse_time(time_str)

    if not duration:
        reason = " ".join(args) or "не указана"
        until_date = None
    else:
        reason = " ".join(args[1:]) or "не указана"
        until_date = message.date.timestamp() + duration

    user_id = message.reply_to_message.from_user.id if message.reply_to_message else None # type: ignore
    if not user_id:
        await message.reply("⚠️ Ответьте на сообщение пользователя.")
        return

    success_chats = []
    failed_chats = []

    for chat_id in config.chat_ids:
        try:
            await message.bot.restrict_chat_member( # type: ignore
                chat_id=chat_id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=False),
                until_date=until_date # type: ignore 
            )
            success_chats.append(str(chat_id))
        except Exception as e:
            failed_chats.append(f"{chat_id}: {e}")

    # Удаление команды админа
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем репорт админам
    until_text = f" до {datetime.fromtimestamp(int(until_date)).strftime('%d.%m.%Y %H:%M:%S')}" if until_date else ""
    report_text = f"""
🔊 [MUTE] Пользователь `{user_id}` получил мут{until_text}.
— Причина: {reason}
— Успешно в чатах: {', '.join(success_chats) if success_chats else 'нет'}
— Ошибки: {', '.join(failed_chats) if failed_chats else 'нет'}
    """.strip()

    await send_report_to_admins(message.bot, report_text)

@router_security.message(Command("unmute"))
async def cmd_unmute(message: types.Message):
    if message.from_user.id not in config.admin_ids: # type: ignore
        await message.reply("❌ У вас нет прав!")
        return

    user_id = message.reply_to_message.from_user.id if message.reply_to_message else None # type: ignore
    if not user_id:
        await message.reply("⚠️ Ответьте на сообщение пользователя.")
        return

    success_chats = []
    failed_chats = []

    for chat_id in config.chat_ids:
        try:
            await message.bot.restrict_chat_member( # type: ignore
                chat_id=chat_id,
                user_id=user_id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_send_polls=True
                )
            )
            success_chats.append(str(chat_id))
        except Exception as e:
            failed_chats.append(f"{chat_id}: {e}")

    # Удаление команды админа
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем репорт админам
    report_text = f"""
🔊 [UNMUTE] Пользователь `{user_id}` размучен.
— Успешно в чатах: {', '.join(success_chats) if success_chats else 'нет'}
— Ошибки: {', '.join(failed_chats) if failed_chats else 'нет'}
    """.strip()

    await send_report_to_admins(message.bot, report_text)

@router_security.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if message.from_user.id not in config.admin_ids: # type: ignore
        await message.reply("❌ У вас нет прав!")
        return

    args = message.text.split()[1:] # type: ignore
    if not args:
        await message.reply("⚠️ Использование: /ban [время] [причина]")
        return

    time_str = args[0]
    duration = parse_time(time_str)

    if not duration:
        reason = " ".join(args) or "не указана"
        until_date = None
    else:
        reason = " ".join(args[1:]) or "не указана"
        until_date = message.date.timestamp() + duration

    user_id = message.reply_to_message.from_user.id if message.reply_to_message else None # type: ignore
    if not user_id:
        await message.reply("⚠️ Ответьте на сообщение пользователя.")
        return

    success_chats = []
    failed_chats = []

    for chat_id in config.chat_ids:
        try:
            await message.bot.ban_chat_member( # type: ignore
                chat_id=chat_id,
                user_id=user_id,
                until_date=until_date # type: ignore
            )
            success_chats.append(str(chat_id))
        except Exception as e:
            failed_chats.append(f"{chat_id}: {e}")

    # Удаление команды админа
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем репорт админам
    until_text  = f" до {datetime.fromtimestamp(int(until_date)).strftime('%d.%m.%Y %H:%M:%S')}" if until_date else ""
    report_text = f"""
🔨 [BAN] Пользователь `{user_id}` заблокирован{until_text}.
— Причина: {reason}
— Успешно в чатах: {', '.join(success_chats) if success_chats else 'нет'}
— Ошибки: {', '.join(failed_chats) if failed_chats else 'нет'}
    """.strip()

    await send_report_to_admins(message.bot, report_text)

@router_security.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if message.from_user.id not in config.admin_ids: # type: ignore
        await message.reply("❌ У вас нет прав!")
        return

    user_id = message.reply_to_message.from_user.id if message.reply_to_message else None # type: ignore
    if not user_id:
        await message.reply("⚠️ Ответьте на сообщение пользователя.")
        return

    success_chats = []
    failed_chats = []

    for chat_id in config.chat_ids:
        try:
            await message.bot.unban_chat_member(chat_id=chat_id, user_id=user_id) # type: ignore
            success_chats.append(str(chat_id))
        except Exception as e:
            failed_chats.append(f"{chat_id}: {e}")

    # Удаление команды админа
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем репорт админам
    report_text = f"""
✅ [UNBAN] Пользователь `{user_id}` разбанен.
— Успешно в чатах: {', '.join(success_chats) if success_chats else 'нет'}
— Ошибки: {', '.join(failed_chats) if failed_chats else 'нет'}
    """.strip()

    await send_report_to_admins(message.bot, report_text)
    
@router_security.message(Command("report"))
async def cmd_report(message: types.Message):

    reported_message = message.reply_to_message
    reporter = message.from_user
    chat_title = message.chat.title or "Приватный чат"
    message_link = f"https://t.me/c/{str(message.chat.id)[4:]}/{reported_message.message_id}"  # Для супергрупп

    if str(message.chat.id).startswith("-100"):  # Если это супергруппа
        message_link = f"https://t.me/c/{str(message.chat.id)[4:]}/{reported_message.message_id}"
    else:
        message_link = "Недоступно (приватный чат)"

    report_text = f"""
🚨 Жалоба от пользователя: 
— ID: {reporter.id} 
— Имя: {reporter.full_name}
— Username: @{reporter.username or 'не указан'} 

💬 Сообщение: {reported_message.text or 'медиа/другое содержимое'}
🔗 Ссылка: {message_link}
🏷️ Чат: {chat_title}
    """.strip()

    for admin_id in config.admin_ids:
        try:
            await message.bot.send_message(admin_id, report_text) # type: ignore
        except Exception:
            pass

    await message.reply("✅ Ваша жалоба отправлена администраторам.")
    
    try:
        await message.delete()
    except Exception:
        pass