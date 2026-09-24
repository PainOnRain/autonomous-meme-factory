import os
import asyncio
import io
import html
import re
import urllib.parse
import httpx
from openai import OpenAI
from telebot.async_telebot import AsyncTeleBot

# 1. Загрузка переменных окружения
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

async def get_fresh_news_pool():
    """Парсинг последних постов из Telegram-канала КБ"""
    url = "https://t.me/s/Cbpub"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    print(f"📡 Загружаем посты из канала КБ: {url}")
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as http_client:
            res = await http_client.get(url)
            if res.status_code != 200:
                print(f"⚠️ Ошибка загрузки страницы КБ: {res.status_code}")
                return []

            pattern = r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>'
            matches = re.findall(pattern, res.text, re.DOTALL)

            news = []
            for raw_html in matches:
                text = re.sub(r'<br\s*/?>', '\n', raw_html)
                text = re.sub(r'<[^>]+>', '', text)
                text = html.unescape(text).strip()

                lower_text = text.lower()
                is_ad = any(k in lower_text for k in ["erid:", "t.me/", "скидк", "промокод", "подписывайся", "розыгрыш"])
                if len(text) >= 35 and not is_ad:
                    first_lines = [l.strip() for l in text.split("\n") if l.strip()]
                    summary = " ".join(first_lines[:2])
                    news.append(summary[:220])

            unique_news = list(dict.fromkeys(news))[-6:][::-1]
            print(f"✅ Найдено новостей: {len(unique_news)}")
            return unique_news
    except Exception as e:
        print(f"❌ Ошибка парсинга КБ: {e}")
        return []

async def junior_pitch(headline):
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
    force = "Это последняя новость в пачке. Твой вердикт ОБЯЗАТЕЛЬНО: СТАТУС: ОДОБРЕНО." if is_last else ""
    templates_str = ", ".join(MEME_TEMPLATES)

    prompt = f"""
Инфоповод: "{headline}"
Нытьё Джуна: "{junior_msg}"

РОЛЬ: 
Ты — бескомпромиссный, предельно жёсткий пророссийский Гигачад-Тимлид. 
Ты презираешь соевых либералов, релокантов, нытиков и инфантилов. 
Твоя задача — не просто прокомментировать новость, а морально уничтожить Джуна за его слабость и сопли, припечатав его железной базой.

ПРАВИЛА ЖЁСТКОСТИ:
- Никакой вежливости, сглаживания углов или заумных лекций.
- Ответ должен быть ультра-коротким (1-2 хлестких, рубящих предложения).
- Бей точно в соевые триггеры: высмеивай самокаты, Верхний Ларс, тыквенный латте, панические атаки, "лапки" и страх перед реальной жизнью.
- Используй терминологию и вайб: "база", "сопли подотри", "на завод", "в окоп захотел?", "наши слоны", "размотали", "поплачь об этом", "чушпан", "ГОЙДА".

ОБРАЗЦЫ ОТВЕТОВ ДЛЯ ПОДРАЖАНИЯ (держи такой же градус):
- "Сопли подотри и марш закрывать таски, пока я тебе повестку в зубы не оформил."
- "Тревожно ему, гляньте на него. Наши парни под огнём снаряды подают, а ты от заголовка в штаны наложил, соя."
- "Плачь громче, твой вой из Верхнего Ларса до самого Кремля слышно. Иди на завод, дурь выбьют."
- "Ути-пути, лапки задрожали? Сдай свой самокат в металлолом и начни работать, чучело."

ЗАДАЧА:
1. Оцени инфоповод: если унылая ерунда — СТАТУС: ОТКЛОНЕНО. Если есть за что размотать сою — СТАТУС: ОДОБРЕНО.
2. Выбери мем-шаблон из списка: [{templates_str}].
3. Придумай верхний (ТЕКСТ_1) и нижний (ТЕКСТ_2) текст на русском КАПСОМ (по 2-3 убойных слова).
{force}

Формат ответа СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой максимально жесткий, ядовитый разнос Джуна>
ШАБЛОН: <шаблон>
ТЕКСТ_1: <текст 1>
ТЕКСТ_2: <текст 2>
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system", 
                    "content": "Ты безжалостный, токсичный гигачад-патриот. Ты общаешься короткими, циничными панчлайнами без цензуры и жалости к слабым."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка Тимлида: {e}")
        return None

async def download_meme_bytes(template, text1, text2):
    """Генерация и скачивание мема в память байтами"""
    t1_clean = re.sub(r'[/\\?%*:|"<>]', '', text1).strip() or "_"
    t2_clean = re.sub(r'[/\\?%*:|"<>]', '', text2).strip() or "_"

    # Формируем URL для Memegen с URL-encoding
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

    # Запасной вариант с дефолтным текстом
    fallback_url = f"https://api.memegen.link/images/{template}/ТРЕВОЖНО/НАШИ_СЛОНЫ.png"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            res = await http_client.get(fallback_url)
            if res.status_code == 200:
                return res.content
    except Exception:
        pass
    return None

async def run_factory():
    print("🚀 Старт фабрики...")
    news_pool = await get_fresh_news_pool()
    if not news_pool:
        print("❌ Новостей нет.")
        return

    approved_headline = None
    approved_junior = None
    approved_reply = None
    template = "clown"
    t1, t2 = "ТРЕВОЖНО", "НАШИ СЛОНЫ"

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
        print("❌ Инфоповод не выбран.")
        return

    # 1. Скачиваем картинку в буфер
    img_bytes = await download_meme_bytes(template, t1, t2)

    # 2. Публикация первого поста Джуниора
    safe_headline = html.escape(approved_headline)
    safe_junior = html.escape(approved_junior)
    safe_reply = html.escape(approved_reply)

    junior_post = f"📰 <b>{safe_headline}</b>\n\n👶 <b>Соевый Джун:</b> {safe_junior}"
    
    try:
        await bot.send_message(TG_CHAT, junior_post, parse_mode='HTML')
        print("✅ Пост Джуниора отправлен в канал.")

        # Небольшая пауза между публикациями
        await asyncio.sleep(3)

        # 3. Публикация ответа Тимлида с картинкой
        lead_caption = f"🚬 <b>Гигачад Тимлид:</b> {safe_reply}"
        
        if img_bytes:
            photo_file = io.BytesIO(img_bytes)
            photo_file.name = "meme.png"
            await bot.send_photo(TG_CHAT, photo_file, caption=lead_caption, parse_mode='HTML')
            print("✅ Ответный пост Тимлида с мемом успешно отправлен!")
        else:
            await bot.send_message(TG_CHAT, lead_caption, parse_mode='HTML')
            print("⚠️ Мем не скачался, отправлен текстовый ответ Тимлида.")

    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
