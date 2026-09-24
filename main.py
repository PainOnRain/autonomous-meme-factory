import os
import asyncio
import random
import re
import html
import httpx
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# 1. Загрузка переменных окружения
HF_KEY = os.getenv("HF_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

if not all([HF_KEY, TG_TOKEN, TG_CHAT]):
    print("❌ ОШИБКА: Не все секреты настроены (HF_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).")
    exit(1)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_KEY
)
bot = AsyncTeleBot(TG_TOKEN)
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"

# Список поддерживаемых культовых шаблонов мемов
MEME_TEMPLATES = [
    "clown",         # Клоун наносит грим (идеально для сои)
    "fine",          # This is fine (собака в огне)
    "drake",         # Дрейк (отрицание / одобрение)
    "rollsafe",      # Смекалочка / многоходовочка
    "fry",           # Подозрительный Фрай
    "disastergirl",  # Девочка на фоне пожара
    "doge",          # Пёс Доге (сравнение силы)
    "harold",        # Гарольд, скрывающий боль
    "buzz",          # Кругом одни...
    "spiderman"      # Стрелочники
]

async def get_fresh_news_pool():
    """Парсинг последних постов из веб-зеркала Telegram-канала КБ"""
    url = "https://t.me/s/Cbpub"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    print(f"📡 Загружаем посты из канала КБ: {url}")
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as http_client:
            res = await http_client.get(url)
            if res.status_code != 200:
                print(f"⚠️ Telegram ответил статусом: {res.status_code}")
                return []

            # Извлечение блоков текста постов
            pattern = r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>'
            matches = re.findall(pattern, res.text, re.DOTALL)

            news = []
            for raw_html in matches:
                # Очистка от HTML-тегов и переносов
                text = re.sub(r'<br\s*/?>', '\n', raw_html)
                text = re.sub(r'<[^>]+>', '', text)
                text = html.unescape(text).strip()

                # Фильтр рекламы и слишком коротких реакций
                lower_text = text.lower()
                is_ad = any(k in lower_text for k in ["erid:", "t.me/", "скидк", "промокод", "подписывайся", "розыгрыш"])
                if len(text) >= 35 and not is_ad:
                    # Берём первые пару предложений в качестве сути инфоповода
                    first_lines = [l.strip() for l in text.split("\n") if l.strip()]
                    summary = " ".join(first_lines[:2])
                    news.append(summary[:220])

            # Берём последние 6 постов (в порядке от новых к старым)
            unique_news = list(dict.fromkeys(news))[-6:][::-1]
            print(f"✅ Найдено подходящих новостей: {len(unique_news)}")
            return unique_news
    except Exception as e:
        print(f"❌ Ошибка парсинга КБ: {e}")
        return []

async def junior_pitch(headline):
    """Соевый либерал-джуниор паникует и наводит суету"""
    prompt = f"""
Инфоповод:
"{headline}"

Ты — 21-летний соевый либерал-джуниор. 
Ты труслив, инфантилен, постоянно ловишь панические атаки, пьёшь тыквенный латте на соевом молоке, боишься повесток и мечтаешь уехать на самокате через Верхний Ларс в Тбилиси или Ереван.
От этой новости у тебя случилась истерика.
Напиши короткий (1-2 предложения) панический заход Тимлиду в чат.
Используй соевый сленг: «кринж», «мне тревожно», «триггерит», «это не окей», «токсично», «пора валить», «у меня лапки», «вайб».
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
        return "Шеф, мне очень тревожно от этой новости... Кажется, пора срочно релоцироваться!"

async def lead_evaluation(headline, junior_msg, is_last=False):
    """Пророссийский гигачад-тимлид разносит джуна и выдает базу"""
    force = "Это последняя новость в пачке, ОБЯЗАТЕЛЬНО поставь СТАТУС: ОДОБРЕНО." if is_last else ""
    templates_str = ", ".join(MEME_TEMPLATES)

    prompt = f"""
Новость: "{headline}"
Соевый Джуниор на панике: "{junior_msg}"

Ты — 45-летний пророссийский Гигачад-Тимлид, ветеран IT, убеждённый патриот, поддерживаешь Россию, СВО, армию и импортозамещение.
Ты спокоен как скала, говоришь с позиции силы и жёстко стебёшь соевого джуна за трусость, женственность и либеральные сопли.
Твоя лексика и тейпы: «база», «наши слоны», «ГОЙДА», «работайте, братья», «иди на завод», «хватит плакать в Верхнем Ларсе», «наши парни на передке софт быстрее коммитят».

ТВОЯ ЗАДАЧА:
1. Оцени новость: если инфоповод скучный — ОТКЛОНИ. Если можно жирно постебаться над джуном, Западом или утвердить величие наших — ОДОБРИ.
2. Выбери мем-шаблон: [{templates_str}].
3. Придумай верхний (ТЕКСТ_1) и нижний (ТЕКСТ_2) текст на русском КАПСОМ (по 2-4 слова).
{force}

Формат ответа СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой базированный ответ-разнос джуна, 1-2 предложения>
ШАБЛОН: <слово из списка шаблонов>
ТЕКСТ_1: <верхняя строка мема капсом>
ТЕКСТ_2: <нижняя строка мема капсом>
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
    """Создание мема с надписями через Memegen API"""
    api_url = "https://api.memegen.link/images"
    payload = {
        "template_id": template if template in MEME_TEMPLATES else "clown",
        "text": [text1, text2]
    }
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            res = await http_client.post(api_url, json=payload)
            if res.status_code == 201:
                return res.json().get("url")
        except Exception as e:
            print(f"Ошибка Memegen API: {e}")

    t1_clean = text1.replace(" ", "_").replace("/", "").replace("?", "") or "_"
    t2_clean = text2.replace(" ", "_").replace("/", "").replace("?", "") or "_"
    return f"https://api.memegen.link/images/{template}/{t1_clean}/{t2_clean}.png"

async def run_factory():
    print("🚀 Старт фабрики мемов (Источник: КБ)...")
    news_pool = await get_fresh_news_pool()
    if not news_pool:
        print("❌ Не удалось получить посты из КБ.")
        return

    approved_headline = None
    approved_junior = None
    approved_reply = None
    template = "clown"
    t1, t2 = "ТРЕВОЖНО", "НАШИ СЛОНЫ"

    for idx, headline in enumerate(news_pool, 1):
        is_last = (idx == len(news_pool))
        print(f"\n--- [Раунд {idx}/{len(news_pool)}] ---")
        print(f"📰 Инфоповод: {headline}")

        j_msg = await junior_pitch(headline)
        print(f"👶 Соевый Джун: {j_msg}")

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

        print(f"🚬 Гигачад Тимлид ({status}): {approved_reply}")

        if status == "ОДОБРЕНО":
            approved_headline = headline
            approved_junior = j_msg
            break

    if not approved_headline:
        print("❌ Тимлид забраковал всю ленту.")
        return

    print(f"\n🖼 Генерируем мем [{template}]: '{t1}' / '{t2}'...")
    image_url = await create_meme_image(template, t1, t2)
    print(f"🔗 URL мема: {image_url}")

    # Публикация диалога с экранированием спецсимволов для безопасности HTML
    safe_headline = html.escape(approved_headline)
    safe_junior = html.escape(approved_junior)
    safe_reply = html.escape(approved_reply)

    junior_post = f"📰 <b>{safe_headline}</b>\n\n👶 <b>Соевый Джун:</b> {safe_junior}"
    try:
        sent = await bot.send_message(TG_CHAT, junior_post, parse_mode='HTML')
        print("✅ Пост Джуниора отправлен.")

        await asyncio.sleep(4)
        lead_caption = f"🚬 <b>Гигачад Тимлид:</b> {safe_reply}"
        await bot.send_photo(
            TG_CHAT,
            image_url,
            caption=lead_caption,
            reply_to_message_id=sent.message_id,
            parse_mode='HTML'
        )
        print("✅ Базированный мем опубликован в ответ!")
    except Exception as e:
        print(f"❌ Ошибка Telegram API: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
