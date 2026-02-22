# bot.py
from aiogram import Bot, Dispatcher
from security import router_security
from help.help import router_help
from database.init import router_base
from quiz.quiz import router_quiz

def get_bot(token: str) -> Bot:
    return Bot(token=token)

def setup_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    dp.include_router(router_security)
    dp.include_router(router_help)
    dp.include_router(router_base)
    dp.include_router(router_quiz)
    
    return dp