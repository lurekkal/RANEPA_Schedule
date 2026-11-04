import json, sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

URL = "https://spb.ranepa.ru/raspisanie/eb-5-23-01-02/"
FILE = Path("data/session.json")
FILE.parent.mkdir(exist_ok=True)

def main():
    print(f"📥 Загрузка расписания сессии (через браузер): {URL}")
    
    html_content = ""
    with sync_playwright() as p:
        try:
            # Запускаем Chromium в headless-режиме (без интерфейса)
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            
            print("   ⏳ Загрузка страницы...")
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            
            # Пытаемся найти выпадающий список и выбрать "100" или "Все"
            try:
                selects = page.locator("select").all()
                for sel in selects:
                    options = sel.locator("option").all_text_contents()
                    # Ищем опцию, где есть "100", "Все" или "All"
                    target_option = next((opt.strip() for opt in options if "100" in opt or "Все" in opt or "All" in opt), None)
                    if target_option:
                        print(f"   ✅ Найдено '{target_option}'. Выбираем...")
                        sel.select_option(label=target_option)
                        # Ждем, пока таблица перерисуется
                        page.wait_for_timeout(2500) 
                        break
            except Exception as e:
                print(f"   ⚠️ Не удалось переключить лимит через UI: {e}")
            
            html_content = page.content()
            browser.close()
            
        except Exception as e:
            print(f"❌ Ошибка браузера: {e}")
            return

    # Парсим полученный полный HTML
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        events = []
        
        for row in soup.select("table tr")[1:]: # Пропускаем заголовок
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            
            date_d = cells[1].get_text(strip=True)
            date_m = cells[2].get_text(strip=True)
            time_t = cells[3].get_text(strip=True)
            
            if not date_d or not date_m:
                continue
            
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

        if len(events) == 0:
            print("⚠️ Найдено 0 событий. Файл не обновлен.")
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
        print(f"✅ Успешно сохранено: {len(events)} событий сессии!")

    except Exception as e:
        print(f"❌ Ошибка парсинга HTML: {e}")

if __name__ == "__main__":
    main()
