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
Ты наивный, суетливый Джуниор. Ты прибежал к Тимлиду с новостью:
"{headline}"

Напиши короткий (1-2 предложения) восторженный или паникующий заход в рабочий чат.
Используй модные зумерские баззворды. Выдай ТОЛЬКО свою реплику.
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
        return "Шеф, ты видел? Это же полностью перевернёт всю индустрию!"

async def lead_evaluation(headline, junior_msg, is_last_chance=False):
    force_instruction = ""
    if is_last_chance:
        force_instruction = "Это последний инфоповод, ставь СТАТУС: ОДОБРЕНО, но обстеби новость с максимальной злобой."

    prompt = f"""
Новость: "{headline}"
Джуниор: "{junior_msg}"

Ты — 45-летний злой, токсичный и циничный Тимлид. 
Ты ненавидишь хайп и корпоративную чушь.

1. Если новость скучная вода — ОТКЛОНИ. Пошли Джуниора искать нормальную тему.
2. Если новость смешная или абсурдная — ОДОБРИ. Уничтожь наивность Джуниора едким ответом.
{force_instruction}

ПРАВИЛО ГЕНЕРАЦИИ МЕМА ДЛЯ [ПРОМПТ]:
НИКАКИХ красивых людей, 3D-графики, VR-очков, киберпанка и постеров!
Мем должен быть смешным сам по себе. Выбери ОДИН из стилей:
- ВАРИАНТ А (Cursed Photo): Абсурдная сцена из жизни со вспышкой, снятая на дешёвый телефон (например: дед с паяльником и вантузом перед гигантским механизмом, серверная замотанная синей изолентой, человек в панике перед горящим чайником).
- ВАРИАНТ B (Животные): Ошалевший кот с выпученными глазами, макака в рабочей каске с молотком, енот в проводах.
- ВАРИАНТ C (Wojak/Комикс): Смешной интернет-мем стиль, crying soyjak, classic rage comic panel.

Формат вывода СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой токсичный саркастичный ответ>
ПРОМПТ: <описание мема на английском, hilarious internet meme, cursed low quality funny photo, direct harsh flash, absurd humor>
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

async def run_factory():
    news_pool = await get_fresh_news_pool()
    if not news_pool:
        print("❌ Не удалось получить новости.")
        return

    approved_headline = None
    approved_junior_msg = None
    approved_lead_reply = None
    approved_img_prompt = None

    total = len(news_pool)
    print(f"📋 В очереди {total} новостей.\n")

    for idx, headline in enumerate(news_pool, 1):
        is_last = (idx == total)
        print(f"--- [Попытка {idx}/{total}] ---")
        print(f"📰 {headline}")

        j_msg = await junior_pitch(headline)
        print(f"👶 Джуниор: {j_msg}")

        lead_raw = await lead_evaluation(headline, j_msg, is_last_chance=is_last)
        if not lead_raw:
            continue

        status = "ОТКЛОНЕНО"
        lead_reply = "Опять бред притащил."
        img_prompt = ""

        for line in lead_raw.split("\n"):
            line = line.strip()
            if line.startswith("СТАТУС:"):
                status = "ОДОБРЕНО" if "ОДОБРЕНО" in line.upper() else "ОТКЛОНЕНО"
            elif line.startswith("ОТВЕТ:"):
                lead_reply = line.replace("ОТВЕТ:", "").strip()
            elif line.startswith("ПРОМПТ:"):
                img_prompt = line.replace("ПРОМПТ:", "").strip()

        print(f"🚬 Тимлид ({status}): {lead_reply}\n")

        if status == "ОДОБРЕНО":
            approved_headline = headline
            approved_junior_msg = j_msg
            approved_lead_reply = lead_reply
            approved_img_prompt = img_prompt or "funny shocked cat staring at broken tech, amateur flash photo"
            break
        else:
            await asyncio.sleep(1)

    if not approved_headline:
        return

    # Задаем жесткий анти-глянцевый стиль для Flux
    meme_modifiers = (
        "hilarious funny meme, cursed image aesthetic, amateur grainy snapshot, "
        "harsh direct flash, 2000s internet meme energy, absurd, no 3d render, no cinematic art"
    )
    final_prompt = f"{approved_img_prompt}, {meme_modifiers}"
    encoded_img_prompt = urllib.parse.quote(final_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=1024&height=1024&nologo=true&private=true&model=flux"

    # Отправка сообщений
    junior_post_text = (
        f"📰 <b>{approved_headline}</b>\n\n"
        f"👶 <b>Джуниор:</b> {approved_junior_msg}"
    )

    try:
        sent_msg = await bot.send_message(TG_CHAT, junior_post_text, parse_mode='HTML')
        print("✅ Пост Джуниора опубликован.")

        print("⏳ Тимлид генерирует ответ и мем...")
        await asyncio.sleep(4)

        lead_caption = f"🚬 <b>Тимлид:</b> {approved_lead_reply}"
        await bot.send_photo(
            TG_CHAT,
            image_url,
            caption=lead_caption,
            reply_to_message_id=sent_msg.message_id,
            parse_mode='HTML'
        )
        print("✅ Мем успешно отправлен в ответ!")
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(run_factory())
