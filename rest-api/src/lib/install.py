import requests
from typing import List, Dict
import time

OLLAMA_URL = "http://localhost:11434"

class InstallSystem:
    def __init__(self, list_model: List[str] | None = None):
        self._list_model = list_model if list_model is not None else []
        self._installed_models = self._get_installed_models()

    def _get_installed_models(self) -> List[str]:
        """Получает список установленных моделей через Ollama API"""
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["model"] for model in data["models"]]
        except Exception as e:
            print(f"Ошибка при получении списка моделей: {e}")
            return []

    def check_model_installed(self, model_name: str) -> bool:
        """Проверяет, установлена ли конкретная модель"""
        base_name = model_name.split(':')[0]
        return any(model.startswith(base_name) for model in self._installed_models)

    def install_model(self, model_name: str) -> bool:
        """Устанавливает модель через Ollama API"""
        if self.check_model_installed(model_name):
            print(f"Модель '{model_name}' уже установлена")
            return True

        print(f"Установка модели '{model_name}'...")
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name},
                stream=True
            )
            response.raise_for_status()
            
            # Читаем потоковый ответ
            for line in response.iter_lines():
                if line:
                    # Можно парсить прогресс, но для простоты просто ждем
                    pass
            
            print(f"Модель '{model_name}' успешно установлена")
            self._installed_models = self._get_installed_models()
            return True
        except Exception as e:
            print(f"Ошибка при установке модели '{model_name}': {e}")
            return False

    def install(self) -> Dict[str, bool]:
        """Устанавливает все модели из списка"""
        if not self._list_model:
            print("Список моделей для установки пуст")
            return {}

        results = {}
        for model in self._list_model:
            results[model] = self.install_model(model)
            time.sleep(1)

        return results