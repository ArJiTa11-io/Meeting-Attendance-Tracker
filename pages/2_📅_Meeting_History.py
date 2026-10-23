
import glob
import json
import os

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "meeting-bot", "output", "reports")
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Meeting History", page_icon="📅", layout="wide")


# -------------------- Data loading and normalization --------------------

def normalize_name(value):
    return " ".join(str(value or "").split()).casefold()


def normalize_roster(raw):
    if not isinstance(raw, list):
        return []

    people = []
    seen = set()

    for item in raw:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("display_name") or "").strip()
        else:
            continue

        key = normalize_name(name)
        if name and key and key not in seen:
            people.append({"name": name})
            seen.add(key)

    return people


def normalize_participants(raw):
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]

    if isinstance(raw, dict):
        participants = []
        for name, details in raw.items():
            details = details if isinstance(details, dict) else {}
            participants.append({
                "name": name,
                "email": details.get("email", ""),
                "join_time": details.get("join_time"),
                "leave_time": details.get("leave_time"),
                "duration_minutes": details.get("duration_minutes", 0),
                "attendance_percentage": details.get("attendance_percentage"),
                "status": details.get("status", ""),
                "sessions": details.get("sessions", []),
            })
        return participants

    return []


@st.cache_data(ttl=2)
def load_all_reports():
    reports = []

    for path in glob.glob(os.path.join(REPORTS_DIR, "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as file:
                report = json.load(file)
            if isinstance(report, dict):
                report["_source_file"] = os.path.basename(path)
                reports.append(report)
        except (json.JSONDecodeError, OSError):
            # A report may be in the middle of being written by the bot.
            continue

    def sort_key(report):
        date_text = str(report.get("date") or "")
        time_text = str(report.get("start_time") or "")
        parsed = pd.to_datetime(f"{date_text} {time_text}", errors="coerce")
        return parsed if not pd.isna(parsed) else pd.Timestamp.min

    reports.sort(key=sort_key, reverse=True)
    return reports


@st.cache_data(ttl=30)
def load_attendee_roster():
    if not os.path.exists(ATTENDEES_FILE):
        return []

    try:
        with open(ATTENDEES_FILE, "r", encoding="utf-8") as file:
            return normalize_roster(json.load(file))
    except (json.JSONDecodeError, OSError):
        return []


def get_expected_attendees(meeting, global_roster):
    # Prefer the roster snapshot stored with this report, if present.
    report_roster = normalize_roster(meeting.get("expected_attendees"))
    return report_roster if report_roster else global_roster


def get_true_absentees(participants, expected_roster):
    attended_names = {
        normalize_name(participant.get("name"))
        for participant in participants
        if normalize_name(participant.get("name"))
    }

    return [
        person for person in expected_roster
        if normalize_name(person.get("name")) not in attended_names
    ]


def format_time_12h(time_value):
    if not time_value:
        return "--"

    try:
        parsed = pd.to_datetime(time_value, errors="raise")
        return parsed.strftime("%I:%M %p")
    except (ValueError, TypeError, OverflowError):
        try:
            parts = str(time_value).split(":")
            hour = int(parts[0])
            minute = parts[1]
            suffix = "AM" if hour < 12 else "PM"
            hour_12 = hour % 12 or 12
            return f"{hour_12}:{minute} {suffix}"
        except (ValueError, IndexError, AttributeError):
            return str(time_value)


def format_date(date_value):
    if not date_value:
        return "--"
    try:
        return pd.to_datetime(date_value, errors="raise").strftime("%d %B %Y")
    except (ValueError, TypeError):
        return str(date_value)


def report_status(report):
    return str(report.get("status") or "completed").strip()


def report_label(report, index):
    meeting_id = str(report.get("meeting_id") or "meeting")
    source = str(report.get("_source_file") or "")
    if source:
        return f"{meeting_id}::{source}"
    return f"{meeting_id}::{index}"


def status_color(status):
    status = str(status or "").strip().casefold()
    if status == "absent":
        return "#e74c3c"
    if status in ("low attendance", "partially present"):
        return "#f39c12"
    if status == "present":
        return "#2ecc71"
    return ""


# -------------------- Page setup --------------------

st.title("📅 Meeting History")

reports = load_all_reports()
global_roster = load_attendee_roster()

if not reports:
    st.info("No meeting reports found yet. Reports will appear here after the bot writes them.")
    st.caption(f"Looking for reports in: {REPORTS_DIR}")
    st.stop()

if "selected_report_key" not in st.session_state:
    st.session_state.selected_report_key = None


def back_to_list():
    st.session_state.selected_report_key = None


def open_report(key):
    st.session_state.selected_report_key = key


# -------------------- Detail view --------------------

selected_key = st.session_state.selected_report_key
selected_report = None

if selected_key is not None:
    for index, report in enumerate(reports):
        if report_label(report, index) == selected_key:
            selected_report = report
            break

if selected_key is not None and selected_report is None:
    st.warning("That report could not be found. The report list may have changed.")
    st.button("← Back to Meeting History", on_click=back_to_list)
    st.stop()

if selected_report is not None:
    meeting = selected_report
    participants = normalize_participants(meeting.get("participants"))
    expected_roster = get_expected_attendees(meeting, global_roster)
    absentees = get_true_absentees(participants, expected_roster)

    title = meeting.get("meeting_title") or meeting.get("meeting_id") or "Meeting"
    st.button("← Back to Meeting History", on_click=back_to_list)
    st.markdown(f"## {title}")

    st.caption(
        f"{format_date(meeting.get('date'))} · "
        f"{format_time_12h(meeting.get('start_time'))} – "
        f"{format_time_12h(meeting.get('end_time'))} · "
        f"Status: {report_status(meeting)}"
    )

    if expected_roster:
        st.caption(
            f"Absence is calculated against {len(expected_roster)} expected attendee(s). "
            "A person is absent only if their name does not appear in this meeting's participant data."
        )
    else:
        st.caption(
            "No expected-attendee roster is available for this report. "
            "The absent count is unknown, so the page will not treat low attendance as absence."
        )

    low_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "low attendance"
    )
    present_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "present"
    )
    partial_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "partially present"
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Detected Attendees", len(participants))
    kpi2.metric("Present", present_count)
    kpi3.metric("Low Attendance", low_count)
    kpi4.metric("Absent", len(absentees) if expected_roster else "N/A")

    if expected_roster:
        attendance_rate = (
            round((len(expected_roster) - len(absentees)) / len(expected_roster) * 100, 1)
            if expected_roster else None
        )
        st.metric("Expected-Attendee Attendance Rate", f"{attendance_rate:.1f}%")
    st.divider()

    table_rows = []

    for participant in participants:
        leave_time = participant.get("leave_time")
        duration = participant.get("duration_minutes", 0)
        try:
            duration_text = f"{float(duration):g} min" if duration is not None else "--"
        except (TypeError, ValueError):
            duration_text = "--"

        table_rows.append({
            "Name": participant.get("name") or "Unknown",
            "Joining Time": format_time_12h(participant.get("join_time")),
            "Leaving Time": format_time_12h(leave_time) if leave_time else "Still in meeting",
            "Duration": duration_text,
            "Attendance %": (
                f"{float(participant['attendance_percentage']):.1f}%"
                if participant.get("attendance_percentage") is not None
                else "--"
            ),
            "Status": participant.get("status") or "Unknown",
        })

    for person in absentees:
        table_rows.append({
            "Name": person.get("name") or "Unknown",
            "Joining Time": "—",
            "Leaving Time": "—",
            "Duration": "—",
            "Attendance %": "0.0%",
            "Status": "Absent",
        })

    if table_rows:
        table_df = pd.DataFrame(table_rows)

        def highlight_status(row):
            color = status_color(row.get("Status"))
            return [
                f"color: {color}" if column == "Status" and color else ""
                for column in row.index
            ]

        st.dataframe(
            table_df.style.apply(highlight_status, axis=1),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No participants were detected for this report.")

    st.divider()
    st.subheader("Session History")

    has_sessions = False
    for participant in participants:
        sessions = participant.get("sessions", [])
        if not isinstance(sessions, list) or not sessions:
            continue

        has_sessions = True
        name = participant.get("name") or "Unknown"

        with st.expander(f"👤 {name}"):
            session_rows = []

            for session_index, session in enumerate(sessions, start=1):
                if not isinstance(session, dict):
                    continue

                join_time = session.get("join_time")
                leave_time = session.get("leave_time")
                duration_text = "Still in meeting" if not leave_time else "--"

                if join_time and leave_time:
                    try:
                        start = pd.to_datetime(join_time, errors="raise")
                        end = pd.to_datetime(leave_time, errors="raise")
                        seconds = max(0, (end - start).total_seconds())
                        duration_text = f"{seconds / 60:.1f} min"
                    except (ValueError, TypeError):
                        duration_text = "--"

                session_rows.append({
                    "Session": session_index,
                    "Joining Time": format_time_12h(join_time),
                    "Leaving Time": format_time_12h(leave_time) if leave_time else "Still in meeting",
                    "Duration": duration_text,
                })

            if session_rows:
                st.dataframe(
                    pd.DataFrame(session_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("No valid session records for this participant.")

    if not has_sessions:
        st.info("No session history available in this report.")


# -------------------- Meeting list view --------------------

else:
    search_col, date_col = st.columns([2, 1])

    with search_col:
        search_text = st.text_input(
            "Search by meeting name",
            placeholder="e.g. Weekly Team Sync",
        )

    with date_col:
        date_filter = st.date_input(
            "Filter by date",
            value=None,
            key="history_date_filter",
        )

    filtered_reports = []

    for index, report in enumerate(reports):
        title = str(report.get("meeting_title") or report.get("meeting_id") or "Meeting")

        if search_text and search_text.casefold() not in title.casefold():
            continue

        if date_filter:
            report_date = pd.to_datetime(report.get("date"), errors="coerce")
            if pd.isna(report_date) or report_date.date() != date_filter:
                continue

        filtered_reports.append((index, report))

    st.caption(f"{len(filtered_reports)} meeting report(s)")

    if not filtered_reports:
        st.info("No meetings match your search or date filter.")

    for index, meeting in filtered_reports:
        participants = normalize_participants(meeting.get("participants"))
        expected_roster = get_expected_attendees(meeting, global_roster)
        absentees = get_true_absentees(participants, expected_roster)

        low_count = sum(
            1 for p in participants
            if str(p.get("status") or "").strip().casefold() == "low attendance"
        )
        meeting_title = meeting.get("meeting_title") or meeting.get("meeting_id") or "Meeting"
        status = report_status(meeting)
        key = report_label(meeting, index)

        with st.container(border=True):
            card_col1, card_col2 = st.columns([4, 1])

            with card_col1:
                st.markdown(f"### {meeting_title}")
                st.write(
                    f"{format_date(meeting.get('date'))} · "
                    f"{format_time_12h(meeting.get('start_time'))} – "
                    f"{format_time_12h(meeting.get('end_time'))}"
                )

                caption_parts = [f"{len(participants)} detected attendee(s)"]

                if low_count:
                    caption_parts.append(f"⚠️ {low_count} low attendance")

                if expected_roster:
                    caption_parts.append(f"🔴 {len(absentees)} absent")
                else:
                    caption_parts.append("Absent count unavailable (no roster)")

                if status.casefold() == "completed":
                    caption_parts.append("✅ Completed")
                elif status.casefold() in ("active", "in_progress", "in progress"):
                    caption_parts.append("🟢 Active")

                st.caption(" · ".join(caption_parts))

            with card_col2:
                st.button(
                    "View →",
                    key=f"open_report_{index}_{key}",
                    use_container_width=True,
                    on_click=open_report,
                    args=(key,),
                )
