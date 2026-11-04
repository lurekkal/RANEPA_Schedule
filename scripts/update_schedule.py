import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE = "https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/"
SESSION_SOURCE = "https://spb.ranepa.ru/raspisanie/eb-5-23-01-02/"
DATA_DIR = Path("data")
SCHEDULE_FILE = DATA_DIR / "schedule.json"
SESSION_FILE = DATA_DIR / "session.json"

DATA_DIR.mkdir(exist_ok=True)

def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def parse_ranepa_page(html: str, source_url: str) -> dict:
    """
    Специализированный парсер для сайта spb.ranepa.ru.
    Ищет div.schedule-item__row вместо tr.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # Ищем все строки расписания по уникальному классу сайта
    rows = soup.select("div.schedule-item__row")
    
    for row in rows:
        try:
            # Извлекаем данные по точным классам из view-source
            date_el = row.select_one("div.schedule-item__date")
            time_el = row.select_one("div.schedule-item__time")
            subject_el = row.select_one("div.schedule-item__subject")
            
            if not all([date_el, time_el, subject_el]):
                continue

            date_text = date_el.get_text(strip=True)
            time_text = time_el.get_text(strip=True)
            subject_text = subject_el.get_text(strip=True)
            
            # Остальные поля могут отсутствовать в некоторых строках
            type_el = row.select_one("div.schedule-item__type")
            teacher_el = row.select_one("div.schedule-item__teacher")
            room_el = row.select_one("div.schedule-item__room")
            groups_el = row.select_one("div.schedule-item__groups")

            type_text = type_el.get_text(strip=True) if type_el else ""
            teacher_text = teacher_el.get_text(strip=True) if teacher_el else ""
            room_text = room_el.get_text(strip=True) if room_el else ""
            groups_text = groups_el.get_text(strip=True) if groups_el else ""

            # Форматируем дату DD.MM.YYYY -> YYYY-MM-DD
            if "." in date_text:
                parts = date_text.split(".")
                if len(parts) == 3:
                    d, m, y = parts[0], parts[1], parts[2]
                    y = f"20{y}" if len(y) == 2 else y
                    date_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                else:
                    date_iso = date_text
            else:
                date_iso = date_text

            # Форматируем время HH:MM–HH:MM
            if "–" in time_text or "-" in time_text:
                start, end = re.split(r"[–\-]", time_text, maxsplit=1)
                start = start.strip()
                end = end.strip()
            else:
                start = time_text.strip()
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
        except Exception as e:
            print(f"⚠️ Пропуск строки: {e}")
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
    if not old_data or not old_data.get("events"):
        return {
            "kind": "первичная загрузка",
            "summary": f"Загружена первая версия ({len(new_data.get('events', []))} записей).",
            "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    
    old_keys = {(e["date"], e["start"], e["subject"]) for e in old_data.get("events", [])}
    new_keys = {(e["date"], e["start"], e["subject"]) for e in new_data.get("events", [])}
    
    added = len(new_keys - old_keys)
    removed = len(old_keys - new_keys)
    
    changed = 0
    old_map = {(e["date"], e["start"], e["subject"]): e for e in old_data.get("events", [])}
    new_map = {(e["date"], e["start"], e["subject"]): e for e in new_data.get("events", [])}
    for key in new_keys & old_keys:
        if old_map[key].get("room") != new_map[key].get("room") or \
           old_map[key].get("teacher") != new_map[key].get("teacher"):
            changed += 1

    if not (added or removed or changed):
        return None
    
    parts = []
    if added or removed:
        parts.append(f"было {len(old_keys)} записей, стало {len(new_keys)}")
    if changed:
        parts.append(f"изменено {changed} пар")
    
    return {
        "kind": "изменение",
        "summary": f"Расписание изменилось: {'. '.join(parts)}.",
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

def update_history(meta: dict, change: dict) -> dict:
    history = meta.get("history", [])
    history.insert(0, change)
    meta["history"] = history[:10]
    meta["last_changed"] = change["date"]
    meta["change_summary"] = change["summary"]
    return meta

def save_json(filepath: Path, data: dict):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранено: {filepath} ({len(data.get('events', []))} событий)")

def load_json(filepath: Path) -> dict:
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("🚀 Запуск синхронного обновления...")
    now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # --- ОСНОВНОЕ РАСПИСАНИЕ ---
    print(f"\n📥 1/2 Основное: {SOURCE}")
    try:
        html = fetch_html(SOURCE)
        new_schedule = parse_ranepa_page(html, SOURCE)
    except Exception as e:
        print(f"❌ Ошибка сети: {e}")
        return

    # ЗАЩИТА: Не перезаписываем, если парсер ничего не нашел
    if not new_schedule["events"]:
        print("🛑 КРИТИЧЕСКАЯ ОШИБКА: Парсер вернул 0 событий. schedule.json НЕ обновлен.")
        print("🛑 Возможно, сайт изменил верстку. Проверь селекторы.")
        return

    old_schedule = load_json(SCHEDULE_FILE)
    change = compare_schedules(old_schedule, new_schedule)
    
    if change:
        print(f"🔄 Изменения: {change['summary']}")
        new_schedule["meta"] = update_history(new_schedule["meta"], change)
    else:
        print("✅ Нет изменений. История сохранена.")
        new_schedule["meta"]["history"] = old_schedule.get("meta", {}).get("history", [])
        new_schedule["meta"]["last_changed"] = old_schedule.get("meta", {}).get("last_changed")
        new_schedule["meta"]["change_summary"] = old_schedule.get("meta", {}).get("change_summary")

    save_json(SCHEDULE_FILE, new_schedule)
    
    # --- СЕССИЯ ---
    print(f"\n📥 2/2 Сессия: {SESSION_SOURCE}")
    try:
        session_html = fetch_html(SESSION_SOURCE)
        new_session = parse_ranepa_page(session_html, SESSION_SOURCE)
    except Exception as e:
        print(f"❌ Ошибка сети сессии: {e}")
        return

    if not new_session["events"]:
        print("⚠️ Сессия: парсер вернул 0 событий. session.json не обновлен.")
    else:
        save_json(SESSION_FILE, new_session)
    
    print("\n🎉 Готово!")

if __name__ == "__main__":
    main()
