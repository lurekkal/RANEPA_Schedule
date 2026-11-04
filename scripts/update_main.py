import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/"
FILE = Path("data/schedule.json")
FILE.parent.mkdir(exist_ok=True)


def get_academic_year(month: int) -> int:
    """
    Определяет год по правилу учебного года:
    - Сентябрь (9) – Декабрь (12) → текущий год
    - Январь (1) – Август (8) → следующий год
    """
    current_year = datetime.now().year
    if month >= 9:
        return current_year
    else:
        return current_year + 1


def parse_schedule(html: str) -> list:
    """Парсит HTML-страницу и возвращает список событий."""
    soup = BeautifulSoup(html, "html.parser")
    events = []

    for row in soup.select("table tr")[1:]:  # Пропускаем заголовок
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        date_d = cells[1].get_text(strip=True)
        date_m = cells[2].get_text(strip=True)
        time_t = cells[3].get_text(strip=True)

        if not date_d or not date_m:
            continue

        # Умное определение года
        try:
            month_num = int(date_m)
            year = get_academic_year(month_num)
            date_iso = f"{year}-{date_m.zfill(2)}-{date_d.zfill(2)}"
        except ValueError:
            continue

        # Форматируем время
        if "–" in time_t:
            start, end = time_t.split("–", 1)
        elif "-" in time_t:
            start, end = time_t.split("-", 1)
        else:
            start, end = time_t, ""

        events.append({
            "date": date_iso,
            "start": start.strip(),
            "end": end.strip(),
            "subject": cells[6].get_text(strip=True) if len(cells) > 6 else "",
            "type": cells[5].get_text(strip=True) if len(cells) > 5 else "",
            "teacher": f"{cells[7].get_text(strip=True)} {cells[8].get_text(strip=True)}".strip() if len(cells) > 8 else "",
            "room": cells[9].get_text(strip=True) if len(cells) > 9 else "",
            "groups": cells[4].get_text(strip=True) if len(cells) > 4 else "",
        })

    return events


def compare_schedules(old_events: list, new_events: list) -> dict | None:
    """Сравнивает старое и новое расписание, возвращает описание изменений."""
    if not old_events:
        return {
            "kind": "первичная загрузка",
            "summary": f"Загружена первая версия ({len(new_events)} записей).",
            "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    old_keys = {(e["date"], e["start"], e["subject"]) for e in old_events}
    new_keys = {(e["date"], e["start"], e["subject"]) for e in new_events}

    added = len(new_keys - old_keys)
    removed = len(old_keys - new_keys)

    changed = 0
    old_map = {(e["date"], e["start"], e["subject"]): e for e in old_events}
    new_map = {(e["date"], e["start"], e["subject"]): e for e in new_events}
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


def main():
    print(f"📥 Загрузка основного расписания: {URL}")
    try:
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        events = parse_schedule(r.text)
    except Exception as e:
        print(f"❌ Критическая ошибка сети: {e}")
        sys.exit(1)

    # 🔒 ЗАЩИТА: если парсер нашел меньше 5 пар — что-то сломалось, не перезаписываем!
    if len(events) < 5:
        print(f"🛑 ОШИБКА: Найдено всего {len(events)} событий. Вероятно, структура сайта изменилась. Отмена сохранения.")
        sys.exit(1)

    # Загружаем старый файл (если есть)
    old_data = {}
    if FILE.exists():
        with open(FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)

    old_events = old_data.get("events", [])
    change = compare_schedules(old_events, events)

    # Формируем meta
    meta = {
        "source_url": URL,
        "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "error": False,
        "events_count": len(events),
        "history": old_data.get("meta", {}).get("history", []),
        "last_changed": old_data.get("meta", {}).get("last_changed"),
        "change_summary": old_data.get("meta", {}).get("change_summary"),
    }

    # Если есть изменения — добавляем в историю
    if change:
        print(f"🔄 {change['summary']}")
        history = meta["history"]
        history.insert(0, change)
        meta["history"] = history[:10]  # Храним последние 10
        meta["last_changed"] = change["date"]
        meta["change_summary"] = change["summary"]
    else:
        print("✅ Изменений не обнаружено.")

    new_data = {"events": events, "meta": meta}

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено: {len(events)} событий в {FILE}")


if __name__ == "__main__":
    main()
