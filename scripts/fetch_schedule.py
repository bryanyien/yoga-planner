#!/usr/bin/env python3
"""
fetch_schedule.py
從 Google Calendar 讀取 Betty 的瑜伽課表，
產生 schedule.json 供 index.html 動態載入。
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── 設定 ──────────────────────────────────────────────────────────────────────

CALENDAR_ID = (
    "9cd23225c844f25d31822968e96d4359ecaa77ee7bdf56079ed773cb726a51f7"
    "@group.calendar.google.com"
)

DAYS_AHEAD = 60

# 課程代碼 → 地點資訊對應表
# type: "train" = 搭火車, "local" = 騎機車
COURSE_META = {
    "YD": {
        "label": "YD 課程",
        "location": "Yoga Dairy 瑜伽日記",
        "address": "台南市善化區建國路 140 號 2F",
        "station": "善化火車站",
        "transport": "train",
        "type": "train",
        "bikeMin": 0,  # 不騎機車去，搭火車
    },
    "AG": {
        "label": "AG 課程",
        "location": "AG Studios 台南崇善",
        "address": "台南市東區崇善路 435 號 1F",
        "station": None,
        "transport": "local",
        "type": "local",
        "bikeMin": 10,  # 預設機車時間（分鐘）
    },
    "健美": {
        "label": "健美課程",
        "location": "健美洋行 南一中體育館",
        "address": "台南市東區東寧路 12 號",
        "station": None,
        "transport": "local",
        "type": "local",
        "bikeMin": 13,
    },
    "TR": {
        "label": "TR 課程",
        "location": "TriAngel Yoga 三角瑜伽",
        "address": "台南市東區府連東路 49 號",
        "station": None,
        "transport": "local",
        "type": "local",
        "bikeMin": 11,
    },
}


def get_calendar_service():
    """建立 Google Calendar API 服務（使用 Service Account）。"""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("❌ 缺少環境變數 GOOGLE_SERVICE_ACCOUNT_JSON", file=sys.stderr)
        sys.exit(1)

    creds_info = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=scopes
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def detect_course_type(summary: str) -> str:
    """
    從行事曆標題偵測課程代碼。
    規則：取標題去除特殊符號後的首字來判斷。
    - YD 開頭 → YD（Yoga Dairy）
    - AG 開頭 → AG（AG Studios）
    - 健美 開頭（可能有 ❇️ 前綴） → 健美（健美洋行）
    - TR 開頭 → TR（TriAngel）
    """
    # 去除常見特殊符號和空白，取前幾個字元判斷
    import re
    # 移除所有 emoji 和特殊符號，只留文字
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', summary).strip()

    if cleaned.startswith('YD'):
        return 'YD'
    if cleaned.startswith('AG'):
        return 'AG'
    if cleaned.startswith('健美'):
        return '健美'
    if cleaned.startswith('TR'):
        return 'TR'

    # 相容舊的 AD 格式（過渡期）
    if cleaned.startswith('AD'):
        return 'YD'  # AD 舊格式視同 YD

    return "UNKNOWN"


def parse_event(event: dict) -> dict | None:
    """將 Google Calendar 事件轉成課表項目。"""
    summary = event.get("summary", "")
    course_type = detect_course_type(summary)

    start = event["start"].get("dateTime") or event["start"].get("date")
    end = event["end"].get("dateTime") or event["end"].get("date")

    if not start:
        return None

    if "T" in start:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end) if end else None
    else:
        start_dt = datetime.fromisoformat(start + "T00:00:00+08:00")
        end_dt = None

    tz_tw = timezone(timedelta(hours=8))
    start_dt = start_dt.astimezone(tz_tw)
    end_dt = end_dt.astimezone(tz_tw) if end_dt else None

    meta = COURSE_META.get(course_type, {
        "label": summary,
        "location": "未知地點",
        "address": "",
        "station": None,
        "transport": "local",
        "type": "local",
        "bikeMin": 10,
    })

    return {
        "id": event.get("id", ""),
        "name": summary,
        "courseType": course_type,
        "label": meta["label"],
        "location": meta["location"],
        "address": meta["address"],
        "station": meta["station"],
        "type": meta["type"],
        "bikeMin": meta["bikeMin"],
        "date": start_dt.strftime("%Y-%m-%d"),
        "weekday": ["一", "二", "三", "四", "五", "六", "日"][start_dt.weekday()],
        "start": start_dt.strftime("%H:%M"),
        "end": end_dt.strftime("%H:%M") if end_dt else None,
    }


def fetch_events() -> list[dict]:
    """從 Google Calendar 抓取未來 DAYS_AHEAD 天的事件。"""
    service = get_calendar_service()

    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=DAYS_AHEAD)).isoformat()

    result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    print(f"✅ 共取得 {len(events)} 個行事曆事件")

    parsed = []
    for e in events:
        item = parse_event(e)
        if item:
            parsed.append(item)

    return parsed


def main():
    print("📅 開始讀取 Google Calendar 課表…")
    events = fetch_events()

    output = {
        "updatedAt": datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M"
        ),
        "schedule": events,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "schedule.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ schedule.json 已更新，共 {len(events)} 筆課程")


if __name__ == "__main__":
    main()
