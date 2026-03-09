import asyncio
from config import BOT_TOKEN
from bot import get_bot, setup_dispatcher
from database.storage import init_db  
from web import keep_alive


async def main():
    if not init_db():
        print("Critical error: Failed to initialize database. Exiting...")
        return
    
    keep_alive()
    
    bot = get_bot(BOT_TOKEN)
    dp = setup_dispatcher()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())