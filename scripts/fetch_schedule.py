#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build

CALENDAR_ID = "9cd23225c844f25d31822968e96d4359ecaa77ee7bdf56079ed773cb726a51f7@group.calendar.google.com"
DAYS_AHEAD = 60

COURSE_META = {
    "AG": {"summary_prefix": "AG", "transport": "local", "addr": "東區崇善路 435 號 1F"},
    "AD": {"summary_prefix": "AD", "transport": "train", "addr": "善化建國路 140 號 2F"},
    "TR": {"summary_prefix": "TR", "transport": "local", "addr": "東區府連東路 49 號"},
}

def get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("❌ 缺少 GOOGLE_SERVICE_ACCOUNT_JSON", file=sys.stderr); sys.exit(1)
    creds = service_account.Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/calendar.readonly"]
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def detect_type(summary):
    s = summary.upper()
    for code, meta in COURSE_META.items():
        if code in s:
            return code, meta
    return "OTHER", {"transport": "local", "addr": ""}

def parse_event(event):
    summary = event.get("summary", "")
    code, meta = detect_type(summary)
    start = event["start"].get("dateTime") or event["start"].get("date")
    end   = event["end"].get("dateTime")   or event["end"].get("date")
    if not start: return None
    tz = timezone(timedelta(hours=8))
    def to_dt(s):
        return datetime.fromisoformat(s).astimezone(tz) if "T" in s else datetime.fromisoformat(s + "T00:00:00+08:00")
    s_dt = to_dt(start)
    e_dt = to_dt(end) if end else None
    return {
        "date":      s_dt.strftime("%Y-%m-%d"),
        "name":      summary,
        "start":     s_dt.strftime("%H:%M"),
        "end":       e_dt.strftime("%H:%M") if e_dt else "",
        "type":      meta["transport"],
        "addr":      meta["addr"],
    }

def main():
    svc = get_service()
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    items = svc.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=DAYS_AHEAD)).isoformat(),
        singleEvents=True, orderBy="startTime"
    ).execute().get("items", [])

    schedule = [e for e in (parse_event(i) for i in items) if e]
    out = {
        "updatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "schedule":  schedule
    }
    path = os.path.join(os.path.dirname(__file__), "..", "schedule.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 完成，共 {len(schedule)} 筆課程")

if __name__ == "__main__":
    main()
