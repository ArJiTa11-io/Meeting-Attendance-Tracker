import glob
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "meeting-bot", "output", "reports")
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")



# Data loading


@st.cache_data(ttl=2)
def load_all_reports():
    """Reads every report JSON file in meeting-bot/output/reports."""
    reports = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
                if isinstance(report, dict):
                    reports.append(report)
        except (json.JSONDecodeError, OSError):
            continue
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


def reports_to_participant_rows(reports):
    """Flattens reports into one row per participant per meeting."""
    rows = []
    for report in reports:
        meeting_date = report.get("date")
        participants = report.get("participants", [])
        if not isinstance(participants, list):
            continue
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            rows.append(
                {
                    "meeting_id": report.get("meeting_id"),
                    "meeting_title": report.get("meeting_title"),
                    "date": meeting_date,
                    "name": participant.get("name"),
                    "attendance_percentage": participant.get("attendance_percentage", 0),
                    "status": participant.get("status"),
                }
            )
    return pd.DataFrame(rows)


def get_absent_info(report, roster):
   
    participants = report.get("participants", [])
    if not isinstance(participants, list):
        participants = []

    report_absent_count = report.get("absent_count")
    report_total_expected = report.get("total_expected")

    if report_absent_count is not None and report_total_expected:
        return int(report_absent_count), int(report_total_expected), False

    if roster:
        attended_names = {
            p.get("name", "").strip().lower()
            for p in participants
            if isinstance(p, dict)
        }
        absent_count = sum(
            1 for person in roster
            if person.get("name", "").strip().lower() not in attended_names
        )
        return absent_count, len(roster), False

    # last resort: Low Attendance stands in for Absent
    low_count = sum(
        1 for p in participants
        if isinstance(p, dict) and p.get("status") == "Low Attendance"
    )
    return low_count, len(participants), True


def reports_to_meeting_rows(reports, roster):
    """One row per meeting, with that meeting's average attendance rate
    and absent count/rate (see get_absent_info for how Absent is worked out)."""
    rows = []
    for report in reports:
        participants = report.get("participants", [])
        if not isinstance(participants, list):
            participants = []
        if not participants:
            continue

        percentages = [
            float(p.get("attendance_percentage", 0))
            for p in participants
            if isinstance(p, dict) and p.get("attendance_percentage") is not None
        ]
        avg_pct = sum(percentages) / len(percentages) if percentages else 0.0

        low_count = sum(
            1 for p in participants
            if isinstance(p, dict) and p.get("status") == "Low Attendance"
        )

        absent_count, expected_total, used_fallback = get_absent_info(report, roster)
        absent_rate_pct = round((absent_count / expected_total) * 100, 1) if expected_total else 0.0

        rows.append(
            {
                "meeting_id": report.get("meeting_id"),
                "meeting_title": report.get("meeting_title"),
                "date": report.get("date"),
                "avg_attendance_pct": round(avg_pct, 1),
                "absent_rate_pct": absent_rate_pct,
                "absent_count": absent_count,
                "low_attendees": low_count,
                "total_participants": len(participants),
                "used_low_attendance_fallback": used_fallback,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values(["date", "meeting_id"])
    return df



# Load + guard


reports = load_all_reports()
roster = load_attendee_roster()

st.title("📊 Dashboard")

if not reports:
    st.info(
        "No meeting reports found yet. Once the bot records a completed "
        "meeting, this page will fill in automatically."
    )
    st.caption(f"Looking for reports in: {REPORTS_DIR}")
    st.stop()

meeting_df = reports_to_meeting_rows(reports, roster)
participant_df = reports_to_participant_rows(reports)

if meeting_df.empty:
    st.info("Reports were found, but no valid meeting data could be loaded.")
    st.stop()

if meeting_df["used_low_attendance_fallback"].iloc[-1]:
    st.caption(
        "ℹ️ No attendee list set up yet, so \"Absent\" here is standing in for "
        "**Low Attendance** (joined but stayed for only a small part of the "
        "meeting). Add people on the **Manage Attendees** page for true Absent tracking."
    )
else:
    st.caption(
        "ℹ️ \"Absent Rate\" compares each meeting against the expected attendee "
        "list — anyone expected who didn't join at all counts as Absent."
    )


# 1. KPI cards (latest meeting vs the one before it)


latest = meeting_df.iloc[-1]
previous = meeting_df.iloc[-2] if len(meeting_df) >= 2 else None

last_attendance_rate = latest["avg_attendance_pct"]
last_absent_rate = latest["absent_rate_pct"]
last_low_count = int(latest["low_attendees"])

if previous is not None:
    attendance_delta = round(last_attendance_rate - previous["avg_attendance_pct"], 1)
    absent_delta = round(last_absent_rate - previous["absent_rate_pct"], 1)
    low_count_delta = int(last_low_count - previous["low_attendees"])
else:
    attendance_delta = None
    absent_delta = None
    low_count_delta = None

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Last Recorded Attendance Rate",
        f"{last_attendance_rate}%",
        delta=f"{attendance_delta}%" if attendance_delta is not None else None,
    )

with col2:
    st.metric(
        "Absent Rate",
        f"{last_absent_rate}%",
        delta=f"{absent_delta}%" if absent_delta is not None else None,
        delta_color="inverse",
    )

with col3:
    st.metric(
        "Low Attendees",
        last_low_count,
        delta=low_count_delta if low_count_delta is not None else None,
        delta_color="inverse",
    )

st.caption(f"Based on the most recent meeting: **{latest['meeting_title']}** on {latest['date'].strftime('%d %b %Y')}")

st.divider()


# 2. Donut chart (latest meeting: present vs absent/low attendance)


col_donut, col_line = st.columns([1, 2])

with col_donut:
    st.subheader("Present vs Absent")

    latest_meeting_id = latest["meeting_id"]
    latest_participants = participant_df[participant_df["meeting_id"] == latest_meeting_id]
    latest_report = next((r for r in reports if r.get("meeting_id") == latest_meeting_id), {})

    present_count = (latest_participants["status"] == "Present").sum()
    partially_present_count = (latest_participants["status"] == "Partially Present").sum()
    low_attendance_count = (latest_participants["status"] == "Low Attendance").sum()

    absent_count = int(latest["absent_count"])

    if not latest["used_low_attendance_fallback"]:
        donut_labels = ["Present", "Partially Present", "Low Attendance", "Absent"]
        donut_values = [present_count, partially_present_count, low_attendance_count, absent_count]
        donut_colors = ["#2ecc71", "#3498db", "#f39c12", "#e74c3c"]
        total_people = int(latest.get("absent_count", 0)) + len(latest_participants)
        # when roster is available, total expected = roster size
        total_people = len(roster) if roster else total_people
    else:
        donut_labels = ["Present", "Partially Present", "Low Attendance (= Absent)"]
        donut_values = [present_count, partially_present_count, low_attendance_count]
        donut_colors = ["#2ecc71", "#3498db", "#e74c3c"]
        total_people = len(latest_participants)

    donut_fig = go.Figure(
        data=[
            go.Pie(
                labels=donut_labels,
                values=donut_values,
                hole=0.6,
                marker=dict(colors=donut_colors),
            )
        ]
    )
    donut_fig.update_layout(
        showlegend=True,
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
        annotations=[
            dict(
                text=f"{total_people}<br>people",
                x=0.5,
                y=0.5,
                font_size=16,
                showarrow=False,
            )
        ],
    )
    st.plotly_chart(donut_fig, use_container_width=True)


# 3. Line chart: 7 / 30 / 90 day trend


with col_line:
    st.subheader("Attendance Trend")

    if "trend_range" not in st.session_state:
        st.session_state.trend_range = 30

    btn_cols = st.columns(3)
    labels = {"7D": 7, "30D": 30, "90D": 90}
    for btn_col, (label, days) in zip(btn_cols, labels.items()):
        with btn_col:
            if st.button(
                label,
                use_container_width=True,
                type="primary" if st.session_state.trend_range == days else "secondary",
            ):
                st.session_state.trend_range = days
                st.rerun()

    cutoff = datetime.now() - timedelta(days=st.session_state.trend_range)
    trend_df = meeting_df[meeting_df["date"] >= cutoff].copy()

    if trend_df.empty:
        st.info("No meetings in this time range yet.")
    else:
        line_fig = go.Figure()
        line_fig.add_trace(
            go.Scatter(
                x=trend_df["date"],
                y=trend_df["avg_attendance_pct"],
                mode="lines+markers",
                name="Attendance Rate %",
                line=dict(color="#2ecc71"),
            )
        )
        line_fig.add_trace(
            go.Scatter(
                x=trend_df["date"],
                y=trend_df["absent_rate_pct"],
                mode="lines+markers",
                name="Absent Rate %",
                line=dict(color="#e74c3c"),
            )
        )
        line_fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
            yaxis_title="%",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(line_fig, use_container_width=True)

st.divider()


# 4. Calendar view


st.subheader("Calendar")

day_lookup = {
    row["date"].date(): row for _, row in meeting_df.iterrows()
}

if "calendar_month" not in st.session_state:
    last_meeting_date = meeting_df.iloc[-1]["date"]
    st.session_state.calendar_month = last_meeting_date.replace(day=1)

if "selected_day" not in st.session_state:
    st.session_state.selected_day = None

nav_prev, nav_label, nav_next = st.columns([1, 3, 1])

with nav_prev:
    if st.button("← Prev", use_container_width=True):
        current = st.session_state.calendar_month
        prev_month_last_day = current - timedelta(days=1)
        st.session_state.calendar_month = prev_month_last_day.replace(day=1)
        st.rerun()

with nav_label:
    st.markdown(
        f"<h4 style='text-align:center'>{st.session_state.calendar_month.strftime('%B %Y')}</h4>",
        unsafe_allow_html=True,
    )

with nav_next:
    if st.button("Next →", use_container_width=True):
        current = st.session_state.calendar_month
        days_in_month = (current.replace(month=current.month % 12 + 1, day=1) - timedelta(days=1)).day if current.month != 12 else 31
        next_month_first_day = current.replace(day=days_in_month) + timedelta(days=1)
        st.session_state.calendar_month = next_month_first_day.replace(day=1)
        st.rerun()

month_start = st.session_state.calendar_month
if month_start.month == 12:
    next_month_start = month_start.replace(year=month_start.year + 1, month=1)
else:
    next_month_start = month_start.replace(month=month_start.month + 1)
days_in_month = (next_month_start - timedelta(days=1)).day

leading_blanks = month_start.weekday()  # Monday = 0

weekday_cols = st.columns(7)
for col, label in zip(weekday_cols, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
    col.markdown(f"<div style='text-align:center; opacity:0.6; font-size:12px'>{label}</div>", unsafe_allow_html=True)

cells = [None] * leading_blanks + list(range(1, days_in_month + 1))
while len(cells) % 7 != 0:
    cells.append(None)

for week_start in range(0, len(cells), 7):
    week_cols = st.columns(7)
    for col, day_num in zip(week_cols, cells[week_start:week_start + 7]):
        if day_num is None:
            col.markdown("&nbsp;", unsafe_allow_html=True)
            continue

        this_date = month_start.replace(day=day_num).date()
        day_data = day_lookup.get(this_date)

        with col:
            if day_data is not None:
                clicked = st.button(
                    f"{day_num}",
                    key=f"cal_{this_date.isoformat()}",
                    use_container_width=True,
                    type="primary" if st.session_state.selected_day == this_date else "secondary",
                )
                if clicked:
                    st.session_state.selected_day = this_date
                    st.rerun()
                st.markdown(
                    f"<div style='text-align:center; font-size:11px; color:#2ecc71'>{day_data['avg_attendance_pct']}%</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center; padding:8px 0; opacity:0.35'>{day_num}</div>",
                    unsafe_allow_html=True,
                )

if st.session_state.selected_day is not None and st.session_state.selected_day in day_lookup:
    selected = day_lookup[st.session_state.selected_day]
    st.markdown(f"**{st.session_state.selected_day.strftime('%d %B %Y')} — {selected['meeting_title']}**")
    sel_col1, sel_col2 = st.columns(2)
    sel_col1.metric("Attendance Rate", f"{selected['avg_attendance_pct']}%")
    sel_col2.metric("Absent Rate", f"{selected['absent_rate_pct']}%")