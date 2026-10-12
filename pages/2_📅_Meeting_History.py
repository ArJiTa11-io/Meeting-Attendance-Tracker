import glob
import json
import os

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "meeting-bot", "output", "reports")
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Meeting History", page_icon="📅", layout="wide")


@st.cache_data(ttl=2)
def load_all_reports():
    reports = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
                if isinstance(report, dict):
                    reports.append(report)
        except (json.JSONDecodeError, OSError):
            continue

    reports.sort(key=lambda r: (r.get("date", ""), r.get("start_time", "")), reverse=True)
    return reports


@st.cache_data(ttl=30)
def load_attendee_roster():
    
    if not os.path.exists(ATTENDEES_FILE):
        return []
    try:
        with open(ATTENDEES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def get_true_absentees(participants, roster):
   
    attended_names = {p.get("name", "").strip().lower() for p in participants}
    return [person for person in roster if person.get("name", "").strip().lower() not in attended_names]


def format_time_12h(time_str):
    if not time_str:
        return "--"
    try:
        parsed = pd.to_datetime(time_str)
        return parsed.strftime("%I:%M %p")
    except (ValueError, TypeError):
        try:
            hour, minute, _ = time_str.split(":")
            hour = int(hour)
            suffix = "AM" if hour < 12 else "PM"
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12
            return f"{hour_12}:{minute} {suffix}"
        except (ValueError, AttributeError):
            return time_str


def format_date(date_str):
    if not date_str:
        return "--"
    try:
        return pd.to_datetime(date_str).strftime("%d %B %Y")
    except (ValueError, TypeError):
        return date_str


def normalize_participants(participants):
   
    if isinstance(participants, list):
        return participants

    if isinstance(participants, dict):
        normalized = []
        for name, data in participants.items():
            if not isinstance(data, dict):
                data = {}
            normalized.append(
                {
                    "name": name,
                    "email": data.get("email", ""),
                    "join_time": data.get("join_time"),
                    "leave_time": data.get("leave_time"),
                    "duration_minutes": data.get("duration_minutes", 0),
                    "attendance_percentage": data.get("attendance_percentage"),
                    "status": data.get("status", ""),
                    "sessions": data.get("sessions", []),
                }
            )
        return normalized

    return []


st.title("📅 Meeting History")

reports = load_all_reports()
roster = load_attendee_roster()

if not reports:
    st.info(
       
    )
    st.caption(f"Looking for reports in: {REPORTS_DIR}")
    st.stop()

if "selected_meeting_id" not in st.session_state:
    st.session_state.selected_meeting_id = None


def open_meeting(meeting_id):
    st.session_state.selected_meeting_id = meeting_id


def back_to_list():
    st.session_state.selected_meeting_id = None


# DETAIL VIEW


if st.session_state.selected_meeting_id is not None:

    meeting = next(
        (report for report in reports if report.get("meeting_id") == st.session_state.selected_meeting_id),
        None,
    )

    if meeting is None:
        st.warning("That meeting couldn't be found.")
        st.button("← Back to Meeting History", on_click=back_to_list)
        st.stop()

    st.button("← Back to Meeting History", on_click=back_to_list)

    participants = normalize_participants(meeting.get("participants", []))
    total_attendees = len(participants)
    low_attendance_count = sum(1 for p in participants if p.get("status") == "Low Attendance")
    true_absentees = get_true_absentees(participants, roster)

    meeting_title = meeting.get("meeting_title") or meeting.get("meeting_id", "Meeting")
    st.markdown(f"## {meeting_title}")

    date_display = format_date(meeting.get("date"))
    st.caption(
        f"{date_display} · {format_time_12h(meeting.get('start_time'))} "
        f"– {format_time_12h(meeting.get('end_time'))}"
    )

    if not roster:
        st.caption(
            
        )

    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    kpi_col1.metric("Total Attendees", total_attendees)
    kpi_col2.metric("Low Attendance", low_attendance_count)
    kpi_col3.metric("Absent", len(true_absentees))

    st.divider()

    if participants or true_absentees:
        table_rows = []

        for participant in participants:
            table_rows.append(
                {
                    "Name": participant.get("name", ""),
                    "Joining Time": format_time_12h(participant.get("join_time")),
                    "Leaving Time": (
                        format_time_12h(participant.get("leave_time"))
                        if participant.get("leave_time")
                        else "Still in meeting"
                    ),
                    "Duration": f"{participant.get('duration_minutes', 0)} min",
                    "Status": participant.get("status", ""),
                }
            )

        # roster members who never joined this meeting at all
        for person in true_absentees:
            table_rows.append(
                {
                    "Name": person.get("name", ""),
                    "Joining Time": "—",
                    "Leaving Time": "—",
                    "Duration": "—",
                    "Status": "Absent",
                }
            )

        table_df = pd.DataFrame(table_rows)

        def highlight_status(row):
            if row["Status"] == "Absent":
                status_color = "#e74c3c"
            elif row["Status"] == "Low Attendance":
                status_color = "#f39c12"
            elif row["Status"] == "Partially Present":
                status_color = "#f39c12"
            elif row["Status"] == "Present":
                status_color = "#2ecc71"
            else:
                status_color = ""
            return [f"color: {status_color}" if column == "Status" else "" for column in row.index]

        st.dataframe(
            table_df.style.apply(highlight_status, axis=1),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No participants were detected for this meeting.")

    st.divider()
    st.subheader("Session History")

    has_sessions = False
    for participant in participants:
        sessions = participant.get("sessions", [])
        if not sessions:
            continue

        has_sessions = True
        participant_name = participant.get("name", "Unknown")

        with st.expander(f"👤 {participant_name}"):
            session_rows = []
            for index, session in enumerate(sessions, start=1):
                join_time = session.get("join_time")
                leave_time = session.get("leave_time")

                try:
                    join_dt = pd.to_datetime(join_time)
                    if leave_time:
                        leave_dt = pd.to_datetime(leave_time)
                        duration_seconds = (leave_dt - join_dt).total_seconds()
                    else:
                        duration_seconds = None
                except (ValueError, TypeError):
                    duration_seconds = None

                duration_text = (
                    f"{duration_seconds / 60:.1f} min" if duration_seconds is not None else "Still in meeting"
                )

                session_rows.append(
                    {
                        "Session": index,
                        "Joining Time": format_time_12h(join_time),
                        "Leaving Time": (format_time_12h(leave_time) if leave_time else "Still in meeting"),
                        "Duration": duration_text,
                    }
                )

            if session_rows:
                st.dataframe(pd.DataFrame(session_rows), width="stretch", hide_index=True)

    if not has_sessions:
        st.info("No session history available.")


# LIST VIEW


else:

    search_col, date_col = st.columns([2, 1])

    with search_col:
        search_text = st.text_input("Search by meeting name", placeholder="e.g. Weekly Team Sync")

    with date_col:
        date_filter = st.date_input("Filter by date", value=None)

    filtered_reports = reports

    if search_text:
        search_lower = search_text.lower()
        filtered_reports = [
            report for report in filtered_reports
            if search_lower in (report.get("meeting_title", "") or "").lower()
        ]

    if date_filter:
        filtered_reports = [
            report for report in filtered_reports
            if report.get("date") == date_filter.isoformat()
        ]

    st.caption(f"{len(filtered_reports)} meeting(s)")

    if not filtered_reports:
        st.info("No meetings match your search/filter.")

    for report_index, meeting in enumerate(filtered_reports):
        participants = normalize_participants(meeting.get("participants", []))
        total = len(participants)
        low_count = sum(1 for p in participants if p.get("status") == "Low Attendance")
        absent_count = len(get_true_absentees(participants, roster))

        meeting_title = meeting.get("meeting_title") or meeting.get("meeting_id", "Meeting")
        date_display = format_date(meeting.get("date"))
        meeting_status = meeting.get("status", "completed")

        with st.container(border=True):
            card_col1, card_col2 = st.columns([4, 1])

            with card_col1:
                st.markdown(f"### {meeting_title}")
                st.write(
                    f"{date_display} · "
                    f"{format_time_12h(meeting.get('start_time'))} "
                    f"– {format_time_12h(meeting.get('end_time'))}"
                )

                caption_parts = [f"{total} attendee(s)"]
                if low_count:
                    caption_parts.append(f"⚠️ {low_count} low attendance")
                if absent_count:
                    caption_parts.append(f"🔴 {absent_count} absent")
                if meeting_status == "completed":
                    caption_parts.append("✅ Completed")

                st.caption(" · ".join(caption_parts))

            with card_col2:
                st.button(
                    "View →",
                    key=f"open_{meeting.get('meeting_id')}_{report_index}",
                    width="stretch",
                    on_click=open_meeting,
                    args=(meeting.get("meeting_id"),),
                )