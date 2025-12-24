#!/bin/sh

# Ждем backend
until curl -f http://backend:8030/health; do
  echo "Waiting for backend..."
  sleep 5
done

# Запуск приложения
dotnet AiRepetitor.dll
