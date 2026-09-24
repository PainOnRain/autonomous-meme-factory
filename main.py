import os
import asyncio
import feedparser
import random
import httpx
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# 1. Секреты
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

# Источник: ИА «Панорама»
PANORAMA_RSS = "https://panorama.pub/rss"

MEME_TEMPLATES = [
    "fine",          # This is fine (собака в огне)
    "harold",        # Гарольд скрывающий боль
    "clown",         # Клоун наносит грим
    "fry",           # Подозрительный Фрай
    "disastergirl",  # Девочка на фоне пожара
    "rollsafe",      # Парень со смекалочкой
    "spiderman",     # Спайдермены
    "doge",          # Пёс Доге
    "buzz",          # Базз Лайтер (везде...)
    "drake"          # Дрейк (нет / да)
]

async def get_fresh_news_pool():
    """Скачиваем RSS Панорамы с маскировкой под браузер"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as http_client:
        try:
            print(f"📡 Загружаем ленту ИА «Панорама»: {PANORAMA_RSS}")
            res = await http_client.get(PANORAMA_RSS)
            if res.status_code == 200:
                feed = feedparser.parse(res.text)
                titles = [entry.title for entry in feed.entries if getattr(entry, 'title', None)]
                if titles:
                    print(f"✅ Найдено новостей: {len(titles)}")
                    return titles[:6]
            print(f"⚠️ Панорама вернула код: {res.status_code}")
        except Exception as e:
            print(f"⚠️ Ошибка запроса: {e}")

    return []

async def junior_pitch(headline):
    prompt = f"""
Ты наивный Джуниор-программист. Ты только что прочитал эту новость и ПРИНЯЛ ЕЁ ЗА ЧИСТУЮ МОНЕТУ:
"{headline}"

Напиши короткий (1-2 предложения) восторженный или паникующий заход Тимлиду в чат.
Ты абсолютно уверен, что это правда, и предлагаешь срочно внедрять это в проект или кричишь, что вас уволят.
Выдай ТОЛЬКО текст своей реплики.
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
        return "Шеф, ты читал?! Нам срочно нужно переписать весь прод под новые требования!"

async def lead_evaluation(headline, junior_msg, is_last=False):
    force = "Это последняя новость, ОБЯЗАТЕЛЬНО поставь СТАТУС: ОДОБРЕНО." if is_last else ""
    templates_str = ", ".join(MEME_TEMPLATES)

    prompt = f"""
Новость: "{headline}"
Джуниор (поверил на полном серьезе): "{junior_msg}"

Ты — 45-летний злой, циничный Тимлид. 
Ты понимаешь весь абсурд ситуации или уничтожаешь Джуниора за то, что он ведётся на любую дичь.
1. Оцени тему: если слишком тонко/непонятно — ОТКЛОНИ. Если абсурд очевиден и можно едко приложить Джуниора — ОДОБРИ.
2. Выбери мем-шаблон: [{templates_str}].
3. Придумай верхний (ТЕКСТ_1) и нижний (ТЕКСТ_2) текст на русском (по 2-5 слов).
{force}

Формат ответа СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой саркастичный комментарий>
ШАБЛОН: <одно слово из шаблонов>
ТЕКСТ_1: <верхняя строчка>
ТЕКСТ_2: <нижняя строчка>
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
    api_url = "https://api.memegen.link/images"
    payload = {
        "template_id": template if template in MEME_TEMPLATES else "fine",
        "text": [text1, text2]
    }
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            res = await http_client.post(api_url, json=payload)
            if res.status_code == 201:
                return res.json().get("url")
        except Exception as e:
            print(f"Ошибка Memegen API: {e}")

    t1_clean = text1.replace("/", "").replace("?", "").replace("#", "") or "_"
    t2_clean = text2.replace("/", "").replace("?", "").replace("#", "") or "_"
    return f"https://api.memegen.link/images/{template}/{t1_clean}/{t2_clean}.png"

async def run_factory():
    print("🚀 Старт цикла Autonomous Meme Factory (Панорама)...")
    news_pool = await get_fresh_news_pool()
    if not news_pool:
        print("❌ Не удалось загрузить новости Панорамы.")
        return

    approved_headline = None
    approved_junior = None
    approved_reply = None
    template = "fine"
    t1, t2 = "ПАНОРАМА", "ДЖУН ПОВЕРИЛ"

    for idx, headline in enumerate(news_pool, 1):
        is_last = (idx == len(news_pool))
        print(f"\n--- [Раунд {idx}/{len(news_pool)}] ---")
        print(f"📰 {headline}")

        j_msg = await junior_pitch(headline)
        print(f"👶 Джун: {j_msg}")

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

        print(f"🚬 Тимлид ({status}): {approved_reply}")

        if status == "ОДОБРЕНО":
            approved_headline = headline
            approved_junior = j_msg
            break

    if not approved_headline:
        print("❌ Ни один инфоповод не утвержден.")
        return

    print(f"\n🖼 Создаём мем [{template}]: '{t1}' / '{t2}'...")
    image_url = await create_meme_image(template, t1, t2)
    print(f"🔗 Ссылка: {image_url}")

    # Публикация
    junior_post = f"📰 <b>{approved_headline}</b>\n\n👶 <b>Джуниор:</b> {approved_junior}"
    try:
        sent = await bot.send_message(TG_CHAT, junior_post, parse_mode='HTML')
        print("✅ Джуниор отписался.")

        await asyncio.sleep(3)
        lead_caption = f"🚬 <b>Тимлид:</b> {approved_reply}"
        await bot.send_photo(TG_CHAT, image_url, caption=lead_caption, reply_to_message_id=sent.message_id, parse_mode='HTML')
        print("✅ Мем Тимлида отправлен в ответ!")
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
