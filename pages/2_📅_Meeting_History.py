import glob
import json
import os

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Meeting History", page_icon="📅", layout="wide")


@st.cache_data(ttl=30)
def load_all_reports():
    reports = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    # newest first
    reports.sort(key=lambda r: (r.get("date", ""), r.get("start_time", "")), reverse=True)
    return reports


@st.cache_data(ttl=30)
def load_attendee_roster():
    """The master list of everyone expected to attend meetings
    (managed on the 'Manage Attendees' page). Used to work out who's
    truly Absent (on the roster, but missing from a meeting) rather
    than just relying on Low Attendance as a stand-in."""
    if not os.path.exists(ATTENDEES_FILE):
        return []
    try:
        with open(ATTENDEES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def get_true_absentees(meeting, roster):
    """Roster members who don't appear anywhere in this meeting's
    participant list at all."""
    attended_names = {p.get("name", "").strip().lower() for p in meeting.get("participants", [])}
    return [person for person in roster if person.get("name", "").strip().lower() not in attended_names]


def format_time_12h(time_str):
    """Turns '10:00:00' into '10:00 AM'."""
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


st.title("📅 Meeting History")

reports = load_all_reports()
roster = load_attendee_roster()

if not reports:
    st.info(
        "No meeting reports found yet. Once the bot records a meeting "
        "(or sample reports are added to the `reports` folder), meetings "
        "will show up here."
    )
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
        (r for r in reports if r.get("meeting_id") == st.session_state.selected_meeting_id),
        None,
    )

    if meeting is None:
        st.warning("That meeting couldn't be found.")
        st.button("← Back to Meeting History", on_click=back_to_list)
        st.stop()

    st.button("← Back to Meeting History", on_click=back_to_list)

    participants = meeting.get("participants", [])
    total_attendees = len(participants)
    low_attendance_count = sum(1 for p in participants if p.get("status") == "Low Attendance")
    true_absentees = get_true_absentees(meeting, roster)

    st.markdown(f"## {meeting.get('meeting_title', 'Meeting')}")
    date_display = meeting.get("date", "")
    try:
        date_display = pd.to_datetime(meeting.get("date")).strftime("%d %B %Y")
    except (ValueError, TypeError):
        pass
    st.caption(
        f"{date_display} · {format_time_12h(meeting.get('start_time', ''))} "
        f"– {format_time_12h(meeting.get('end_time', ''))}"
    )

    if not roster:
        st.caption(
            "ℹ️ No attendee list set up yet — add people on the **Manage Attendees** "
            "page to see true Absent counts here (people who were expected but never joined)."
        )

    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    kpi_col1.metric("Total Attendees", total_attendees)
    kpi_col2.metric("Low Attendance", low_attendance_count)
    kpi_col3.metric("Absent", len(true_absentees))

    st.divider()

    table_rows = []
    for p in participants:
        table_rows.append(
            {
                "Name": p.get("name", ""),
                "Joining Time": p.get("join_time", "—"),
                "Leaving Time": p.get("leave_time", "—"),
                "Duration": f"{p.get('duration_minutes', 0)} min",
                "Status": p.get("status", ""),
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
            color = "#e74c3c"
        elif row["Status"] == "Low Attendance":
            color = "#f39c12"
        else:
            color = "#2ecc71"
        return [f"color: {color}" if col == "Status" else "" for col in row.index]

    st.dataframe(
        table_df.style.apply(highlight_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )


# LIST VIEW


else:

    search_col, date_col = st.columns([2, 1])

    with search_col:
        search_text = st.text_input("Search by meeting name", placeholder="e.g. Weekly Team Sync")

    with date_col:
        date_filter = st.date_input("Filter by date", value=None)

    filtered_reports = reports

    if search_text:
        filtered_reports = [
            r for r in filtered_reports
            if search_text.lower() in r.get("meeting_title", "").lower()
        ]

    if date_filter:
        filtered_reports = [
            r for r in filtered_reports
            if r.get("date") == date_filter.isoformat()
        ]

    st.caption(f"{len(filtered_reports)} meeting(s)")

    if not filtered_reports:
        st.info("No meetings match your search/filter.")

    for meeting in filtered_reports:
        participants = meeting.get("participants", [])
        total = len(participants)
        low_count = sum(1 for p in participants if p.get("status") == "Low Attendance")
        absent_count = len(get_true_absentees(meeting, roster))

        try:
            date_display = pd.to_datetime(meeting.get("date")).strftime("%d %b %Y")
        except (ValueError, TypeError):
            date_display = meeting.get("date", "")

        with st.container(border=True):
            card_col1, card_col2 = st.columns([4, 1])

            with card_col1:
                st.markdown(f"### {meeting.get('meeting_title', 'Meeting')}")
                st.write(
                    f"{date_display} · "
                    f"{format_time_12h(meeting.get('start_time', ''))} – "
                    f"{format_time_12h(meeting.get('end_time', ''))}"
                )
                st.caption(
                    f"{total} attendee(s)"
                    + (f" · ⚠️ {low_count} low attendance" if low_count else "")
                    + (f" · 🔴 {absent_count} absent" if absent_count else "")
                )

            with card_col2:
                st.button(
                    "View →",
                    key=f"open_{meeting.get('meeting_id')}",
                    use_container_width=True,
                    on_click=open_meeting,
                    args=(meeting.get("meeting_id"),),
                )