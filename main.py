import os
import asyncio
import io
import html
import re
import urllib.parse
import random
import sqlite3
import httpx
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# 1. Загрузка переменных окружения
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
DB_PATH = "published_history.db"

if not all([OPENROUTER_KEY, TG_TOKEN, TG_CHAT]):
    print("❌ ОШИБКА: Не заданы переменные (OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).")
    exit(1)

# Клиент OpenRouter (полностью совместим с OpenAI SDK)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY
)

# Бесплатная версия Llama 3.1 8B на OpenRouter
MODEL_NAME = "meta-llama/llama-3.1-8b-instruct:free"
bot = AsyncTeleBot(TG_TOKEN)

MEME_TEMPLATES = [
    "clown",         # Клоун наносит грим
    "fine",          # This is fine (собака в огне)
    "drake",         # Дрейк
    "rollsafe",      # Смекалочка
    "fry",           # Подозрительный Фрай
    "disastergirl",  # Девочка на фоне пожара
    "doge",          # Пёс Доге
    "harold",        # Гарольд, скрывающий боль
    "buzz",          # Базз Лайтер
    "spiderman"      # Спайдермены
]

# Пул архетипов Джуна
JUNIOR_ARCHETYPES = [
    "ты словил выгорание от двух задач в Jira, жалуешься на микроменеджмент и токсичную культуру овертаймов.",
    "ты в бытовой драме релоканта: заблокировали сервис подписок, иностранный банк заморозил перевод, в кофейне нет матчи.",
    "ты душнишь про западные институты, корпоративный комплаенс, инклюзивность и переживаешь за индекс счастья сотрудников.",
    "ты псевдо-визионер: сыплешь терминами вроде 'синергия', 'майндсет', 'экологичный фидбек' и предлагаешь решить проблему ретроспективой и дыхательными практиками.",
    "ты в открытой панике: боишься, что из-за этой новости компания урежет бюджет на мерч, курсы английского и корпоративного психолога."
]

# Пул архетипов Тимлида
LEAD_ARCHETYPES = [
    "Суровый экс-заводчанин, перешедший в IT: считает программирование курортом, постоянно грозится отправить нытика к фрезерному станку.",
    "Старый циничный бородатый сисадмин: презирает модные фреймворки, скрам, коучей и решает любые проблемы перезагрузкой сервера.",
    "Прагматичный техдиректор-капиталист: оценивает людей исключительно по выработке, метрикам и прибыли, высмеивая любые эмоции языком KPI.",
    "Ультра-патриотичный технарь старой школы: убежден, что софт нужно писать на C и отечественном железе, а любые западные жалобы — признак профнепригодности."
]

# 2. SQLite база данных для дедупликации постов
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_news (
                post_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def is_already_posted(post_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM posted_news WHERE post_id = ?", (post_id,))
        return cur.fetchone() is not None

def mark_as_posted(post_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO posted_news (post_id) VALUES (?)", (post_id,))

# 3. Парсер канала КБ с вытаскиванием post_id
async def get_fresh_news_pool():
    url = "https://t.me/s/Cbpub"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print(f"📡 Загружаем посты из канала: {url}")
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as http_client:
            res = await http_client.get(url)
            if res.status_code != 200:
                print(f"⚠️ Ошибка загрузки страницы КБ: статус {res.status_code}")
                return []

            pattern = r'<div class="tgme_widget_message\b[^>]*\bdata-post="([^"]+)"[^>]*>[\s\S]*?<div class="tgme_widget_message_text\b[^>]*>([\s\S]*?)</div>'
            matches = re.findall(pattern, res.text)

            news = []
            for post_id, raw_html in matches:
                if is_already_posted(post_id):
                    continue

                text = re.sub(r'<br\s*/?>', '\n', raw_html)
                text = re.sub(r'<[^>]+>', '', text)
                text = html.unescape(text).strip()

                lower_text = text.lower()
                is_ad = any(k in lower_text for k in ["erid:", "t.me/", "скидк", "промокод", "подписывайся", "розыгрыш"])

                if len(text) >= 35 and not is_ad:
                    first_lines = [l.strip() for l in text.split("\n") if l.strip()]
                    summary = " ".join(first_lines[:2])[:220]
                    news.append({"id": post_id, "text": summary})

            # Берем до 6 свежих новостей
            seen_ids = set()
            unique_news = []
            for item in reversed(news):
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    unique_news.append(item)
                if len(unique_news) >= 6:
                    break

            print(f"✅ Найдено свежих неопубликованных новостей: {len(unique_news)}")
            return unique_news
    except Exception as e:
        print(f"❌ Ошибка парсинга канала: {e}")
        return []

# 4. Генерация нытья Джуниора
async def junior_pitch(headline):
    current_mood = random.choice(JUNIOR_ARCHETYPES)

    prompt = f"""Инфоповод: "{headline}"

РОЛЬ:
Ты — 22-летний начинающий IT-специалист (зумер).
Твоё текущее состояние: {current_mood}

ТРЕБОВАНИЯ:
- Напиши ОДНУ короткую реплику (1-2 предложения прямой речи) в рабочий чат.
- ОБЯЗАТЕЛЬНО зацепись за конкретную сущность из инфоповода (назови компанию, сумму, технологию, закон, сервис или действие из текста).
- НЕ используй заезженные слова: "кринж", "лапки", "соя", "тревожно", "вайб". Пиши естественно и живо.

Выведи ТОЛЬКО текст прямой речи:"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты отыгрываешь карикатурного, ранимого зумера-программиста."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            presence_penalty=0.6,
            frequency_penalty=0.5
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"Ошибка генерации Джуниора: {e}")
        return "Коллеги, после таких новостей я временно беру дей-офф и отключаю уведомления..."

# 5. Генерация разноса от Тимлида
async def lead_evaluation(headline, junior_msg, is_last=False):
    force = "Это последний инфоповод в пачке. Твой вердикт ОБЯЗАТЕЛЬНО: СТАТУС: ОДОБРЕНО." if is_last else ""
    templates_str = ", ".join(MEME_TEMPLATES)
    current_archetype = random.choice(LEAD_ARCHETYPES)

    prompt = f"""Инфоповод: "{headline}"
Реплика Джуна: "{junior_msg}"

РОЛЬ ТИМЛИДА:
{current_archetype}

ТРЕБОВАНИЯ:
- Ответ должен быть коротким (1-2 хлестких, ядовитых предложения).
- Разбей конкретный довод Джуна, высмеивая его наивность и оторванность от реальности.
- Не используй шаблонные общие оскорбления; строй панч вокруг того, ЧТО именно ляпнул Джун.

ЗАДАЧА:
1. Оцени инфоповод: если скучная рутина — СТАТУС: ОТКЛОНЕНО. Если есть повод для разноса — СТАТУС: ОДОБРЕНО.
2. Выбери мем-шаблон из списка: [{templates_str}].
3. Придумай верхний (ТЕКСТ_1) и нижний (ТЕКСТ_2) текст на русском КАПСОМ (по 2-3 слова).
{force}

Формат ответа СТРОГО по шаблону:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой ответ Джуну>
ШАБЛОН: <шаблон>
ТЕКСТ_1: <текст 1>
ТЕКСТ_2: <текст 2>"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Ты токсичный, циничный и остроумный технический руководитель."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            presence_penalty=0.6,
            frequency_penalty=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка генерации Тимлида: {e}")
        return None

# 6. Скачивание мема
async def download_meme_bytes(template, text1, text2):
    t1_clean = re.sub(r'[/\\?%*:|"<>]', '', text1).strip() or "_"
    t2_clean = re.sub(r'[/\\?%*:|"<>]', '', text2).strip() or "_"

    t1_encoded = urllib.parse.quote(t1_clean.replace(" ", "_"))
    t2_encoded = urllib.parse.quote(t2_clean.replace(" ", "_"))
    direct_url = f"https://api.memegen.link/images/{template}/{t1_encoded}/{t2_encoded}.png"

    print(f"🖼 Скачиваем мем: {direct_url}")
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        try:
            res = await http_client.get(direct_url)
            if res.status_code == 200 and len(res.content) > 1000:
                return res.content
        except Exception as e:
            print(f"Ошибка скачивания мема: {e}")

    # Fallback при ошибке API
    fallback_url = f"https://api.memegen.link/images/{template}/ДЕПЛОЙ_В_ПЯТНИЦУ/РАБОТАЕМ.png"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            res = await http_client.get(fallback_url)
            if res.status_code == 200:
                return res.content
    except Exception:
        pass
    return None

# 7. Пайплайн публикации
async def run_factory():
    print("🚀 Старт генерации контента...")
    init_db()

    news_pool = await get_fresh_news_pool()
    if not news_pool:
        print("❌ Свежих неопубликованных новостей нет.")
        return

    approved_item = None
    approved_junior = None
    approved_reply = None
    template = "clown"
    t1, t2 = "РАБОТАТЬ", "НА ЗАВОД"

    for idx, item in enumerate(news_pool, 1):
        headline = item["text"]
        is_last = (idx == len(news_pool))
        print(f"\n--- [Кандидат {idx}/{len(news_pool)}] ID: {item['id']} ---")
        print(f"📰 {headline}")

        j_msg = await junior_pitch(headline)
        print(f"👶 Джун: {j_msg}")

        lead_raw = await lead_evaluation(headline, j_msg, is_last=is_last)
        if not lead_raw:
            continue

        status = "ОТКЛОНЕНО"
        parsed_reply = None
        parsed_tpl = template
        parsed_t1, parsed_t2 = t1, t2

        for line in lead_raw.split("\n"):
            line = line.strip()
            if line.startswith("СТАТУС:"):
                status = "ОДОБРЕНО" if "ОДОБРЕНО" in line.upper() else "ОТКЛОНЕНО"
            elif line.startswith("ОТВЕТ:"):
                parsed_reply = line.replace("ОТВЕТ:", "").strip()
            elif line.startswith("ШАБЛОН:"):
                candidate_tpl = line.replace("ШАБЛОН:", "").strip().lower()
                if candidate_tpl in MEME_TEMPLATES:
                    parsed_tpl = candidate_tpl
            elif line.startswith("ТЕКСТ_1:"):
                parsed_t1 = line.replace("ТЕКСТ_1:", "").strip()
            elif line.startswith("ТЕКСТ_2:"):
                parsed_t2 = line.replace("ТЕКСТ_2:", "").strip()

        print(f"🚬 Тимлид ({status}): {parsed_reply}")

        if status == "ОДОБРЕНО" and parsed_reply:
            approved_item = item
            approved_junior = j_msg
            approved_reply = parsed_reply
            template, t1, t2 = parsed_tpl, parsed_t1, parsed_t2
            break

    if not approved_item:
        print("❌ Инфоповод не выбран.")
        return

    img_bytes = await download_meme_bytes(template, t1, t2)

    safe_headline = html.escape(approved_item["text"])
    safe_junior = html.escape(approved_junior)
    safe_reply = html.escape(approved_reply)

    junior_post = f"📰 <b>{safe_headline}</b>\n\n👶 <b>Джуниор:</b> {safe_junior}"

    try:
        await bot.send_message(TG_CHAT, junior_post, parse_mode='HTML')
        print("✅ Реплика Джуниора опубликована.")

        await asyncio.sleep(3)

        lead_caption = f"🚬 <b>Тимлид:</b> {safe_reply}"
        if img_bytes:
            photo_file = io.BytesIO(img_bytes)
            photo_file.name = "meme.png"
            await bot.send_photo(TG_CHAT, photo_file, caption=lead_caption, parse_mode='HTML')
            print("✅ Ответ Тимлида с мемом опубликован.")
        else:
            await bot.send_message(TG_CHAT, lead_caption, parse_mode='HTML')
            print("⚠️ Мем не загрузился, отправлен текстовый ответ.")

        mark_as_posted(approved_item["id"])
        print(f"🔒 Новость {approved_item['id']} сохранена в SQLite.")

    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
