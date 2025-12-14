# RAG-Tutor (MVP, free stack)


## Требования
- Python 3.10+
- Ollama (если хотите локальный LLM через ollama), или замените вызов LLM в query.py


## Установка
1. Создать виртуальное окружение
```bash
python -m venv .venv
source .venv/bin/activate # или .venv\Scripts\activate на Windows
pip install -r requirements.txt
```

## Запуск
1. Создать эмбеддинги
```bash
python build_index.py --input data\\cloud_ru_docs.jsonl --persist_dir .\\db
```
2. Запуск (при включенной Ollama)
```bash
python ui.py
```
