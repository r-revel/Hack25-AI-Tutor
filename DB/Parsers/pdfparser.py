
import os
import re
import json
from PyPDF2 import PdfReader


def get_chapter_name(heading_pattern, clean, simple_page):
    match = heading_pattern.match(clean)
    if match:
        prefix = match.group(1).strip()
        title_body = match.group(2).strip()
        page_str = match.group(3)
    
        # Определяем уровень по prefix
        if prefix.lower().startswith('глава'):
            level = 1
            title = f"Глава {prefix.split()[1]} {title_body}".replace('..', '.')
        else:
            dots = prefix.count('.')
            level = dots + 1 if dots > 0 else 2
            title = f"{prefix} {title_body}".strip()
    
        # Страница
        page = int(page_str) if page_str and page_str.isdigit() else None
    
        # Fallback для страницы
        if page is None:
            pg = simple_page.search(clean)
            page = int(pg.group(1)) if pg else None
            
    return title, page
                
               
# PARSE TOC FROM TEXT
# Читаем содержимое листа содержания
def parse_toc_lines(lines):
    """Парсит строки оглавления → list[{title, level, page_start}]"""
    entries = []
    # Универсальный шаблон для: "Глава 1.", "1.1.", "2.3.4.", "A.1."
    heading_pattern = re.compile(
        r'^\s*(Глава\s+\S+\.|\d+\.\d*\.?|\d+\.\d+\.\d*\.?|[A-Z]\.\d*\.?)\s+(.+?)'
        r'(?:\s+\.+\s*(\d+))?\s*$',
        re.IGNORECASE
    )
    simple_page = re.compile(r'(\d+)$')

    prev_line = ''
    for line in lines:
        line_orig = str(line)
        line = line.strip()
        if not line:
            continue

        # Чистим многоточия и лишние пробелы
        clean = re.sub(r'\.{2,}', ' ', line)
        clean = re.sub(r'\s+', ' ', clean).strip()

        if clean== 'Глава':
            r = 0
            
        # --- Вариант 1: по шаблону заголовка + страница ---
        match = heading_pattern.match(clean)
        if match:
            prefix = match.group(1).strip()
            title_body = match.group(2).strip()
            page_str = match.group(3)

            # Определяем уровень по prefix
            if prefix.lower().startswith('глава'):
                level = 1
                title = f"Глава {prefix.split()[1]} {title_body}".replace('..', '.')
            else:
                dots = prefix.count('.')
                level = dots + 1 if dots > 0 else 2
                title = f"{prefix} {title_body}".strip()

            # Страница
            page = int(page_str) if page_str and page_str.isdigit() else None

            # Fallback для страницы
            if page is None:
                pg = simple_page.search(clean)
                page = int(pg.group(1)) if pg else None

            if page:
                entries.append({"title": title, "level": level, "page_start": page})
                
            else:
                dots = prefix.count('.')
                if dots <= 2 and page == None:
                    prev_line = clean
                
            continue
        
        else:
            if len(prev_line) > 1:
                clean = f"{prev_line} {clean}"
                title, page = get_chapter_name(heading_pattern, clean, simple_page)
                if page:
                               
                    entries.append({"title": title, "level": level, "page_start": page})
                    prev_line = ''
                    continue
                

        # --- Вариант 2: fallback — ищем "Глава" или начало с цифры + конец = число ---
        if "Глава" in clean or re.match(r'^\d+\.?\s', clean):
            pg = simple_page.search(clean)
            if pg:
                try:
                    page = int(pg.group(1))
                    title_part = clean[:pg.start()].strip()
                    level = 1 if "Глава" in title_part else 2
                    entries.append({"title": title_part, "level": level, "page_start": page})
                except:
                    pass

    # Фильтр: только адекватные страницы и уровни
    entries = [e for e in entries if 1 <= e["level"] <= 3 and e["page_start"] > 0]
    entries.sort(key=lambda x: x["page_start"])
    return entries



# Определяем лист СОДЕРЖАНИЕ
def extract_toc_text(pdf_reader, max_toc_pages=25):
    """
    Извлекает текст оглавления, читая подряд страницы от первого вхождения
    'Содержание' до тех пор, пока не будет найдена первая глава (по номеру страницы)
    или не закончится логическая структура оглавления.
    
    Возвращает: текст оглавления (все страницы подряд), или None.
    """
    KEYWORDS = ["Содержание", "Оглавление", "Contents", "Table of Contents"]
    total_pages = len(pdf_reader.pages)
    
    # 1. Ищем первую страницу с оглавлением
    toc_start_idx = None
    for i in range(total_pages):
        text = pdf_reader.pages[i].extract_text()
        if text and any(kw.lower() in text.lower() for kw in KEYWORDS):
            toc_start_idx = i
            break

    if toc_start_idx is None:
        print("оглавление не найдено.")
        return None

    print(f"найдено 'Содержание' на стр. {toc_start_idx + 1}")

    # 2. Собираем страницы оглавления постранично
    text_parts = []
    toc_pages_read = 0

    # Будем читать от toc_start_idx вперёд
    for idx in range(toc_start_idx, min(toc_start_idx + max_toc_pages, total_pages)):
        page_text = pdf_reader.pages[idx].extract_text()
        if not page_text:
            # Пустая страница — скорее всего, скан → остановимся
            break
        text_parts.append(page_text)
        toc_pages_read += 1

        # Анализ: проверим, не начинается ли эта страница с "Глава 1."?
        # (т.е. оглавление закончилось, началась книга)
        lines = page_text.splitlines()
        for line in lines[:5]:  # первые 5 строк — достаточны
            clean = re.sub(r'\s+', ' ', line.strip())
            if re.match(r'^Глава\s+1\.?\s', clean, re.IGNORECASE) or \
               re.match(r'^Chapter\s+1\.?\s', clean, re.IGNORECASE):
                dots = clean.count('.')
                if dots >= 4: continue
                
                # Возможно, это уже тело книги — проверим номер страницы в оглавлении
                # (но пока просто остановимся, чтобы не захватить лишнее)
                # Можно добавить: if idx >= toc_start_idx + 2 — тогда точно конец оглавления
                print(f"Обнаружено начало 'Глава 1' на стр. {idx + 1} — остановка сбора оглавления.")
                toc_pages_read = idx - toc_start_idx + 1
                break
        else:
            continue
        break  # выйти из внешнего цикла при обнаружении главы

    print(f"собрано {toc_pages_read} стр. оглавления (стр. {toc_start_idx + 1}–{toc_start_idx + toc_pages_read})")
    return "\n".join(text_parts)



# TEXT EXTRACTION (skip image pages)
# Извлекает текст из диапазона страниц, пропуская пустые (сканы).
# Страницы в книгах могут быть отсканированы и текста не иметь
def extract_page_range(reader, start_1b, end_1b):

    text_lines = []
    n = len(reader.pages)
    for p in range(start_1b - 1, min(end_1b, n)):
        raw = reader.pages[p].extract_text()
        if raw and raw.strip():
            clean = re.sub(r'\n\s*\n', '\n\n', raw)
            text_lines.append(f"--- Страница {p + 1} ---")
            text_lines.append(clean)
    return "\n".join(text_lines)


# Строим структуру содержания
import re

def normalize_heading(text):
    """Нормализует заголовок: убирает точки, пробелы, приводит к нижнему регистру."""
    match = re.sub(r'[\s\.]+', ' ', text).strip().lower()
    return match

def get_ngrams(s, n=2):
    """Разбивает строку на n-граммы (по умолчанию — биграммы)."""
    return {s[i:i+n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}

def jaccard_similarity(a, b, n=2):
    """Вычисляет схожесть Жаккара между двумя строками по n-граммам."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    set_a = get_ngrams(a, n)
    set_b = get_ngrams(b, n)
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0

# Агрессивная нормализация: удаляем всё кроме букв/цифр, нижний регистр, ё→е.
def aggressive_normalize(text):
    if not text:
        return ""
    text = re.sub(r'[^а-яА-Яa-zA-Z0-9ёЁ]', '', text)
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    return text.lower()

def strip_trailing_page_number(text):
    """
    Удаляет номер страницы в конце строки, если он отделён пробелами/точками.
    Примеры:
      "SciPy............................................ 28" → "SciPy"
      "1.1 Эволюционные алгоритмы 22" → "1.1 Эволюционные алгоритмы"
      "Глава 2.5 — Обучение 101" → "Глава 2.5 — Обучение"
      "Алгоритм NEAT 12обзоралгоритмаneat28" → оставит как есть (нет чистого числа в конце)
    """
    if not text:
        return text

    # Ищем в конце: (пробелы/точки/тире) + ЦИФРЫ + конец строки
    # Регулярка: \s*[\.\-—]*\s*(\d+)\s*$
    match = re.search(r'\s*[\.\-—]*\s*(\d+)\s*$', text)
    if match:
        # Убедимся, что перед цифрой — не буква (иначе это часть слова, например 'neat28')
        start_idx = match.start(1)
        if start_idx == 0 or not text[start_idx - 1].isalnum():
            # Цифра в самом конце, отделена — удаляем всю «хвостовую» часть
            return text[:match.start()].rstrip()
    return text

def if_chapter_starts_with(page_text, heading):
    clean_heading = strip_trailing_page_number(heading)
    norm_h = aggressive_normalize(clean_heading)
    norm_p = aggressive_normalize(page_text)
    
    if norm_p.startswith(norm_h):
        return True
    else:
        return False

def heading_appears_on_page(page_text, heading, 
                             exact_prefix_len=20, 
                             fuzzy_threshold=0.95):
    """
    Проверяет, встречается ли heading в page_text, устойчиво к:
    - разрывам слов (эволюци онные),
    - опечаткам,
    - лишним/недостающим пробелам и знакам.
    
    Методы:
    1. Точное вхождение нормализованной строки.
    2. Вхождение первых N символов (быстро и надёжно для уникальных заголовков).
    3. Fuzzy-сравнение по n-граммам (если 1–2 не сработали).
    """
    if not heading or not page_text:
        return False

    clean_heading = strip_trailing_page_number(heading)
    norm_h = aggressive_normalize(clean_heading)
    norm_p = aggressive_normalize(page_text)

    if not norm_h:
        return False

    # 1. Точное вхождение
    if norm_h in norm_p:
        return True

    # 2. Вхождение префикса (часто достаточно — заголовки длинные и уникальные)
    prefix_len = min(exact_prefix_len, len(norm_h))
    prefix = norm_h[:prefix_len]
    if prefix in norm_p:
        return True

    # 3. Fuzzy: ищем наилучшее совпадение окна ~len(norm_h)
    L = len(norm_h)
    if L == 0:
        return False

    best_sim = 0.0
    for i in range(max(0, len(norm_p) - L + 1)):
        window = norm_p[i:i + L]
        sim = jaccard_similarity(norm_h, window, n=2)
        if sim > best_sim:
            best_sim = sim
            if best_sim >= fuzzy_threshold:
                return True

    return best_sim >= fuzzy_threshold

def extract_chapter_content(reader, start_page_1b, next_chapter_title=None, total_pages=None):
    """
    Извлекает текст главы, начиная со start_page_1b,
    и останавливается, когда находит next_chapter_title (если задан).
    Возвращает: (content_text, actual_end_page_1b)
    """
    if total_pages is None:
        total_pages = len(reader.pages)

    content_lines = []
    actual_end = start_page_1b

    # Читаем от start_page_1b до конца или до обнаружения следующей главы
    for p_idx_0b in range(start_page_1b - 1, total_pages):
        page_num = p_idx_0b + 1
        raw = reader.pages[p_idx_0b].extract_text()
        if not raw:
            # Страница-скан: пропускаем, но продолжаем (глава может идти дальше)
            actual_end = page_num
            continue

        # Проверка: если ищем следующую главу — есть ли она на этой странице?
        if next_chapter_title and heading_appears_on_page(raw, next_chapter_title):
            # Нашли начало следующей главы → останавливаемся ДО этой страницы
            # Но: если мы только начали (page_num == start_page_1b), то глава — 0 страниц?
            # Решение: включаем эту страницу, НО обрезаем текст до заголовка
            # → упрощённый вариант: **не включаем** эту страницу в текущую главу
            break

        # Добавляем страницу в текущую главу
        clean = re.sub(r'\n\s*\n', '\n\n', raw)
        content_lines.append(f"--- Страница {page_num} ---")
        content_lines.append(clean)
        actual_end = page_num

    return "\n".join(content_lines), actual_end

def update_start_page_if_needed(data: dict) -> dict:
    """
    Обновляет data['debug']['start_page'], если в data['content']
    найдено первое вхождение шаблона '--- Страница N ---', и N != текущему start_page.
    
    :param data: словарь с ключами 'content' и 'debug' (в debug должен быть 'start_page')
    :return: обновлённый словарь (изменён in-place и возвращён)
    """
    content = data.get("content", "")
    debug = data.get("debug", {})
    current_start = debug.get("start_page", 0)

    # Ищем первое вхождение шаблона
    match = re.search(r"--- Страница\s+(\d+)\s+---", content)
    if match:
        detected_start = int(match.group(1))
        if detected_start != current_start:
            debug["start_page"] = detected_start
            # Опционально: можно также обновить end_page по аналогии, если нужно
    return data

def build_tree_and_fill(entries, total_pages, reader):
    """
    Строит дерево глав, но ИЗВЛЕКАЕТ содержимое ТОЛЬКО по появлению заголовков
    в тексте — номера страниц из оглавления используются ТОЛЬКО для сортировки.
    """
    if not entries:
        return []

    # Сортируем по page_start (для порядка), но не используем при извлечении
    entries = sorted(entries, key=lambda x: x.get("page_start", 0))

    # Список заголовков в правильном порядке (только уровень 1 и 2 для тела)
    ordered_headings = [e["title"] for e in entries if e.get("level", 1) <= 2]

    # Рекурсивное дерево пока оставим как есть — но наполнение будет flat-поиском
    # Для простоты: сначала сделаем плоскую структуру, потом свернём в дерево
    chapters_flat = []

    current_idx = 0  # индекс текущей главы в ordered_headings
    current_content_lines = []
    current_start_physical = 0

    start_page = entries[0]['page_start'] - 1
    if start_page == 0:
        start_page = entries[1]['page_start'] - 1
    
    # Проходим по ВСЕМ страницам книги подряд
    for p_idx_0b in range(start_page, total_pages):
        page_num = p_idx_0b + 1
        raw = reader.pages[p_idx_0b].extract_text()
        
        if not raw:
            continue

        raw = re.sub(r'\.{2,}', ' ', raw)
        raw = re.sub(r'\s+', ' ', raw).strip()
        
        # Проверяем: не начинается ли НОВАЯ глава на этой странице?
        next_heading = None
        if current_idx + 1 < len(ordered_headings):
            next_heading = ordered_headings[current_idx + 1]

        # Если текущая глава уже начата, ищем следующий заголовок
        if current_idx < len(ordered_headings):
            current_heading = ordered_headings[current_idx]
            # Проверим: может, ЭТО — начало ТЕКУЩЕЙ главы? (для первой)
            if current_idx == 0 and not current_content_lines:
                if heading_appears_on_page(raw, current_heading):
                    current_start_physical = page_num
                    
            # === Проверка: встречается ли ЗАГОЛОВОК СЛЕДУЮЩЕЙ главы на этой странице? ===
            if next_heading and heading_appears_on_page(raw, next_heading):
                # Найдём позицию (приблизительно) — ищем normalized substring
                clean_heading = strip_trailing_page_number(next_heading)
                norm_h = aggressive_normalize(clean_heading)
                norm_page = aggressive_normalize(raw)
    
                # Ищем начало совпадения в НЕнормализованном тексте (лучше сохранить регистр)
                # Используем "мягкое" сравнение: приведём к нижнему, удалим пунктуацию
                search_str = re.sub(r'[^а-яa-z0-9ё]', '', clean_heading.lower())
                search_in = re.sub(r'[^а-яa-z0-9ё]', '', raw.lower())
    
                pos = search_in.find(search_str)
                if pos == -1:
                    # fallback: не нашли позицию — добавим всю страницу в текущую главу
                    split_idx = len(raw)
                else:
                    # Найдём приблизительную позицию в исходном тексте
                    # Идём по символам raw и ищем, где накопленная "очищенная" строка достигнет pos
                    clean_count = 0
                    split_idx = 0
                    for i, ch in enumerate(raw):
                        if re.match(r'[а-яa-z0-9ё]', ch, re.IGNORECASE):
                            clean_count += 1
                        if clean_count > pos:
                            split_idx = i
                            break
    
                # Разделяем страницу:
                part_current = raw[:split_idx].strip()
                part_next = raw[split_idx:].strip()
    
                # Добавляем "остаток текущей главы"
                if part_current and current_idx < len(ordered_headings):
                    clean_cur = re.sub(r'\n\s*\n', '\n\n', part_current)
                    current_content_lines.append(f"--- Страница {page_num} ---")
                    current_content_lines.append(clean_cur)
    
    
                is_in = if_chapter_starts_with(raw, next_heading)
    
    
                # Закрываем текущую главу
                content = "\n".join(current_content_lines) if current_content_lines else "(Нет текста)"
                chapters_flat.append({
                    "title": ordered_headings[current_idx],
                    "content": content,
                    "debug": {"start_page": current_start_physical, "end_page": page_num - 1 if is_in == True else page_num}
                })
    
                # Начинаем следующую главу
                current_idx += 1
                current_content_lines = []
                current_start_physical = page_num
    
                # Новая глава получает "остаток страницы"
                if part_next and current_idx < len(ordered_headings):
                    clean_next = re.sub(r'\n\s*\n', '\n\n', part_next)
                    current_content_lines.append(f"--- Страница {page_num} --- (продолжение)")
                    current_content_lines.append(clean_next)
    
                # ⚠️ Важно: после этого — НЕ делать `continue`, если может быть ещё одна смена главы!
                # Проверим рекурсивно: а не начинается ли ещё одна глава на том же остатке?
                # Для простоты — сделаем цикл while для одной страницы
                remaining_text = part_next
                while (current_idx + 1 < len(ordered_headings)
                       and remaining_text
                       and heading_appears_on_page(remaining_text, ordered_headings[current_idx + 1])):
                    next_next_heading = ordered_headings[current_idx + 1]
                    search_str = re.sub(r'[^а-яa-z0-9ё]', '', strip_trailing_page_number(next_next_heading).lower())
                    search_in = re.sub(r'[^а-яa-z0-9ё]', '', remaining_text.lower())
                    pos = search_in.find(search_str)
                    if pos == -1:
                        break
    
                    # Находим split_idx в remaining_text
                    clean_count = 0
                    split_idx2 = 0
                    for i, ch in enumerate(remaining_text):
                        if re.match(r'[а-яa-z0-9ё]', ch, re.IGNORECASE):
                            clean_count += 1
                        if clean_count > pos:
                            split_idx2 = i
                            break
    
                    cur_part = remaining_text[:split_idx2].strip()
                    next_part = remaining_text[split_idx2:].strip()
    
                    # Сохраняем текущую (промежуточную) главу
                    if cur_part:
                        chapters_flat.append({
                            "title": ordered_headings[current_idx],
                            "content": cur_part,
                            "debug": {"start_page": page_num, "end_page": page_num}
                        })
    
                    current_idx += 1
                    remaining_text = next_part
    
                # Остаток (после всех заголовков) добавляем в последнюю начатую главу
                if remaining_text and current_idx < len(ordered_headings):
                    clean_rem = re.sub(r'\n\s*\n', '\n\n', remaining_text)
                    if not current_content_lines:
                        current_content_lines.append(f"--- Страница {page_num} --- (продолжение)")
                    current_content_lines.append(clean_rem)
    
                continue  # страница обработана — идём к следующей

        # Добавляем страницу в текущую главу
        if current_idx < len(ordered_headings):
            clean = re.sub(r'\n\s*\n', '\n\n', raw)
            current_content_lines.append(f"--- Страница {page_num} ---")
            current_content_lines.append(clean)

    # Последняя глава
    if current_idx < len(ordered_headings) and current_content_lines:
        content = "\n".join(current_content_lines)
        chapters_flat.append({
            "title": ordered_headings[current_idx],
            "content": content,
            "debug": {"start_page": current_start_physical, "end_page": total_pages}
        })
        
    for i in range(len(chapters_flat)):
        
        chapters_flat[i] = update_start_page_if_needed(chapters_flat[i])
        
    # Теперь свернём в иерархическое дерево по исходным entries
    def fold_into_tree(flat_list, all_entries):
        # Группируем flat_list по соответствию заголовка
        title_to_content = {ch["title"]: ch["content"] for ch in flat_list}
        title_to_debug = {ch["title"]: ch.get("debug", {}) for ch in flat_list}

        def build(entries_group, level=1):
            res = []
            i = 0
            while i < len(entries_group):
                e = entries_group[i]
                if e["level"] != level:
                    i += 1
                    continue
                node = {"name": e["title"]}
                # Дочерние — уровень+1
                children = []
                j = i + 1
                while j < len(entries_group) and entries_group[j]["level"] > level:
                    if entries_group[j]["level"] == level + 1:
                        children.append(entries_group[j])
                    j += 1
                if children:
                    node["chapters"] = build(children, level + 1)
                else:
                    node["content"] = title_to_content.get(e["title"], "(Не найдено)")
                    dbg = title_to_debug.get(e["title"], {})
                    if dbg:
                        node["debug"] = dbg
                res.append(node)
                i = j
            return res

        level1 = [e for e in all_entries if e["level"] == 1]
        return build(all_entries, 1)

    tree = fold_into_tree(chapters_flat, entries)
    return tree

# Извлекаем содержимое книги
def process_book(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        total = len(reader.pages)

        toc_text = extract_toc_text(reader)
        if not toc_text:
            print(f"Оглавление не найдено: {os.path.basename(pdf_path)}")
            return None

        lines = toc_text.splitlines()
        entries = parse_toc_lines(lines)
        if not entries:
            print(f"Не распознано глав: {os.path.basename(pdf_path)}")
            return None

        chapters_tree = build_tree_and_fill(entries, total, reader)

        title = os.path.splitext(os.path.basename(pdf_path))[0]
        return {
            "title": title,
            "chapters": chapters_tree
        }

    except Exception as e:
        print(f"❌ Ошибка обработки {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    folder = r"D:\Work\MIFI\Hakhathon\Books\ML_Python"
    if not os.path.isdir(folder):
        print("Папка не существует.")
        return

    pdf_files = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("PDF не найдены.")
        return

    print(f"Обнаружено {len(pdf_files)} PDF. Начинаю обработку...\n")

    success = 0
    for pdf in pdf_files:
        path = os.path.join(folder, pdf)
        print(f"{pdf}...")
        result = process_book(path)
        if result:
            out_path = os.path.join(folder, os.path.splitext(pdf)[0] + ".json")
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            n_top = len(result["chapters"]) if result["chapters"] else 0
            print(f"{os.path.basename(out_path)} — {n_top} глав")
            success += 1

    print(f"Готово! Успешно обработано: {success}/{len(pdf_files)} книг.")


if __name__ == "__main__":
    main()