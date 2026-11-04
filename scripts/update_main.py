import json, sys, re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/"
FILE = Path("data/schedule.json")
FILE.parent.mkdir(exist_ok=True)

def main():
    print(f"📥 Загрузка основного расписания: {URL}")
    try:
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        events = []
        # Ищем таблицу. Пропускаем первую строку (заголовки)
        for row in soup.select("table tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 6: continue
            
            date_d = cells[1].get_text(strip=True)
            date_m = cells[2].get_text(strip=True)
            time_t = cells[3].get_text(strip=True)
            
            if not date_d or not date_m: continue
            
            # Формируем дату (предполагаем 2026 год, как в текущем контексте)
            date_iso = f"2026-{date_m.zfill(2)}-{date_d.zfill(2)}"
            
            start, end = (time_t.split("–") + [""])[:2] if "–" in time_t else (time_t, "")
            
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

        # 🔒 КРИТИЧЕСКАЯ ЗАЩИТА: если парсер нашел меньше 5 пар, что-то пошло не так. Не перезаписываем!
        if len(events) < 5:
            print(f"🛑 ОШИБКА: Найдено всего {len(events)} событий. Вероятно, структура сайта изменилась. Отмена сохранения.")
            sys.exit(1)

        # Загружаем старую историю, если файл существует
        old_data = {}
        if FILE.exists():
            with open(FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)

        new_data = {
            "events": events,
            "meta": {
                "source_url": URL,
                "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "error": False,
                "events_count": len(events),
                "history": old_data.get("meta", {}).get("history", []),
                "last_changed": old_data.get("meta", {}).get("last_changed"),
                "change_summary": old_data.get("meta", {}).get("change_summary")
            }
        }

        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Успешно сохранено: {len(events)} событий в {FILE}")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
