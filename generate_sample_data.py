import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEAM = [
    ("Arjita Pandey", "arjita@company.com"),
    ("Adhrav Rai", "adhrav@company.com"),
    ("Rohan Sharma", "rohan@company.com"),
    ("Priya Nair", "priya@company.com"),
    ("Karan Mehta", "karan@company.com"),
    ("Sana Khan", "sana@company.com"),
]

MEETING_TITLES = [
    "Weekly Team Sync",
    "Client Review",
    "Sprint Planning",
    "Design Walkthrough",
    "Standup",
]

LOW_ATTENDANCE_THRESHOLD = 75.0
PRESENT_THRESHOLD = 90.0


def classify(pct):
    if pct >= PRESENT_THRESHOLD:
        return "Present"
    if pct >= LOW_ATTENDANCE_THRESHOLD:
        return "Partially Present"
    return "Low Attendance"


def fmt_clock(dt):
    return dt.strftime("%I:%M %p").lstrip("0")


def build_meeting(date_obj, index):
    title = random.choice(MEETING_TITLES)
    start_hour = random.choice([9, 10, 11, 14, 15, 16])
    start_minute = random.choice([0, 15, 30])
    duration_minutes = random.choice([30, 30, 45, 60, 60])

    start_dt = date_obj.replace(
        hour=start_hour, minute=start_minute, second=0, microsecond=0
    )
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    attendee_count = random.randint(3, len(TEAM))
    attendees = random.sample(TEAM, attendee_count)

    participants = []
    for name, email in attendees:
        # most people join near the start and stay till the end;
        # occasionally someone joins late / leaves early
        join_offset = random.choice([0, 0, 0, 2, 5, 10])
        leave_offset = random.choice([0, 0, 0, -3, -8, -15])

        join_dt = start_dt + timedelta(minutes=join_offset)
        leave_dt = end_dt + timedelta(minutes=leave_offset)
        if leave_dt <= join_dt:
            leave_dt = join_dt + timedelta(minutes=5)

        attended_minutes = max(1, int((leave_dt - join_dt).total_seconds() // 60))
        pct = round(min(100.0, (attended_minutes / duration_minutes) * 100), 1)

        participants.append(
            {
                "name": name,
                "email": email,
                "join_time": fmt_clock(join_dt),
                "leave_time": fmt_clock(leave_dt),
                "duration_minutes": attended_minutes,
                "attendance_percentage": pct,
                "status": classify(pct),
            }
        )

    return {
        "meeting_id": f"meet-{date_obj.strftime('%Y-%m-%d')}-{index:02d}",
        "meeting_title": title,
        "date": date_obj.strftime("%Y-%m-%d"),
        "start_time": start_dt.strftime("%H:%M:%S"),
        "end_time": end_dt.strftime("%H:%M:%S"),
        "duration_minutes": duration_minutes,
        "total_participants": len(participants),
        "participants": participants,
    }


def main():
    today = datetime(2026, 10, 6)
    start_date = today - timedelta(days=89)  # ~90 days of history

    day = start_date
    meeting_count = 0

    while day <= today:
        # skip weekends, and not every weekday has a meeting
        if day.weekday() < 5 and random.random() < 0.55:
            num_meetings_today = 1 if random.random() < 0.85 else 2
            for i in range(1, num_meetings_today + 1):
                meeting = build_meeting(day, i)
                filename = f"{meeting['meeting_id']}.json"
                path = os.path.join(OUTPUT_DIR, filename)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(meeting, f, indent=2)
                meeting_count += 1
        day += timedelta(days=1)

    print(f"Generated {meeting_count} sample meeting reports in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()