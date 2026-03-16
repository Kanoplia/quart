# config.py
import os
from dataclasses import dataclass

@dataclass
class BotConfig:
    token: str
    base_url: str
    admin_ids: list[int]
    chat_ids: list[int]
    support_chat_id: int
    commands: list[str]
    adm_chat_id: int
    db: str

config = BotConfig(
    token="8391779709:AAGiKML1NEVLD-MuSBXsCRj5szW9DwxsXbo", 
    base_url="http://127.0.0.1:8000",
    admin_ids=[1167279221,1599926314],  
    chat_ids=[-1003484286449,-1003456437345],
    support_chat_id = -1003567400108,
    commands=['обратная связь','жалоба','обжалование','правила','идеи и предложения'],
    adm_chat_id= -1003567400108,
    db= 'my_database.db'
    )

BOT_TOKEN = config.token