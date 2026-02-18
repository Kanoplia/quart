from .keyboart import *
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup
from config import config 
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import sqlite3 
from aiogram.utils.keyboard import InlineKeyboardBuilder

router_help = Router()
ADMIN_USER_IDS = config.admin_ids


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

def save_complaint_to_db(user_id: int, complaint_text: str, tag: str = "жалоба"):
    """Save complaint to database"""
    connection = sqlite3.connect('my_database.db')
    cursor = connection.cursor()
    
    # Insert user if not exists (with default status)
    cursor.execute("INSERT OR IGNORE INTO Users (id, status) VALUES (?, 10)", (user_id,))
    
    # Insert complaint ticket
    cursor.execute(
        "INSERT INTO Tickets (teg, tiket, user_id) VALUES (?, ?, ?)",
        (tag, complaint_text, user_id)
    )
    
    connection.commit()
    connection.close()

@router_help.message(F.text.lower() == "обжалование")
async def cmd_obh(message: Message, state: FSMContext):
    if not is_private_chat(message):
        return
    
    await state.set_state(ComplaintStates.waiting_for_complaint)
    welcome_text = "опиши свою проблему"
    await message.answer(welcome_text)

@router_help.message(ComplaintStates.waiting_for_complaint)
async def get_complaint_text(message: Message, state: FSMContext):
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
async def confirm_complaint(callback_query, state: FSMContext, bot):
    user_data = await state.get_data()
    complaint_text = user_data.get("complaint_text")
    user_id = int(callback_query.data.split("_")[1])
    
    save_complaint_to_db(user_id, complaint_text)
    
    await bot.send_message(user_id, "жалоба отправлена")
    await state.clear()
    await callback_query.answer()

@router_help.callback_query(F.data.startswith("cancel_"))
async def cancel_complaint(callback_query, state: FSMContext, bot):
    user_id = int(callback_query.data.split("_")[1])
    await bot.send_message(user_id, "жалоба отменена")
    await state.clear()
    await callback_query.answer()