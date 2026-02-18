from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton,ReplyKeyboardMarkup
import sqlite3 

router_base = Router()


@router_base.message(CommandStart())
async def cmd_start(message: Message, bot):
    try:
        conn = sqlite3.connect('my_database.db')
    except:
        print('с базой хуйня какая то')
