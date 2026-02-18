import asyncio
from config import BOT_TOKEN
from bot import get_bot, setup_dispatcher

async def main():
    bot = get_bot(BOT_TOKEN)
    dp = setup_dispatcher()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())