# config.py
import os
from dataclasses import dataclass

@dataclass
class BotConfig:
    token: str
    base_url: str
    admin_ids: list[int]
    chat_ids: list[int]

config = BotConfig(
        token="8391779709:AAGiKML1NEVLD-MuSBXsCRj5szW9DwxsXbo",  # Вместо os.getenv("BOT_TOKEN")
        base_url="http://127.0.0.1:8000",
        admin_ids=[1167279221],  # Укажите реальные ID администраторов
        chat_ids=[-1003484286449,-1003456437345]  # Укажите ID чатов, где работает бот
   
    )
support_chat_id = -1003567400108
BOT_TOKEN = config.token