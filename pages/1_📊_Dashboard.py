import glob
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

REPORTS_DIR = os.path.join(
    PROJECT_ROOT,
    "meeting-bot",
    "output",
    "reports"
)

st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide"
)


# Data loading


@st.cache_data(ttl=2)
def load_all_reports():
    reports = []

    for path in sorted(
        glob.glob(
            os.path.join(
                REPORTS_DIR,
                "*.json"
            )
        )
    ):
        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:
                report = json.load(f)

                if isinstance(
                    report,
                    dict
                ):
                    reports.append(
                        report
                    )

        except (
            json.JSONDecodeError,
            OSError
        ):
            continue

    return reports


def reports_to_participant_rows(
    reports
):
    rows = []

    for report in reports:
        meeting_date = report.get(
            "date"
        )

        participants = report.get(
            "participants",
            []
        )

        if not isinstance(
            participants,
            list
        ):
            continue

        for participant in participants:
            if not isinstance(
                participant,
                dict
            ):
                continue

            rows.append(
                {
                    "meeting_id":
                        report.get(
                            "meeting_id"
                        ),

                    "meeting_title":
                        report.get(
                            "meeting_title"
                        ),

                    "date":
                        meeting_date,

                    "name":
                        participant.get(
                            "name"
                        ),

                    "attendance_percentage":
                        participant.get(
                            "attendance_percentage",
                            0
                        ),

                    "status":
                        participant.get(
                            "status"
                        )
                }
            )

    return pd.DataFrame(
        rows
    )


def reports_to_meeting_rows(
    reports
):
    rows = []

    for report in reports:
        participants = report.get(
            "participants",
            []
        )

        if not isinstance(
            participants,
            list
        ):
            participants = []

        participant_percentages = [
            p.get(
                "attendance_percentage",
                0
            )
            for p in participants
            if isinstance(
                p,
                dict
            )
        ]

        participant_percentages = [
            float(value)
            for value in participant_percentages
            if value is not None
        ]

        if participant_percentages:
            avg_pct = (
                sum(
                    participant_percentages
                )
                /
                len(
                    participant_percentages
                )
            )
        else:
            avg_pct = report.get(
                "attendance_rate"
            )

        if avg_pct is None:
            avg_pct = 0

        low_count = sum(
            1
            for p in participants
            if isinstance(
                p,
                dict
            )
            and p.get(
                "status"
            ) == "Low Attendance"
        )

        total_expected = report.get(
            "total_expected",
            0
        )

        absent_count = report.get(
            "absent_count"
        )

        absent_rate = report.get(
            "absent_rate"
        )

        if absent_count is None:
            absent_count = 0

        if absent_rate is None:
            if total_expected:
                absent_rate = (
                    absent_count /
                    total_expected
                ) * 100
            else:
                absent_rate = 0

        rows.append(
            {
                "meeting_id":
                    report.get(
                        "meeting_id"
                    ),

                "meeting_title":
                    report.get(
                        "meeting_title"
                    ),

                "date":
                    report.get(
                        "date"
                    ),

                "avg_attendance_pct":
                    round(
                        float(
                            avg_pct
                        ),
                        1
                    ),

                "attendance_rate":
                    report.get(
                        "attendance_rate"
                    ),

                "absent_rate_pct":
                    round(
                        float(
                            absent_rate
                        ),
                        1
                    ),

                "low_attendees":
                    low_count,

                "absent_count":
                    absent_count,

                "present_count":
                    report.get(
                        "present_count",
                        0
                    ),

                "total_expected":
                    total_expected,

                "total_participants":
                    len(
                        participants
                    )
            }
        )

    df = pd.DataFrame(
        rows
    )

    if not df.empty:
        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["date"]
        )

        df = df.sort_values(
            [
                "date",
                "meeting_id"
            ]
        )

    return df


# Load + guard


reports = load_all_reports()

st.title(
    "📊 Dashboard"
)

if not reports:
    st.info(
        "No meeting reports found yet. "
        "Once the bot records a completed meeting, "
        "the dashboard will fill in automatically."
    )

    st.caption(
        f"Looking for reports in: {REPORTS_DIR}"
    )

    st.stop()


meeting_df = reports_to_meeting_rows(
    reports
)

participant_df = reports_to_participant_rows(
    reports
)

if meeting_df.empty:
    st.info(
        "Reports were found, but no valid meeting data could be loaded."
    )

    st.stop()


st.caption(
    "Attendance rate uses the expected-attendee roster when one "
    "was provided. Low Attendance means a participant joined but "
    "did not stay for most of the meeting."
)


# 1. KPI cards


latest = meeting_df.iloc[-1]

previous = (
    meeting_df.iloc[-2]
    if len(meeting_df) >= 2
    else None
)

latest_attendance_rate = latest.get(
    "attendance_rate"
)

if pd.isna(
    latest_attendance_rate
):
    latest_attendance_rate = (
        latest[
            "avg_attendance_pct"
        ]
    )

last_absent_rate = (
    latest[
        "absent_rate_pct"
    ]
)

last_low_count = int(
    latest[
        "low_attendees"
    ]
)

if previous is not None:
    previous_attendance = previous.get(
        "attendance_rate"
    )

    if pd.isna(
        previous_attendance
    ):
        previous_attendance = (
            previous[
                "avg_attendance_pct"
            ]
        )

    attendance_delta = round(
        float(
            latest_attendance_rate
        )
        -
        float(
            previous_attendance
        ),
        1
    )

    absent_delta = round(
        float(
            last_absent_rate
        )
        -
        float(
            previous[
                "absent_rate_pct"
            ]
        ),
        1
    )

    low_count_delta = int(
        last_low_count
        -
        int(
            previous[
                "low_attendees"
            ]
        )
    )

else:
    attendance_delta = None
    absent_delta = None
    low_count_delta = None


col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "Last Recorded Attendance Rate",
        f"{float(latest_attendance_rate):.1f}%",
        delta=(
            f"{attendance_delta:+.1f}%"
            if attendance_delta is not None
            else None
        )
    )


with col2:
    st.metric(
        "Absent Rate",
        f"{float(last_absent_rate):.1f}%",
        delta=(
            f"{absent_delta:+.1f}%"
            if absent_delta is not None
            else None
        ),
        delta_color="inverse"
    )


with col3:
    st.metric(
        "Low Attendees",
        last_low_count,
        delta=(
            low_count_delta
            if low_count_delta is not None
            else None
        ),
        delta_color="inverse"
    )


st.caption(
    "Based on the most recent meeting: "
    f"**{latest['meeting_title']}** on "
    f"{latest['date'].strftime('%d %b %Y')}"
)

st.divider()


# 2. Donut chart


col_donut, col_line = st.columns(
    [1, 2]
)


with col_donut:
    st.subheader(
        "Present vs Absent"
    )

    latest_meeting_id = (
        latest[
            "meeting_id"
        ]
    )

    latest_report = next(
        (
            report
            for report in reports
            if report.get(
                "meeting_id"
            ) == latest_meeting_id
        ),
        {}
    )

    present_count = latest_report.get(
        "present_count"
    )

    absent_count = latest_report.get(
        "absent_count"
    )

    total_expected = latest_report.get(
        "total_expected",
        0
    )

    if (
        present_count is None
        or absent_count is None
    ):
        latest_participants = (
            participant_df[
                participant_df[
                    "meeting_id"
                ]
                == latest_meeting_id
            ]
        )

        present_count = int(
            (
                latest_participants[
                    "status"
                ]
                != "Low Attendance"
            ).sum()
        )

        absent_count = int(
            (
                latest_participants[
                    "status"
                ]
                == "Low Attendance"
            ).sum()
        )

    if total_expected == 0:
        total_expected = (
            present_count +
            absent_count
        )

    donut_fig = go.Figure(
        data=[
            go.Pie(
                labels=[
                    "Present",
                    "Absent"
                ],
                values=[
                    present_count,
                    absent_count
                ],
                hole=0.6,
                marker=dict(
                    colors=[
                        "#2ecc71",
                        "#e74c3c"
                    ]
                )
            )
        ]
    )

    donut_fig.update_layout(
        showlegend=True,
        margin=dict(
            t=10,
            b=10,
            l=10,
            r=10
        ),
        height=320,
        annotations=[
            dict(
                text=(
                    f"{total_expected}<br>"
                    "expected"
                ),
                x=0.5,
                y=0.5,
                font_size=16,
                showarrow=False
            )
        ]
    )

    st.plotly_chart(
        donut_fig,
        width="stretch"
    )


# 3. Line chart


with col_line:
    st.subheader(
        "Attendance Trend"
    )

    if (
        "trend_range"
        not in st.session_state
    ):
        st.session_state.trend_range = 30

    btn_cols = st.columns(3)

    labels = {
        "7D": 7,
        "30D": 30,
        "90D": 90
    }

    for btn_col, (
        label,
        days
    ) in zip(
        btn_cols,
        labels.items()
    ):
        with btn_col:
            if st.button(
                label,
                width="stretch",
                type=(
                    "primary"
                    if
                    st.session_state.trend_range
                    == days
                    else
                    "secondary"
                )
            ):
                st.session_state.trend_range = days
                st.rerun()

    cutoff = (
        datetime.now()
        -
        timedelta(
            days=st.session_state.trend_range
        )
    )

    trend_df = meeting_df[
        meeting_df["date"] >= cutoff
    ].copy()

    if trend_df.empty:
        st.info(
            "No meetings in this time range yet."
        )

    else:
        line_fig = go.Figure()

        line_fig.add_trace(
            go.Scatter(
                x=trend_df[
                    "date"
                ],
                y=trend_df[
                    "avg_attendance_pct"
                ],
                mode="lines+markers",
                name="Attendance Rate %"
            )
        )

        line_fig.add_trace(
            go.Scatter(
                x=trend_df[
                    "date"
                ],
                y=trend_df[
                    "absent_rate_pct"
                ],
                mode="lines+markers",
                name="Absent Rate %"
            )
        )

        line_fig.update_layout(
            margin=dict(
                t=10,
                b=10,
                l=10,
                r=10
            ),
            height=320,
            yaxis_title="%",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02
            )
        )

        st.plotly_chart(
            line_fig,
            width="stretch"
        )


st.divider()


# 4. Calendar


st.subheader(
    "Calendar"
)

day_lookup = {
    row["date"].date():
        row
    for _, row in meeting_df.iterrows()
}


if (
    "calendar_month"
    not in st.session_state
):
    last_meeting_date = (
        meeting_df.iloc[-1]["date"]
    )

    st.session_state.calendar_month = (
        last_meeting_date.replace(
            day=1
        )
    )


if (
    "selected_day"
    not in st.session_state
):
    st.session_state.selected_day = None


nav_prev, nav_label, nav_next = (
    st.columns(
        [1, 3, 1]
    )
)


with nav_prev:
    if st.button(
        "← Prev",
        width="stretch"
    ):
        current = (
            st.session_state.calendar_month
        )

        prev_month_last_day = (
            current -
            timedelta(days=1)
        )

        st.session_state.calendar_month = (
            prev_month_last_day.replace(
                day=1
            )
        )

        st.rerun()


with nav_label:
    st.markdown(
        f"<h4 style='text-align:center'>"
        f"{st.session_state.calendar_month.strftime('%B %Y')}"
        f"</h4>",
        unsafe_allow_html=True
    )


with nav_next:
    if st.button(
        "Next →",
        width="stretch"
    ):
        current = (
            st.session_state.calendar_month
        )

        if current.month == 12:
            next_month_first_day = (
                current.replace(
                    year=current.year + 1,
                    month=1,
                    day=1
                )
            )
        else:
            next_month_first_day = (
                current.replace(
                    month=current.month + 1,
                    day=1
                )
            )

        st.session_state.calendar_month = (
            next_month_first_day
        )

        st.rerun()


month_start = (
    st.session_state.calendar_month
)

if month_start.month == 12:
    next_month_start = (
        month_start.replace(
            year=month_start.year + 1,
            month=1
        )
    )
else:
    next_month_start = (
        month_start.replace(
            month=month_start.month + 1
        )
    )


days_in_month = (
    next_month_start -
    timedelta(days=1)
).day

leading_blanks = (
    month_start.weekday()
)

weekday_cols = st.columns(7)

for col, label in zip(
    weekday_cols,
    [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun"
    ]
):
    col.markdown(
        f"<div style='text-align:center; "
        f"opacity:0.6; font-size:12px'>"
        f"{label}</div>",
        unsafe_allow_html=True
    )


cells = (
    [None] * leading_blanks
    +
    list(
        range(
            1,
            days_in_month + 1
        )
    )
)

while len(cells) % 7 != 0:
    cells.append(None)


for week_start in range(
    0,
    len(cells),
    7
):
    week_cols = st.columns(7)

    for col, day_num in zip(
        week_cols,
        cells[
            week_start:
            week_start + 7
        ]
    ):
        if day_num is None:
            col.markdown(
                "&nbsp;",
                unsafe_allow_html=True
            )

            continue

        this_date = (
            month_start
            .replace(
                day=day_num
            )
            .date()
        )

        day_data = day_lookup.get(
            this_date
        )

        with col:
            if day_data is not None:
                clicked = st.button(
                    f"{day_num}",
                    key=(
                        f"cal_{this_date.isoformat()}"
                    ),
                    width="stretch",
                    type=(
                        "primary"
                        if
                        st.session_state.selected_day
                        == this_date
                        else
                        "secondary"
                    )
                )

                if clicked:
                    st.session_state.selected_day = (
                        this_date
                    )

                    st.rerun()

                st.markdown(
                    f"<div style='text-align:center; "
                    f"font-size:11px; "
                    f"color:#2ecc71'>"
                    f"{day_data['avg_attendance_pct']}%"
                    f"</div>",
                    unsafe_allow_html=True
                )

            else:
                st.markdown(
                    f"<div style='text-align:center; "
                    f"padding:8px 0; "
                    f"opacity:0.35'>"
                    f"{day_num}"
                    f"</div>",
                    unsafe_allow_html=True
                )


if (
    st.session_state.selected_day
    is not None
    and
    st.session_state.selected_day
    in day_lookup
):
    selected = day_lookup[
        st.session_state.selected_day
    ]

    st.markdown(
        f"**{st.session_state.selected_day.strftime('%d %B %Y')} "
        f"— {selected['meeting_title']}**"
    )

    sel_col1, sel_col2 = (
        st.columns(2)
    )

    sel_col1.metric(
        "Attendance Rate",
        f"{selected['avg_attendance_pct']}%"
    )

    sel_col2.metric(
        "Absent Rate",
        f"{selected['absent_rate_pct']}%"
    )