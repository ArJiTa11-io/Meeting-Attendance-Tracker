import glob
import json
import os

import pandas as pd
import streamlit as st

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "meeting-bot", "output", "reports"
)
REPORTS_DIR = os.path.abspath(REPORTS_DIR)


def load_all_reports(reports_dir=REPORTS_DIR):
    reports = []
    for file_path in glob.glob(os.path.join(reports_dir, "*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception as e:
            st.warning(f"Could not read {file_path}: {e}")
    return reports


def build_participant_records(reports):
    """One row per (participant, meeting) - the raw material for
    per-participant aggregation."""
    rows = []
    for r in reports:
        meeting_title = r.get("meeting_title", "Untitled")
        meeting_date = r.get("date")
        for p in r.get("participants", []):
            rows.append({
                "Name": p.get("name"),
                "Email": p.get("email"),
                "Meeting Title": meeting_title,
                "Date": meeting_date,
                "Attendance %": p.get("attendance_percentage", 0),
                "Status": p.get("status"),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


def compute_participant_summary(df):
    """Total meetings, attended count, low-attendance count, avg % -
    one row per unique participant."""
    if df.empty:
        return pd.DataFrame()

    summary = df.groupby(["Name", "Email"]).agg(
        Total_Meetings=("Meeting Title", "count"),
        Avg_Attendance=("Attendance %", "mean"),
        Low_Attendance_Count=("Status", lambda s: (s == "Low Attendance").sum()),
        Attended_Count=("Status", lambda s: (s != "Absent").sum()),
    ).reset_index()

    summary["Avg_Attendance"] = summary["Avg_Attendance"].round(1)
    summary = summary.sort_values("Avg_Attendance", ascending=False)
    return summary


def main():
    st.set_page_config(page_title="Participant History", page_icon="👤", layout="wide")
    st.title("👤 Participant Attendance History")

    reports = load_all_reports()
    df = build_participant_records(reports)

    if df.empty:
        st.info("No meeting reports found yet.")
        return

    summary = compute_participant_summary(df)

    st.subheader("All Participants — Summary")
    st.dataframe(
        summary.rename(columns={
            "Total_Meetings": "Total Meetings",
            "Avg_Attendance": "Avg Attendance %",
            "Low_Attendance_Count": "Low Attendance Count",
            "Attended_Count": "Meetings Attended",
        }),
        width="stretch",
        hide_index=True,
    )

    st.divider()

    st.subheader("Individual Participant Detail")
    names = sorted(df["Name"].unique())
    selected_name = st.selectbox("Select a participant", names)

    person_df = df[df["Name"] == selected_name].sort_values("Date")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Meetings", len(person_df))
    col2.metric("Avg Attendance %", f"{person_df['Attendance %'].mean():.1f}%")
    col3.metric("Low Attendance Count", int((person_df["Status"] == "Low Attendance").sum()))
    col4.metric(
        "Best / Worst",
        f"{person_df['Attendance %'].max():.0f}% / {person_df['Attendance %'].min():.0f}%",
    )

    st.write("**Attendance % over time:**")
    chart_data = person_df.set_index("Date")["Attendance %"]
    st.line_chart(chart_data)

    st.write("**Meeting-by-meeting detail:**")
    display_df = person_df.copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%d %b %Y")
    st.dataframe(
        display_df[["Meeting Title", "Date", "Attendance %", "Status"]],
        width="stretch",
        hide_index=True,
    )


if __name__ == "__main__":
    main()
