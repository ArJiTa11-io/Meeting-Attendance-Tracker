import glob
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),  # pages/
    "..",  # up to project root
    "meeting-bot", "output", "reports"
)
REPORTS_DIR = os.path.abspath(REPORTS_DIR)


def load_all_reports(reports_dir=REPORTS_DIR):
    """Read every report JSON file in the folder into a list of dicts."""
    reports = []
    for file_path in glob.glob(os.path.join(reports_dir, "*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_file"] = file_path
                reports.append(data)
        except Exception as e:
            st.warning(f"Could not read {file_path}: {e}")
    return reports


def reports_to_dataframe(reports):
    """One row per meeting - used for the Reports table and KPIs."""
    rows = []
    for r in reports:
        participants = r.get("participants", [])
        avg_pct = (
            sum(p.get("attendance_percentage", 0) for p in participants) / len(participants)
            if participants else 0
        )
        low_count = sum(1 for p in participants if p.get("status") == "Low Attendance")

        rows.append({
            "Meeting Title": r.get("meeting_title", "Untitled"),
            "Date": r.get("date"),
            "Duration (min)": r.get("duration_minutes"),
            "Participants": r.get("total_participants", len(participants)),
            "Avg Attendance %": round(avg_pct, 1),
            "Low Attendance Count": low_count,
            "Meeting ID": r.get("meeting_id"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False).reset_index(drop=True)
    return df


def compute_kpis(df):
    """Calculate the 4 KPI values from the meetings dataframe."""
    if df.empty:
        return None

    today = df["Date"].max()  # most recent meeting date acts as "today" reference
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    last_meeting = df.iloc[0]

    this_week_df = df[df["Date"] >= this_week_start]
    last_week_df = df[(df["Date"] >= last_week_start) & (df["Date"] <= last_week_end)]

    this_week_avg = this_week_df["Avg Attendance %"].mean() if not this_week_df.empty else None
    last_week_avg = last_week_df["Avg Attendance %"].mean() if not last_week_df.empty else None

    trend = None
    if this_week_avg is not None and last_week_avg is not None:
        trend = round(this_week_avg - last_week_avg, 1)

    low_attendance_this_week = int(this_week_df["Low Attendance Count"].sum()) if not this_week_df.empty else 0

    return {
        "last_meeting_title": last_meeting["Meeting Title"],
        "last_meeting_date": last_meeting["Date"].strftime("%d %b %Y"),
        "last_meeting_attendees": int(last_meeting["Participants"]),
        "last_meeting_avg_pct": last_meeting["Avg Attendance %"],
        "this_week_avg_pct": round(this_week_avg, 1) if this_week_avg is not None else None,
        "trend": trend,
        "low_attendance_this_week": low_attendance_this_week,
        "total_meetings": len(df),
    }


def render_kpi_cards(kpis):
    st.subheader("Attendance Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Last Meeting Attendees",
            kpis["last_meeting_attendees"],
            help=f"{kpis['last_meeting_title']} — {kpis['last_meeting_date']}",
        )

    with col2:
        if kpis["this_week_avg_pct"] is not None:
            delta = f"{kpis['trend']:+.1f}%" if kpis["trend"] is not None else None
            st.metric("This Week Avg Attendance", f"{kpis['this_week_avg_pct']}%", delta=delta)
        else:
            st.metric("This Week Avg Attendance", "No data")

    with col3:
        st.metric("Low Attendance Flags (This Week)", kpis["low_attendance_this_week"])

    with col4:
        st.metric("Total Meetings Tracked", kpis["total_meetings"])


def render_reports_table(df, reports):
    st.subheader("My Reports")

    if df.empty:
        st.info("No meeting reports saved yet.")
        return

    display_df = df.copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%d %b %Y")

    for i, row in display_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
            c1.write(f"**{row['Meeting Title']}**")
            c2.write(row["Date"])
            c3.write(f"{row['Duration (min)']} min")
            c4.write(f"{row['Participants']} attendees")
            c5.write(f"{row['Avg Attendance %']}% avg")

            if st.button("View Report", key=f"view_{row['Meeting ID']}"):
                st.session_state["selected_meeting"] = row["Meeting ID"]

    selected_id = st.session_state.get("selected_meeting")
    if selected_id:
        selected_report = next((r for r in reports if r.get("meeting_id") == selected_id), None)
        if selected_report:
            st.divider()
            st.subheader(f"Details — {selected_report.get('meeting_title')}")
            participants_df = pd.DataFrame(selected_report.get("participants", []))
            st.dataframe(participants_df, width="stretch", hide_index=True)


def main():
    st.set_page_config(page_title="Attendance Dashboard", page_icon="📊", layout="wide")
    st.title("📊 Attendance Dashboard")

    reports = load_all_reports()
    df = reports_to_dataframe(reports)
    kpis = compute_kpis(df)

    if kpis:
        render_kpi_cards(kpis)
        st.divider()
    else:
        st.info("No meeting reports found yet — once meetings are tracked, KPIs will appear here.")

    render_reports_table(df, reports)


if __name__ == "__main__":
    main()