import os
import asyncio
import feedparser
import random
import httpx
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

# Список поддерживаемых культовых шаблонов
MEME_TEMPLATES = [
    "fine",          # This is fine (собака в огне)
    "harold",        # Гарольд скрывающий боль
    "clown",         # Клоун наносит грим (по шагам)
    "fry",           # Подозрительный Фрай (Not sure if...)
    "disastergirl",  # Девочка на фоне горящего дома
    "rollsafe",      # Парень стучит по виску (смекалочка)
    "spiderman",     # Спайдермены показывают пальцем друг на друга
    "doge",          # Доге
    "buzz",          # Базз Лайтер: повсюду...
    "drake"          # Дрейк (нет / да)
]

async def get_fresh_news_pool():
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://habr.com/ru/rss/articles/?fl=ru")
        if not feed.entries:
            return []
        return [entry.title for entry in feed.entries[:6]]
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []

async def junior_pitch(headline):
    prompt = f"""
Ты восторженный Джуниор. Ты прибежал к Тимлиду с новостью:
"{headline}"

Напиши короткий (1-2 предложения) заход с наивным энтузиазмом или паникой. Используй баззворды. Выдай ТОЛЬКО текст реплики.
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
        return "Шеф, ты видел? Это же перевернет весь стек!"

async def lead_evaluation(headline, junior_msg, is_last=False):
    force = "Это последняя попытка, ОБЯЗАТЕЛЬНО поставь СТАТУС: ОДОБРЕНО." if is_last else ""
    templates_str = ", ".join(MEME_TEMPLATES)
    
    prompt = f"""
Новость: "{headline}"
Джуниор: "{junior_msg}"

Ты — 45-летний злой, циничный Тимлид. 
1. Оцени новость: если скучно — ОТКЛОНИ. Если можно едко обстебать — ОДОБРИ.
2. Выбери наиболее подходящий мем-шаблон из списка: [{templates_str}].
3. Придумай верхний (ТЕКСТ_1) и нижний (ТЕКСТ_2) короткий текст для нанесения на мем. Текст должен быть острым и смешным!
{force}

Формат ответа СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой комментарий в чат>
ШАБЛОН: <одно слово из списка шаблонов>
ТЕКСТ_1: <верхняя строчка мема, до 5-6 слов>
ТЕКСТ_2: <нижняя строчка мема, до 5-6 слов>
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

async def create_meme_image(template, text1, text2):
    """Генерация мема через Memegen API с надписями прямо на картинке"""
    api_url = "https://api.memegen.link/images"
    payload = {
        "template_id": template if template in MEME_TEMPLATES else "fine",
        "text": [text1, text2]
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(api_url, json=payload, timeout=10.0)
            if res.status_code == 201:
                return res.json().get("url")
        except Exception as e:
            print(f"Ошибка Memegen: {e}")
    # Фоллбэк
    return f"https://api.memegen.link/images/fine/{text1}/{text2}.png"

async def run_factory():
    news_pool = await get_fresh_news_pool()
    if not news_pool:
        return

    approved_headline = None
    approved_junior = None
    approved_reply = None
    template = "fine"
    t1, t2 = "ВСЁ ХОРОШО", "ПРОД ГОРИТ"

    for idx, headline in enumerate(news_pool, 1):
        is_last = (idx == len(news_pool))
        j_msg = await junior_pitch(headline)
        lead_raw = await lead_evaluation(headline, j_msg, is_last=is_last)
        if not lead_raw:
            continue

        status = "ОТКЛОНЕНО"
        for line in lead_raw.split("\n"):
            line = line.strip()
            if line.startswith("СТАТУС:"):
                status = "ОДОБРЕНО" if "ОДОБРЕНО" in line.upper() else "ОТКЛОНЕНО"
            elif line.startswith("ОТВЕТ:"):
                approved_reply = line.replace("ОТВЕТ:", "").strip()
            elif line.startswith("ШАБЛОН:"):
                template = line.replace("ШАБЛОН:", "").strip().lower()
            elif line.startswith("ТЕКСТ_1:"):
                t1 = line.replace("ТЕКСТ_1:", "").strip()
            elif line.startswith("ТЕКСТ_2:"):
                t2 = line.replace("ТЕКСТ_2:", "").strip()

        if status == "ОДОБРЕНО":
            approved_headline = headline
            approved_junior = j_msg
            break

    if not approved_headline:
        return

    # Получаем ссылку на готовый мем с наложенным текстом
    image_url = await create_meme_image(template, t1, t2)
    print(f"🖼 Мем сгенерирован ({template}): {image_url}")

    # Публикация
    junior_post = f"📰 <b>{approved_headline}</b>\n\n👶 <b>Джуниор:</b> {approved_junior}"
    try:
        sent = await bot.send_message(TG_CHAT, junior_post, parse_mode='HTML')
        await asyncio.sleep(3)
        lead_caption = f"🚬 <b>Тимлид:</b> {approved_reply}"
        await bot.send_photo(TG_CHAT, image_url, caption=lead_caption, reply_to_message_id=sent.message_id, parse_mode='HTML')
        print("✅ Пост с мемом успешно опубликован!")
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
