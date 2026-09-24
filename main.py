import os
import asyncio
import feedparser
import random
import urllib.parse
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

HF_KEY = os.getenv("HF_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

if not all([HF_KEY, TG_TOKEN, TG_CHAT]):
    print("❌ ОШИБКА: Не все секреты настроены.")
    exit(1)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_KEY
)
bot = AsyncTeleBot(TG_TOKEN)
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"

async def get_news_headline():
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
    print(f"🧠 Агенты обсуждают: {headline[:50]}...")
    
    prompt = f"""
Ты режиссер ситкома про IT-отдел. Разыграй короткий диалог между двумя агентами по поводу новости:
"{headline}"

Агенты:
1. 👶 Джуниор: наивный, верит во все новые технологии, сыплет баззвордами.
2. 🚬 Тимлид: уставший циник с дергающимся глазом, ненавидит оверинжиниринг и костыли.

После диалога Тимлид формулирует визуальную идею для мема. Избегай унылых шуток в стиле "до первого бага". Нужен абсурд, щитпостинг или жизненная боль.

Выведи ответ СТРОГО в следующем формате:
[ДИАЛОГ]
👶 Джуниор: <одна короткая реплика>
🚬 Тимлид: <острая саркастичная реплика в ответ>
[ПРОМПТ]
<детальный промпт на английском для генератора мема: забавный, мемный стиль, funny meme template, absurdity, real photo expression, relatable visual>
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты пишешь жесткие, смешные диалоги для айтишников в формате щитпоста."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return None

async def send_to_telegram(image_url, caption_text):
    try:
        await bot.send_photo(TG_CHAT, image_url, caption=caption_text, parse_mode='HTML')
        print("✅ Успешно опубликовано!")
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

async def run_factory_once():
    headline = await get_news_headline()
    if not headline:
        return
    print(f"📰 Новость: {headline}\n")

    raw_output = await generate_agent_discussion(headline)
    if not raw_output:
        return
    print(f"🎭 Сценарий:\n{raw_output}\n")

    dialogue_part = ""
    img_prompt = ""

    if "[ДИАЛОГ]" in raw_output and "[ПРОМПТ]" in raw_output:
        parts = raw_output.split("[ПРОМПТ]")
        dialogue_part = parts[0].replace("[ДИАЛОГ]", "").strip()
        img_prompt = parts[1].strip()
    else:
        dialogue_part = raw_output[:300]
        img_prompt = "funny confused animal looking at computer screen meme"

    encoded_img_prompt = urllib.parse.quote(f"{img_prompt}, funny meme photography")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=1024&height=1024&nologo=true&private=true"

    caption_text = (
        f"📰 <b>{headline}</b>\n\n"
        f"<blockquote>{dialogue_part}</blockquote>"
    )

    await send_to_telegram(image_url, caption_text)

if __name__ == "__main__":
    asyncio.run(run_factory_once())
