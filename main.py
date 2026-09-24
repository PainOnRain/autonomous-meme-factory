import os
import asyncio
import feedparser
import random
import urllib.parse
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# Загрузка секретов из переменных окружения
HF_KEY = os.getenv("HF_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

if not all([HF_KEY, TG_TOKEN, TG_CHAT]):
    print("❌ ОШИБКА: Не все секреты настроены (HF_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).")
    exit(1)

# Клиент к бесплатному Serverless Router Hugging Face
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_KEY
)

bot = AsyncTeleBot(TG_TOKEN)
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"

async def get_news_headline():
    """Скрейпинг свежих новостей из RSS-ленты Хабра"""
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://habr.com/ru/rss/articles/?fl=ru")
        if not feed.entries:
            return None
        top_entries = feed.entries[:5]
        return random.choice(top_entries).title
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

async def generate_agent_discussion(headline):
    """Генерация ситком-диалога между Джуниором и Тимлидом и концепта мема"""
    print(f"🧠 Агенты обсуждают: {headline[:50]}...")
    
    prompt = f"""
Ты сценарист абсурдного IT-ситкома. Разыграй короткий диалог между двумя агентами по новости:
"{headline}"

Агенты:
1. 👶 Джуниор: восторженный неофит, паникует или восхищается баззвордами.
2. 🚬 Тимлид: уставший циник, отвечает едким сарказмом и приземляет.

ПРАВИЛО ДЛЯ ВИЗУАЛА:
Придумай визуальную сцену для [ПРОМПТ]. 
СТРОГИЙ ЗАПРЕТ на красивые лица, моделей, фотостоки, неоновый киберпанк и кинематографичность. 
Сделай абсурдную бытовую ситуацию или проклятый образ (cursed image), связанный с репликой Тимлида.
Примеры хорошего стиля:
- "paranoid man with tinfoil hat aggressively staring down a kitchen toaster, flash photography, 2000s web camera meme, cursed image aesthetic"
- "a racoon wearing glasses desperately looking at smoking computer servers, messy office, amateur photo, chaos"

Формат вывода СТРОГО:
[ДИАЛОГ]
👶 Джуниор: <одна короткая реплика>
🚬 Тимлид: <едкий саркастичный ответ>
[ПРОМПТ]
<детальное описание абсурдной сцены на английском, amateur snapshot, flash photo, cursed meme energy, realistic chaotic absurdity>
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты пишешь жесткие, смешные диалоги и абсурдные мемные промпты для айтишников."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return None

async def send_to_telegram(image_url, caption_text):
    """Публикация изображения с подписью в Telegram-канал"""
    try:
        await bot.send_photo(TG_CHAT, image_url, caption=caption_text, parse_mode='HTML')
        print("✅ Успешно опубликовано в Telegram!")
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

async def run_factory_once():
    headline = await get_news_headline()
    if not headline:
        print("❌ Не удалось получить новость.")
        return
    print(f"📰 Новость: {headline}\n")

    raw_output = await generate_agent_discussion(headline)
    if not raw_output:
        print("❌ Не удалось сгенерировать диалог.")
        return
    print(f"🎭 Сценарий:\n{raw_output}\n")

    dialogue_part = ""
    img_prompt = ""

    # Парсинг структурированного ответа
    if "[ДИАЛОГ]" in raw_output and "[ПРОМПТ]" in raw_output:
        parts = raw_output.split("[ПРОМПТ]")
        dialogue_part = parts[0].replace("[ДИАЛОГ]", "").strip()
        img_prompt = parts[1].strip()
    else:
        dialogue_part = raw_output[:300].strip()
        img_prompt = "confused funny animal staring at a smoking broken appliance, flash snapshot, cursed meme"

    # Сборка запроса к Pollinations с моделью Flux для качественной генерации деталей
    encoded_img_prompt = urllib.parse.quote(f"{img_prompt}, raw amateur photo, flash snapshot, cursed meme context")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=1024&height=1024&nologo=true&private=true&model=flux"

    caption_text = (
        f"📰 <b>{headline}</b>\n\n"
        f"<blockquote>{dialogue_part}</blockquote>"
    )

    await send_to_telegram(image_url, caption_text)

if __name__ == "__main__":
    asyncio.run(run_factory_once())
