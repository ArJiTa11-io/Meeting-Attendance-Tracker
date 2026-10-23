
import glob
import json
import os
import calendar
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "meeting-bot", "output", "reports")
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")


# -------------------- Data loading --------------------

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
            continue

    reports.sort(key=report_sort_key)
    return reports


def report_sort_key(report):
    date_text = str(report.get("date") or "")
    start_text = str(report.get("start_time") or "")
    timestamp = pd.to_datetime(f"{date_text} {start_text}", errors="coerce")
    return timestamp if not pd.isna(timestamp) else pd.Timestamp.min


@st.cache_data(ttl=30)
def load_attendee_roster():
    if not os.path.exists(ATTENDEES_FILE):
        return []
    try:
        with open(ATTENDEES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return normalize_roster(data)
    except (json.JSONDecodeError, OSError):
        return []


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
        result = []
        for name, details in raw.items():
            details = details if isinstance(details, dict) else {}
            result.append({"name": name, **details})
        return result

    return []


def expected_names_for_report(report, global_roster):
    report_roster = normalize_roster(report.get("expected_attendees"))
    if report_roster:
        return report_roster
    return global_roster


def attendance_metrics(report, global_roster):
    participants = normalize_participants(report.get("participants"))
    expected = expected_names_for_report(report, global_roster)

    attended_keys = {
        normalize_name(p.get("name"))
        for p in participants
        if normalize_name(p.get("name"))
    }

    if expected:
        expected_keys = {normalize_name(p["name"]) for p in expected}
        present_count = sum(1 for key in expected_keys if key in attended_keys)
        absent_names = [
            person["name"]
            for person in expected
            if normalize_name(person["name"]) not in attended_keys
        ]
        attendance_rate = round(present_count / len(expected_keys) * 100, 1) if expected_keys else None
        absent_rate = round(len(absent_names) / len(expected_keys) * 100, 1) if expected_keys else None
        absent_count = len(absent_names)
        absent_is_known = True
    else:
        present_count = len(attended_keys)
        absent_names = []
        attendance_rate = None
        absent_rate = None
        absent_count = None
        absent_is_known = False

    low_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "low attendance"
    )
    partial_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "partially present"
    )
    full_count = sum(
        1 for p in participants
        if str(p.get("status") or "").strip().casefold() == "present"
    )

    percentages = []
    for participant in participants:
        try:
            value = participant.get("attendance_percentage")
            if value is not None:
                percentages.append(float(value))
        except (TypeError, ValueError):
            continue

    # This is a separate metric, not the expected-attendee attendance rate.
    avg_participant_pct = round(sum(percentages) / len(percentages), 1) if percentages else None

    return {
        "participants": participants,
        "expected": expected,
        "attendance_rate": attendance_rate,
        "absent_rate": absent_rate,
        "absent_count": absent_count,
        "absent_is_known": absent_is_known,
        "present_count": present_count,
        "low_count": low_count,
        "partial_count": partial_count,
        "full_count": full_count,
        "participant_count": len(participants),
        "avg_participant_pct": avg_participant_pct,
    }


def make_meeting_rows(reports, roster):
    rows = []
    for index, report in enumerate(reports):
        metrics = attendance_metrics(report, roster)
        raw_date = report.get("date")
        parsed_date = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_date):
            parsed_date = pd.to_datetime(
                f"{raw_date or ''} {report.get('start_time') or ''}",
                errors="coerce",
            )
        if pd.isna(parsed_date):
            continue

        rows.append({
            "report_index": index,
            "meeting_id": str(report.get("meeting_id") or ""),
            "meeting_title": str(report.get("meeting_title") or report.get("meeting_id") or "Meeting"),
            "date": parsed_date,
            "attendance_rate": metrics["attendance_rate"],
            "absent_rate": metrics["absent_rate"],
            "absent_count": metrics["absent_count"],
            "absent_is_known": metrics["absent_is_known"],
            "low_count": metrics["low_count"],
            "participant_count": metrics["participant_count"],
            "present_count": metrics["present_count"],
            "avg_participant_pct": metrics["avg_participant_pct"],
            "status": str(report.get("status") or "completed"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["date", "report_index"]).reset_index(drop=True)
    return df


# -------------------- Dashboard --------------------

reports = load_all_reports()
roster = load_attendee_roster()

st.title("📊 Dashboard")

if not reports:
    st.info("No meeting reports found yet. Once the bot records a meeting, this page will update automatically.")
    st.caption(f"Looking for reports in: {REPORTS_DIR}")
    st.stop()

meeting_df = make_meeting_rows(reports, roster)

if meeting_df.empty:
    st.info("Reports were found, but no valid meeting dates could be read.")
    st.caption(f"Reports folder: {REPORTS_DIR}")
    st.stop()

if "selected_day" not in st.session_state:
    st.session_state.selected_day = None
if "trend_range" not in st.session_state:
    st.session_state.trend_range = 30
if "calendar_month" not in st.session_state:
    latest_date = meeting_df.iloc[-1]["date"]
    st.session_state.calendar_month = latest_date.to_pydatetime().replace(day=1)

latest = meeting_df.iloc[-1]
previous = meeting_df.iloc[-2] if len(meeting_df) > 1 else None

if roster or any(normalize_roster(r.get("expected_attendees")) for r in reports):
    st.caption(
        '“Attendance Rate” means the percentage of expected attendees who joined. '
        '“Absent Rate” means the percentage of expected attendees who never joined.'
    )
else:
    st.caption(
        "No expected-attendee roster is available. Attendance Rate and Absent Rate "
        "are shown as N/A until a roster is configured. Low Attendance counts detected "
        "participants whose recorded status is Low Attendance."
    )

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    value = latest["attendance_rate"]
    delta = None
    if previous is not None and pd.notna(value) and pd.notna(previous["attendance_rate"]):
        delta = f"{value - previous['attendance_rate']:+.1f}%"
    st.metric("Last Recorded Attendance Rate", f"{value:.1f}%" if pd.notna(value) else "N/A", delta=delta)

with kpi2:
    value = latest["absent_rate"]
    delta = None
    if previous is not None and pd.notna(value) and pd.notna(previous["absent_rate"]):
        delta = f"{value - previous['absent_rate']:+.1f}%"
    st.metric(
        "Absent Rate",
        f"{value:.1f}%" if pd.notna(value) else "N/A",
        delta=delta,
        delta_color="inverse",
    )

with kpi3:
    delta = int(latest["low_count"] - previous["low_count"]) if previous is not None else None
    st.metric("Low Attendees", int(latest["low_count"]), delta=delta, delta_color="inverse")

st.caption(
    f"Most recent report: **{latest['meeting_title']}** · "
    f"{latest['date'].strftime('%d %b %Y')} · {latest['status']}"
)
st.divider()


# -------------------- Present vs absent donut --------------------

col_donut, col_line = st.columns([1, 2])

day_lookup = {}
for _, row in meeting_df.iterrows():
    day_lookup[row["date"].date()] = row

with col_donut:
    selected_day = st.session_state.selected_day
    if selected_day in day_lookup:
        donut_row = day_lookup[selected_day]
        st.subheader(f"Attendance Breakdown — {selected_day.strftime('%d %b %Y')}")
    else:
        donut_row = latest
        st.subheader("Attendance Breakdown — Latest Meeting")

    report = reports[int(donut_row["report_index"])]
    metrics = attendance_metrics(report, roster)

    if metrics["expected"]:
        absent = metrics["absent_count"] or 0
        present = metrics["present_count"]
        values = [present, absent]
        labels = ["Expected attendees present", "Expected attendees absent"]
        colors = ["#2ecc71", "#e74c3c"]
        total_people = len(metrics["expected"])
    elif metrics["participant_count"]:
        values = [
            metrics["full_count"],
            metrics["partial_count"],
            metrics["low_count"],
        ]
        labels = ["Present", "Partially Present", "Low Attendance"]
        colors = ["#2ecc71", "#3498db", "#f39c12"]
        total_people = metrics["participant_count"]
    else:
        values, labels, colors, total_people = [], [], [], 0

    if values and sum(values) > 0:
        donut_fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors),
        )])
        donut_fig.update_layout(
            showlegend=True,
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
            annotations=[dict(
                text=f"{total_people}<br>people",
                x=0.5, y=0.5, font_size=16, showarrow=False,
            )],
        )
        st.plotly_chart(donut_fig, use_container_width=True)
    else:
        st.info("No participant or expected-attendee data is available for this report.")


# -------------------- Attendance trend --------------------

with col_line:
    st.subheader("Attendance Trend")
    button_cols = st.columns(3)
    for col, (label, days) in zip(button_cols, [("7D", 7), ("30D", 30), ("90D", 90)]):
        with col:
            if st.button(
                label,
                key=f"trend_{days}",
                use_container_width=True,
                type="primary" if st.session_state.trend_range == days else "secondary",
            ):
                st.session_state.trend_range = days
                st.rerun()

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=st.session_state.trend_range)
    trend_df = meeting_df[meeting_df["date"] >= cutoff].copy()

    if trend_df.empty:
        st.info("No meetings in this time range yet.")
    else:
        fig = go.Figure()
        if trend_df["attendance_rate"].notna().any():
            fig.add_trace(go.Scatter(
                x=trend_df["date"], y=trend_df["attendance_rate"],
                mode="lines+markers", name="Attendance Rate %",
                line=dict(color="#2ecc71"),
                customdata=trend_df["meeting_title"],
                hovertemplate="%{x|%d %b %Y}<br>%{customdata}<br>Attendance: %{y:.1f}%<extra></extra>",
            ))
        if trend_df["absent_rate"].notna().any():
            fig.add_trace(go.Scatter(
                x=trend_df["date"], y=trend_df["absent_rate"],
                mode="lines+markers", name="Absent Rate %",
                line=dict(color="#e74c3c"),
                customdata=trend_df["meeting_title"],
                hovertemplate="%{x|%d %b %Y}<br>%{customdata}<br>Absent: %{y:.1f}%<extra></extra>",
            ))
        if not fig.data:
            st.info("Add an expected-attendee roster to display attendance and absence rates.")
        else:
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
                yaxis_title="Percentage",
                yaxis=dict(range=[0, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

st.divider()


# -------------------- Calendar --------------------

st.subheader("Calendar")

current_month = st.session_state.calendar_month
nav_prev, nav_label, nav_next = st.columns([1, 3, 1])

with nav_prev:
    if st.button("← Prev", use_container_width=True):
        previous_month = current_month - timedelta(days=1)
        st.session_state.calendar_month = previous_month.replace(day=1)
        st.rerun()

with nav_label:
    st.markdown(
        f"<h4 style='text-align:center'>{current_month.strftime('%B %Y')}</h4>",
        unsafe_allow_html=True,
    )

with nav_next:
    if st.button("Next →", use_container_width=True):
        if current_month.month == 12:
            next_month = current_month.replace(year=current_month.year + 1, month=1, day=1)
        else:
            next_month = current_month.replace(month=current_month.month + 1, day=1)
        st.session_state.calendar_month = next_month
        st.rerun()

month_start = st.session_state.calendar_month
days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
leading_blanks = month_start.weekday()

weekday_cols = st.columns(7)
for col, label in zip(weekday_cols, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
    col.markdown(
        f"<div style='text-align:center;opacity:0.65;font-size:12px'>{label}</div>",
        unsafe_allow_html=True,
    )

cells = [None] * leading_blanks + list(range(1, days_in_month + 1))
while len(cells) % 7:
    cells.append(None)

for offset in range(0, len(cells), 7):
    week_cols = st.columns(7)
    for col, day_num in zip(week_cols, cells[offset:offset + 7]):
        if day_num is None:
            col.markdown("&nbsp;", unsafe_allow_html=True)
            continue

        current_date = date(month_start.year, month_start.month, day_num)
        row = day_lookup.get(current_date)
        with col:
            if row is not None:
                if st.button(
                    str(day_num),
                    key=f"calendar_{current_date.isoformat()}",
                    use_container_width=True,
                    type="primary" if st.session_state.selected_day == current_date else "secondary",
                ):
                    st.session_state.selected_day = current_date
                    st.rerun()

                attendance = row["attendance_rate"]
                label = f"{attendance:.1f}%" if pd.notna(attendance) else "Meeting"
                st.markdown(
                    f"<div style='text-align:center;font-size:11px;color:#2ecc71'>{label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                col.markdown(
                    f"<div style='text-align:center;padding:8px 0;opacity:0.35'>{day_num}</div>",
                    unsafe_allow_html=True,
                )

if st.session_state.selected_day in day_lookup:
    selected = day_lookup[st.session_state.selected_day]
    st.markdown(
        f"**{st.session_state.selected_day.strftime('%d %B %Y')} — "
        f"{selected['meeting_title']}**"
    )
    selected_col1, selected_col2, selected_col3 = st.columns(3)
    selected_col1.metric(
        "Attendance Rate",
        f"{selected['attendance_rate']:.1f}%" if pd.notna(selected["attendance_rate"]) else "N/A",
    )
    selected_col2.metric(
        "Absent Rate",
        f"{selected['absent_rate']:.1f}%" if pd.notna(selected["absent_rate"]) else "N/A",
    )
    selected_col3.metric("Low Attendees", int(selected["low_count"]))
    if st.button("Clear selected date"):
        st.session_state.selected_day = None
        st.rerun()
