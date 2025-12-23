# rest-api\src\lib\seed_topics.py
import json
import re
import crud
import lib.schemas as schemas


# =========================
# helpers
# =========================

BLACKLIST_PHRASES = [
    "Эта статья полезна",
    "Начать тест",
    "Вы будете использовать",
    "Практические руководства",
]


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_title(title: str, content: str) -> str:
    if not title or not content:
        return content

    title_low = title.lower()
    content_low = content.lower()

    if content_low.startswith(title_low):
        return content[len(title):].strip()

    return content


def remove_blacklist(text: str) -> str:
    for phrase in BLACKLIST_PHRASES:
        text = text.replace(phrase, "")
    return text.strip()


def extract_intro(content: str, max_len: int = 400) -> str:
    """
    Берём первый осмысленный абзац
    """
    if not content:
        return ""

    # делим на абзацы
    paragraphs = re.split(r"\n\s*\n", content)

    for p in paragraphs:
        p = normalize(p)
        if len(p) >= 60:
            return p[:max_len]

    # fallback
    return normalize(content)[:max_len]


def build_topic_fields(data: dict):
    raw_title = data.get("title", "")
    raw_content = data.get("content", "")

    title = normalize(raw_title)
    content = raw_content

    content = strip_title(title, content)
    content = remove_blacklist(content)
    content = normalize(content)

    description = extract_intro(content)

    return title, description, content


# =========================
# seed function
# =========================

def seed_topics_from_jsonl(db, path: str):
    """
    Сид тем из JSONL-файла
    """

    if crud.get_topics(db, skip=0, limit=1):
        print("📚 Topics already exist")
        return

    print("🌱 Seeding topics from JSONL:", path)

    created = 0
    skipped = 0

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(f"⚠️ Line {line_no}: invalid JSON")
                skipped += 1
                continue

            title, description, clean_content = build_topic_fields(data)

            if not title or not clean_content:
                skipped += 1
                continue

            find_topic = crud.get_topic_title(db=db, title=title)

            if (find_topic == None):
                topic = schemas.TopicCreate(
                    title=title,
                    description=description,
                    image="default.png",
                    json=json.dumps(
                        {
                            **data,
                            "clean_content": clean_content
                        },
                        ensure_ascii=False
                    )
                )
            else:
                skipped += 1
                
            crud.create_topic(db=db, topic=topic)
            created += 1

    print(f"✅ Topics created: {created}")
    print(f"⏭️ Skipped: {skipped}")
