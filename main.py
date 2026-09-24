import os
import asyncio
import feedparser
import random
import urllib.parse
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# 1. Загрузка секретов
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
    """Сбор свежих заголовков с Хабра"""
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://habr.com/ru/rss/articles/?fl=ru")
        if not feed.entries:
            return None
        return random.choice(feed.entries[:5]).title
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

async def step1_junior_pitch(headline):
    """Агент 1: Джуниор влетает с новостью в чат"""
    print("👶 Джуниор генерирует заход...")
    prompt = f"""
Ты восторженный 20-летний Джуниор-разработчик. Ты только что прочитал эту новость:
"{headline}"

Напиши короткое (1-2 предложения) импульсивное сообщение в рабочий чат.
Ты восхищен технологиями, сыплешь баззвордами или паникуешь, что вас заменят.
Используй смайлики. Не придумывай диалог, пиши ТОЛЬКО свою прямую речь.
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"Ошибка Джуниора: {e}")
        return None

async def step2_lead_verdict(headline, junior_text):
    """Агент 2: Тимлид реагирует на слова Джуниора и формулирует промпт"""
    print("🚬 Тимлид оценивает тейк...")
    prompt = f"""
Новость: "{headline}"
Джуниор написал в чат: "{junior_text}"

Ты — 40-летний выгоревший Тимлид. Ответь Джуниору прямо на его слова.
Отрежь его энтузиазм жестким сарказмом, цинизмом или абсурдной житейской правдой (1-2 предложения).

Также придумай идею для мема по мотивам твоего ответа.
СТРОГИЙ ЗАПРЕТ на красивые лица, моделей, фотостоки и неоновый киберпанк.
Нужна абсурдная бытовая ситуация, флеш-фотография, cursed meme energy.

Формат ответа СТРОГО:
ОТВЕТ: <твой саркастичный ответ Джуниору>
ПРОМПТ: <описание абсурдной мемной сцены на английском, amateur flash photo, chaotic real-life meme>
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка Тимлида: {e}")
        return None

async def run_factory_once():
    # Шаг 1: Получаем новость
    headline = await get_news_headline()
    if not headline:
        return
    print(f"📰 Новость: {headline}\n")

    # Шаг 2: Реплика Джуниора
    junior_msg = await step1_junior_pitch(headline)
    if not junior_msg:
        return
    print(f"👶 Джуниор:\n{junior_msg}\n")

    # Шаг 3: Реакция Тимлида
    lead_raw = await step2_lead_verdict(headline, junior_msg)
    if not lead_raw:
        return
    print(f"🚬 Тимлид сырой ответ:\n{lead_raw}\n")

    lead_reply = "Опять переделывать за вами..."
    img_prompt = "tired programmer staring at broken microwave oven, amateur flash photo"

    for line in lead_raw.split("\n"):
        if line.startswith("ОТВЕТ:"):
            lead_reply = line.replace("ОТВЕТ:", "").strip()
        elif line.startswith("ПРОМПТ:"):
            img_prompt = line.replace("ПРОМПТ:", "").strip()

    # Шаг 4: Генерация мем-арта
    encoded_img_prompt = urllib.parse.quote(f"{img_prompt}, raw snapshot, cursed meme")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=1024&height=1024&nologo=true&private=true&model=flux"

    # Шаг 5: Публикация первого сообщения от Джуниора
    junior_post_text = (
        f"📰 <b>{headline}</b>\n\n"
        f"👶 <b>Джуниор:</b> {junior_msg}"
    )
    
    try:
        sent_msg = await bot.send_message(TG_CHAT, junior_post_text, parse_mode='HTML')
        print("✅ Сообщение Джуниора отправлено.")

        # Имитируем живую паузу на ответ
        print("⏳ Тимлид печатает ответ...")
        await asyncio.sleep(4)

        # Публикация ответа Тимлида реплаем 
        lead_post_caption = f"🚬 <b>Тимлид:</b> {lead_reply}"
        await bot.send_photo(
            TG_CHAT, 
            image_url, 
            caption=lead_post_caption, 
            reply_to_message_id=sent_msg.message_id, 
            parse_mode='HTML'
        )
        print("✅ Мем Тимлида успешно опубликован в ответ!")
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory_once())
