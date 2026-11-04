import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# === Конфигурация ===
SOURCE = "https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/"
SESSION_SOURCE = "https://spb.ranepa.ru/raspisanie/eb-5-23-01-02/"
DATA_DIR = Path("data")
SCHEDULE_FILE = DATA_DIR / "schedule.json"
SESSION_FILE = DATA_DIR / "session.json"

DATA_DIR.mkdir(exist_ok=True)

# === Утилиты ===
def fetch_html(url: str) -> str:
    """Загружает HTML-страницу с заголовками обычного браузера."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def parse_schedule_page(html: str, source_url: str) -> dict:
    """
    Парсит HTML-страницу расписания.
    Возвращает структуру, которую ожидает твой фронтенд.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # Ищем все строки таблицы. 
    # ВАЖНО: Если сайт использует специфические классы, их можно добавить в select().
    # Сейчас скрипт ищет любые tr, внутри которых есть время (например, "12:00–14:50")
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
            
        # Собираем весь текст строки для проверки
        row_text = row.get_text(separator=" ", strip=True)
        
        # Пропускаем строки, где нет времени (это заголовки или мусор)
        if not re.search(r"\d{2}:\d{2}", row_text):
            continue

        try:
            # Адаптируй индексы [0], [1] и т.д., если порядок столбцов на сайте другой
            date_text = cells[0].get_text(strip=True)
            time_text = cells[1].get_text(strip=True)
            subject_text = cells[2].get_text(strip=True)
            
            # Пытаемся взять остальные ячейки, если они есть
            type_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            teacher_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            room_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            groups_text = cells[6].get_text(strip=True) if len(cells) > 6 else ""

            # Форматируем дату в ISO (YYYY-MM-DD)
            if "." in date_text:
                d, m, y = date_text.split(".")
                # Если год из 2 цифр, превращаем в 4
                y = f"20{y}" if len(y) == 2 else y
                date_iso = f"{y}-{m}-{d}"
            else:
                date_iso = date_text

            # Форматируем время
            if "–" in time_text or "-" in time_text:
                start, end = re.split(r"[–\-]", time_text)
                start = start.strip()
                end = end.strip()
            else:
                start = time_text
                end = ""

            events.append({
                "date": date_iso,
                "start": start,
                "end": end,
                "subject": subject_text,
                "type": type_text,
                "teacher": teacher_text,
                "room": room_text,
                "groups": groups_text,
            })
        except Exception:
            # Пропускаем битые строки, чтобы не ломать весь парсинг
            continue

    return {
        "events": events,
        "meta": {
            "source_url": source_url,
            "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": False,
            "events_count": len(events),
        }
    }


def compare_schedules(old_data: dict, new_data: dict) -> dict | None:
    """Сравнивает старое и новое расписание, возвращает описание изменений."""
    if not old_data or not old_data.get("events"):
        return {
            "kind": "первичная загрузка",
            "summary": f"Загружена первая версия расписания ({len(new_data.get('events', []))} записей).",
            "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    
    old_events = {(e["date"], e["start"], e["subject"]): e for e in old_data.get("events", [])}
    new_events = {(e["date"], e["start"], e["subject"]): e for e in new_data.get("events", [])}
    
    added = [k for k in new_events if k not in old_events]
    removed = [k for k in old_events if k not in new_events]
    
    # Проверяем изменения в аудиториях/преподавателях
    changed = []
    for key in new_events:
        if key in old_events:
            if old_events[key].get("room") != new_events[key].get("room") or \
               old_events[key].get("teacher") != new_events[key].get("teacher"):
                changed.append(key)

    if not (added or removed or changed):
        return None  # Изменений нет
    
    parts = []
    if added: parts.append(f"было {len(old_events)} записей, стало {len(new_events)}")
    if changed: parts.append(f"изменено {len(changed)} пар (аудитория/преподаватель)")
    
    return {
        "kind": "изменение",
        "summary": f"Расписание изменилось: {'. '.join(parts)}.",
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def update_history(meta: dict, change: dict) -> dict:
    """Добавляет изменение в историю (максимум 10 записей)."""
    history = meta.get("history", [])
    history.insert(0, change)
    meta["history"] = history[:10]
    meta["last_changed"] = change["date"]
    meta["change_summary"] = change["summary"]
    return meta


def save_json(filepath: Path, data: dict):
    """Сохраняет данные в JSON без пробелов в ключах."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранено: {filepath} ({len(data.get('events', []))} событий)")


def load_json(filepath: Path) -> dict:
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# === ГЛАВНАЯ ЛОГИКА (Выполняется за один запуск) ===
def main():
    print("🚀 Запуск синхронного обновления расписания...")
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # ---------------------------------------------------------
    # ШАГ 1: Основное расписание
    # ---------------------------------------------------------
    print(f"\n📥 1/2 Загрузка основного расписания: {SOURCE}")
    try:
        html = fetch_html(SOURCE)
        new_schedule = parse_schedule_page(html, SOURCE)
    except Exception as e:
        print(f"❌ Ошибка основного расписания: {e}")
        new_schedule = {
            "events": [],
            "meta": {"source_url": SOURCE, "last_checked": now_str, "error": True, "error_message": str(e)}
        }

    old_schedule = load_json(SCHEDULE_FILE)
    change = compare_schedules(old_schedule, new_schedule)
    
    if change:
        print(f"🔄 Обнаружены изменения: {change['summary']}")
        new_schedule["meta"] = update_history(new_schedule["meta"], change)
    else:
        print("✅ Изменений в основном расписании нет. Сохраняем историю.")
        new_schedule["meta"]["history"] = old_schedule.get("meta", {}).get("history", [])
        new_schedule["meta"]["last_changed"] = old_schedule.get("meta", {}).get("last_changed")
        new_schedule["meta"]["change_summary"] = old_schedule.get("meta", {}).get("change_summary")

    save_json(SCHEDULE_FILE, new_schedule)
    
    # ---------------------------------------------------------
    # ШАГ 2: Расписание сессии (ТОТ ЖЕ МОМЕНТ ВРЕМЕНИ)
    # ---------------------------------------------------------
    print(f"\n📥 2/2 Загрузка расписания сессии: {SESSION_SOURCE}")
    try:
        session_html = fetch_html(SESSION_SOURCE)
        new_session = parse_schedule_page(session_html, SESSION_SOURCE)
    except Exception as e:
        print(f"❌ Ошибка расписания сессии: {e}")
        new_session = {
            "events": [],
            "meta": {"source_url": SESSION_SOURCE, "last_checked": now_str, "error": True, "error_message": str(e)}
        }

    # Для сессии историю изменений пока не ведем (или можно добавить по аналогии), 
    # просто сохраняем чистые данные.
    save_json(SESSION_FILE, new_session)
    
    print("\n🎉 Готово! Оба файла обновлены синхронно.")


if __name__ == "__main__":
    main()
