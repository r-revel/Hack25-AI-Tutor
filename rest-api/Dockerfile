FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директорий для данных и логов
RUN mkdir -p /app/logs /app/data

ENV DATA_PATH=/data/cloud_ru_docs.jsonl
ENV CHROMA_DIR=/var/lib/chroma_db
ENV SQL_PATH=/var/lib/sqlite

# Открытие порта
EXPOSE 8030

# Команда запуска
CMD ["python", "src/main.py"]