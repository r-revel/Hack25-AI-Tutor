from langchain_community.llms import Ollama
import re
from typing import List, Tuple, Dict
import time


class RussianSwearDetector:
    def __init__(self, model_name: str = "qwen2.5:7b"):
        # Базовый список матерных корней (упрощённо)
        self.swear_patterns = [
            r'\b[хx][уy][йеёяю]\w*\b',
            r'\bп[иi][зз3][дд]\w*\b',
            r'\b[еe][бб6]\w*\b',
            r'\bбл[яяa][тт]\w*\b',
            r'\b[сc][уy][кк]\w*\b',
            # добавьте свои паттерны
        ]
        self.patterns = [re.compile(p, re.IGNORECASE)
                         for p in self.swear_patterns]

        # Инициализация модели Ollama через LangChain
        self.llm = Ollama(model=model_name)

    def regex_check(self, text: str) -> Tuple[bool, List[str]]:
        """Быстрая проверка по regex"""
        found_words = []
        for pattern in self.patterns:
            matches = pattern.findall(text)
            if matches:
                found_words.extend(matches)
        return len(found_words) > 0, found_words

    def ai_check(self, text: str) -> bool:
        """Проверка контекста через модель Ollama"""
        prompt = f"""Текст содержит мат или оскорбления? Ответь одним словом: ДА или НЕТ.
        Текст: {text}"""

        try:
            response = self.llm.invoke(prompt)
            answer = response.strip().upper()
            return "ДА" in answer
        except Exception as e:
            print(f"Ошибка при обращении к модели: {e}")
            return False

    def check(self, text: str) -> Dict:
        # 1. Быстрая проверка по regex
        swear_found, words = self.regex_check(text)

        # 2. Если не нашли явного мата, проверяем контекст через AI
        method = "regex"
        if not swear_found:
            swear_found = self.ai_check(text)
            method = "ai" if swear_found else "regex"

        return {
            "has_swear": swear_found,
            "found_words": words,
            "method": method
        }

