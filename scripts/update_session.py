import json, sys, re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://spb.ranepa.ru/raspisanie/eb-5-23-01-02/"
FILE = Path("data/session.json")
FILE.parent.mkdir(exist_ok=True)

def main():
    print(f"📥 Загрузка расписания сессии: {URL}")
    try:
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        events = []
        for row in soup.select("table tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 6: continue
            
            date_d = cells[1].get_text(strip=True)
            date_m = cells[2].get_text(strip=True)
            time_t = cells[3].get_text(strip=True)
            
            if not date_d or not date_m: continue
            
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

        # 🔒 ЗАЩИТА: для сессии порог ниже, но если 0, то не сохраняем
        if len(events) == 0:
            print("⚠️ Предупреждение: Найдено 0 событий сессии. Файл не обновлен.")
            return

        new_data = {
            "events": events,
            "meta": {
                "source_url": URL,
                "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "error": False,
                "events_count": len(events)
            }
        }

        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Успешно сохранено: {len(events)} событий сессии в {FILE}")

    except Exception as e:
        print(f"❌ Критическая ошибка сессии: {e}")
        # Не делаем sys.exit(1), чтобы не ломать весь workflow, если сессии просто нет

if __name__ == "__main__":
    main()
