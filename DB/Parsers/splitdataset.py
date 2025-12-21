import json
import os
from pathlib import Path
import re

# Путь к исходному файлу (замените на ваш реальный путь)
input_file = "D:\Work\MIFI\Hakhathon\R\cloud_ru_docs.jsonl"

# Путь к папке в которую будут сохраняться файлы
output_dir = "D:\Work\MIFI\Hakhathon\R\Content"
os.makedirs(output_dir, exist_ok=True)

def clean_content(text: str) -> str:
    if not text:
        return ""
    # Убираем дублирующийся маркированный список в конце (часто встречается)
    # Пример: "- Постановка задачи\n- Перед началом работы\n- 1. Создайте ..."
    lines = text.strip().splitlines()
    cleaned_lines = []
    for line in lines:
        # Пропускаем строки, начинающиеся с '-', если они идут *ближе к концу* и выглядят как повтор оглавления
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) < 100 and not stripped.startswith("- https://"):
            # Проверим, не идёт ли это после "## Результат" или "## Что дальше"
            if cleaned_lines and any(
                s in cleaned_lines[-1] for s in ["Результат", "Что дальше", "Сервер 1С развернут", "научились"]
            ):
                continue  # пропускаем повторяющееся оглавление
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # Доп. чистка: лишние пустые строки, начальные/конечные пробелы
    text = re.sub(r"\n{3,}", "\n\n", text)  # >2 пустых строки → 2
    text = text.strip()

    return text

def clean_title(title: str) -> str:
    return title.strip() if title else ""

# Обработка
with open(input_file, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f if line.strip()]

for i, rec in enumerate(records, start=1):
    title = clean_title(rec.get("title", ""))
    content = clean_content(rec.get("content", ""))

    title = title.replace('/', '_')
    data = {
        "title": title,
        "chapters": [
            {
                "name": title,
                "content": content,
                "debug": {
                    "start_page": 1,
                    "end_page": 1
                }
            }
        ]
    }

    out_path = f"{output_dir}/{data['title']}.json"
    with open(out_path, "w", encoding="utf-8") as out_f:
        json.dump(data, out_f, ensure_ascii=False, indent=2)
        
    print(f"{i}/{len(records)}")