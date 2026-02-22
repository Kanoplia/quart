from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from collections import defaultdict
from config import config
# Добавлен импорт CommandObject
from aiogram.filters.command import CommandObject

router_quiz = Router()

# Временное хранилище квизов (ключ - chat_id)
quiz_data = defaultdict(lambda: {
    'is_active': False,
    'scores': {}  # {user_id: {'score': int, 'name': str}}
})

def is_allowed_chat(chat_id: int) -> bool:
    """Проверяет разрешен ли чат для работы бота"""
    return chat_id in config.chat_ids

def is_admin(user_id: int) -> bool:
    """Проверяет является ли пользователь администратором"""
    return user_id in config.admin_ids

@router_quiz.message(Command("start_quiz"))
async def cmd_start_quiz(message: Message):
    """Активирует квиз без привязки к вопросу"""
    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return
    
    chat_id = message.chat.id
    quiz_data[chat_id]['is_active'] = True
    quiz_data[chat_id]['scores'] = {}  # Очищаем предыдущие результаты
    
    await message.answer("✅ Квиз активирован!\n"
                         "Администратор может начинать задавать вопросы вручную.")

@router_quiz.message(Command("stop_quiz"))
async def cmd_stop_quiz(message: Message):
    """Деактивирует квиз"""
    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return
    
    chat_id = message.chat.id
    if not quiz_data[chat_id]['is_active']:
        await message.answer("❌ Квиз не активен")
        return
    
    quiz_data[chat_id]['is_active'] = False
    await message.answer("🏁 Квиз остановлен. Результаты сохранены.")

@router_quiz.message(Command("top"))
async def cmd_top(message: Message):
    """Показывает топ участников"""
    if not is_allowed_chat(message.chat.id):
        return
    
    chat_id = message.chat.id
    scores = quiz_data[chat_id]['scores']
    
    if not scores:
        await message.answer("📊 Топ игроков пуст")
        return
    
    # Сортируем по баллам
    top = sorted(
        scores.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:10]
    
    result = "🏆 ТОП игроков:\n\n"
    for i, (user_id, data) in enumerate(top, 1):
        # Исправлено склонение слова "балл"
        points = data['score']
        if points % 10 == 1 and points % 100 != 11:
            points_str = f"{points} балл"
        elif 2 <= points % 10 <= 4 and (points % 100 < 10 or points % 100 >= 20):
            points_str = f"{points} балла"
        else:
            points_str = f"{points} баллов"
        
        result += f"{i}. @{data['name']} — {points_str}\n"
    
    await message.answer(result)

@router_quiz.message(Command("approve"), F.reply_to_message)
async def cmd_approve(message: Message, command: CommandObject):
    """Начисляет баллы пользователю, на чье сообщение ответил админ"""
    if not is_allowed_chat(message.chat.id) or not is_admin(message.from_user.id):
        return
    
    chat_id = message.chat.id
    if not quiz_data[chat_id]['is_active']:
        await message.answer("❌ Квиз не активен")
        return
    
    # Проверка на сообщение из канала
    if message.reply_to_message.sender_chat:
        await message.answer("❌ Нельзя начислять баллы сообщению из канала")
        return
    
    # Получаем и обрабатываем аргументы (удаляем лишние пробелы)
    points_str = command.args.strip() if command.args else ""
    if not points_str or not points_str.isdigit():
        await message.answer("❗ Укажите количество баллов. Пример: /approve 5")
        return
    
    points = int(points_str)
    if points <= 0:
        await message.answer("❗ Количество баллов должно быть положительным числом")
        return
    
    # Получаем данные пользователя
    user = message.reply_to_message.from_user
    user_id = user.id
    name = user.username or user.first_name
    
    # Инициализируем запись если нужно
    if user_id not in quiz_data[chat_id]['scores']:
        quiz_data[chat_id]['scores'][user_id] = {'score': 0, 'name': name}
    
    # Начисляем баллы
    quiz_data[chat_id]['scores'][user_id]['score'] += points
    quiz_data[chat_id]['scores'][user_id]['name'] = name  # Обновляем имя при изменении
    
    # Правильное склонение для баллов
    current_score = quiz_data[chat_id]['scores'][user_id]['score']
    if current_score % 10 == 1 and current_score % 100 != 11:
        points_str_current = f"{current_score} балл"
    elif 2 <= current_score % 10 <= 4 and (current_score % 100 < 10 or current_score % 100 >= 20):
        points_str_current = f"{current_score} балла"
    else:
        points_str_current = f"{current_score} баллов"
    
    # Отправляем подтверждение
    await message.answer(f"✅ {name} получил(а) {points} балл(ов)!\n"
                         f"Теперь у него {points_str_current}")