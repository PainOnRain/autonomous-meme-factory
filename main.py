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

async def get_fresh_news_pool():
    """Собираем пул из 6 свежих новостей с Хабра"""
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://habr.com/ru/rss/articles/?fl=ru")
        if not feed.entries:
            return []
        # Забираем заголовки первых 6 статей
        return [entry.title for entry in feed.entries[:6]]
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []

async def junior_pitch(headline):
    """Джуниор приносит инфоповод с горящими глазами"""
    prompt = f"""
Ты наивный, гиперактивный Джуниор. Ты прибежал в личку к Тимлиду с новостью с Хабра:
"{headline}"

Напиши короткий (1-2 предложения) восторженный или паникующий заход. 
Используй модные слова (AI, стек, оптимизация, переписать всё, сингулярность). 
Пиши ТОЛЬКО свою реплику.
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
        return "Шеф, глянь новость, это же революция!"

async def lead_evaluation(headline, junior_msg, is_last_chance=False):
    """
    Тимлид: токсичный, агрессивный циник. 
    Оценивает, можно ли сделать из этого смешной мем.
    """
    force_instruction = ""
    if is_last_chance:
        force_instruction = "Это последняя новость в ленте, поэтому ты ОБЯЗАН поставить СТАТУС: ОДОБРЕНО, но с максимальным презрением."

    prompt = f"""
Новость: "{headline}"
Джуниор предлагает: "{junior_msg}"

Ты — 45-летний предельно токсичный, грубый и выгоревший Тимлид. 
Ты ненавидишь глупые вопросы, зумерский энтузиазм и корпоративную чушь.
Твоя задача — оценить новость для мема.

ПРАВИЛА:
1. Если новость скучная, унылая корпоративная вода или банальщина — ОТКЛОНИ её. 
Опусти Джуниора на землю матом/жестким сарказмом в стиле «Где ты этот мусор откопал? Иди ищи нормальный инфоповод, пока я тебе доступ к репозиторию не закрыл».
2. Если новость абсурдная, жизненная, про поломки, ИИ-хайп или распил — ОДОБРИ её. 
Выдай едкий циничный комментарий и придумай идею мема.
{force_instruction}

МЕМ-ПРОМПТ:
Запрещены красивые лица, фотомодели и неоновый арт. 
Только бытовой абсурд, флеш-фотография (amateur flash snapshot), проклятый реализм (cursed image aesthetic).

Формат вывода СТРОГО:
СТАТУС: [ОДОБРЕНО или ОТКЛОНЕНО]
ОТВЕТ: <твой грубый ответ Джуниору>
ПРОМПТ: <описание мемной сцены на английском (только если ОДОБРЕНО, иначе оставь пустым)>
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

    total_candidates = len(news_pool)
    print(f"📋 В очереди на проверку {total_candidates} новостей.\n")

    # Конвейер отбора: гоняем Джуниора, пока Тимлид не утвердит
    for idx, headline in enumerate(news_pool, 1):
        is_last = (idx == total_candidates)
        print(f"--- [Попытка {idx}/{total_candidates}] ---")
        print(f"📰 Новость: {headline}")

        j_msg = await junior_pitch(headline)
        print(f"👶 Джуниор: {j_msg}")

        lead_raw = await lead_evaluation(headline, j_msg, is_last_chance=is_last)
        if not lead_raw:
            continue

        status = "ОТКЛОНЕНО"
        lead_reply = "Мусор. Переделывай."
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
            approved_img_prompt = img_prompt or "stressed IT worker screaming at broken computer, amateur flash photo"
            break
        else:
            print("❌ Тимлид забраковал новость. Джуниор идёт искать дальше...\n")
            await asyncio.sleep(1)

    if not approved_headline:
        print("❌ Ни одна новость не прошла редсовет.")
        return

    # Генерация визуала через Flux
    encoded_img_prompt = urllib.parse.quote(f"{approved_img_prompt}, raw amateur photo, flash photography, cursed meme vibe")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=1024&height=1024&nologo=true&private=true&model=flux"

    # Отправка в Telegram
    junior_post_text = (
        f"📰 <b>{approved_headline}</b>\n\n"
        f"👶 <b>Джуниор:</b> {approved_junior_msg}"
    )

    try:
        sent_msg = await bot.send_message(TG_CHAT, junior_post_text, parse_mode='HTML')
        print("✅ Пост Джуниора опубликован.")

        print("⏳ Тимлид печатает разнос...")
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
