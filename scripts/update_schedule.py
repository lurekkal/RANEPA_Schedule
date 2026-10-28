import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://spb.ranepa.ru/raspisanie/ekonomicheskaya-bezopasnost-eb-5-23-01-eb-5-23-02/"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "schedule.json"
TZ = ZoneInfo("Europe/Moscow")
MONTHS = {"01":1,"02":2,"03":3,"04":4,"05":5,"06":6,"07":7,"08":8,"09":9,"10":10,"11":11,"12":12}
RU_MONTHS = {"января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,"июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12}
def now(): return datetime.now(TZ).isoformat(timespec="seconds")
def clean(s): return re.sub(r"\s+"," ",s or "").strip()
def parse():
    response = requests.get(URL, timeout=35, headers={"User-Agent":"Mozilla/5.0 (compatible; ScheduleMonitor/1.0)"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = None
    for t in soup.find_all("table"):
        txt = clean(t.get_text(" ", strip=True)).lower()
        if "преподаватель" in txt and "аудитория" in txt and ("предмет" in txt or "дисциплин" in txt):
            table = t; break
    if table is None:
        # The WordPress page may render schedule as a table-like block.
        rows = soup.select("tr")
        if not rows: raise RuntimeError("Не найдена таблица расписания на странице источника")
    else: rows = table.find_all("tr")
    year = datetime.now(TZ).year
    current_month = None
    events = []
    for tr in rows:
        cells = [clean(c.get_text(" ", strip=True)) for c in tr.find_all(["td","th"])]
        if len(cells) < 8: continue
        joined = " ".join(cells).lower()
        if "деньнедели" in joined or "день недели" in joined: continue
        # Expected columns: weekday, day, month, time, groups, type, subject, teacher position, teacher, room.
        cells = (cells + [""]*10)[:10]
        weekday, day, month, time, groups, typ, subject, position, teacher, room = cells
        day_match = re.search(r"\b(\d{1,2})\b", day)
        month_match = re.search(r"\b(\d{1,2})\b", month)
        if not day_match or not month_match or not subject: continue
        d, m = int(day_match.group(1)), int(month_match.group(1))
        if m not in range(1,13) or d not in range(1,32): continue
        # Semester pages often span Sep–Jan; infer year rollover from month transition.
        if current_month is not None and current_month >= 9 and m <= 2: year += 1
        current_month = m
        try: date = f"{year:04d}-{m:02d}-{d:02d}"; datetime.strptime(date,"%Y-%m-%d")
        except ValueError: continue
        tm = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", time)
        start, end = (tm.group(1),tm.group(2)) if tm else ("","")
        # Ignore completely empty decorative rows; keep self-study days when source lists them.
        if not subject: continue
        events.append({"date":date,"weekday":weekday,"start":start,"end":end,"groups":groups,"type":typ,"subject":subject,"teacher":teacher,"position":position,"room":room})
    # Deduplicate while preserving order.
    unique = {json.dumps(e,ensure_ascii=False,sort_keys=True):e for e in events}
    events = sorted(unique.values(),key=lambda e:(e["date"],e["start"],e["groups"],e["subject"]))
    if not events: raise RuntimeError("Источник доступен, но строки расписания не удалось разобрать; прежние данные сохранены.")
    return events

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"events":[],"meta":{},"history":[]}
    checked = now()
    try:
        events = parse()
        old_events = old.get("events",[])
        old_hash = hashlib.sha256(json.dumps(old_events,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        new_hash = hashlib.sha256(json.dumps(events,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        meta = old.get("meta",{})
        history = old.get("history",[])
        if not old_events or old_hash != new_hash:
            summary = "Загружена первая версия расписания." if not old_events else f"Расписание изменилось: было {len(old_events)} записей, стало {len(events)}."
            meta["last_changed"] = checked
            meta["change_summary"] = summary
            history.insert(0,{"date":checked,"kind":"изменение" if old_events else "первичная загрузка","summary":summary})
        meta.update({"last_checked":checked,"source_url":URL,"error":False,"events_count":len(events)})
        payload={"events":events,"meta":meta,"history":history[:50]}
    except Exception as exc:
        meta=old.get("meta",{})
        meta.update({"last_checked":checked,"error":True,"error_message":str(exc)})
        payload={**old,"meta":meta}
        print(f"Ошибка обновления; старые данные не удалены: {exc}")
        # Do not fail workflow: keep the site buildable, but expose failure state.
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Проверка завершена: {payload.get('meta',{}).get('events_count','без новых данных')} событий.")
if __name__ == "__main__": main()
