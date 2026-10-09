import json
import os
import subprocess
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MANAGER_FILE = os.path.join(
    PROJECT_ROOT,
    "meeting-bot",
    "meeting-manager.js"
)

MANAGER_URL = (
    "http://127.0.0.1:8765"
)

IST = ZoneInfo(
    "Asia/Kolkata"
)


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )
    except Exception:
        return None


def format_datetime(value):
    parsed = parse_datetime(
        value
    )

    if parsed is None:
        return "--"

    return parsed.astimezone(
        IST
    ).strftime(
        "%d %b %Y, %I:%M:%S %p"
    )


def format_time(value):
    parsed = parse_datetime(
        value
    )

    if parsed is None:
        return "--"

    return parsed.astimezone(
        IST
    ).strftime(
        "%I:%M:%S %p"
    )


def manager_request(
    method,
    endpoint,
    data=None
):
    url = (
        MANAGER_URL +
        endpoint
    )

    body = None
    headers = {}

    if data is not None:
        body = json.dumps(
            data
        ).encode(
            "utf-8"
        )

        headers[
            "Content-Type"
        ] = "application/json"

    request = Request(
        url,
        data=body,
        headers=headers,
        method=method
    )

    with urlopen(
        request,
        timeout=10
    ) as response:
        raw = response.read()

        if not raw:
            return None

        return json.loads(
            raw.decode(
                "utf-8"
            )
        )


def manager_is_running():
    try:
        result = manager_request(
            "GET",
            "/health"
        )

        return (
            isinstance(
                result,
                dict
            )
            and result.get(
                "status"
            ) == "ok"
        )

    except Exception:
        return False


def start_manager():
    if manager_is_running():
        return True

    try:
        subprocess.Popen(
            [
                "node",
                MANAGER_FILE
            ],
            cwd=PROJECT_ROOT
        )

    except Exception as error:
        st.error(
            f"Could not start meeting manager: {error}"
        )

        return False

    for _ in range(20):
        time.sleep(0.5)

        if manager_is_running():
            return True

    st.error(
        "Meeting manager did not start. "
        "Check the terminal running Streamlit."
    )

    return False


def get_meetings():
    try:
        result = manager_request(
            "GET",
            "/meetings"
        )

        if isinstance(
            result,
            list
        ):
            return result

        return []

    except Exception:
        return []


def normalize_participants(
    participants
):
    if isinstance(
        participants,
        list
    ):
        return participants

    if isinstance(
        participants,
        dict
    ):
        normalized = []

        for name, data in (
            participants.items()
        ):
            if not isinstance(
                data,
                dict
            ):
                data = {}

            normalized.append(
                {
                    "name": name,
                    "email": data.get(
                        "email",
                        ""
                    ),
                    "join_time": data.get(
                        "join_time"
                    ),
                    "leave_time": data.get(
                        "leave_time"
                    ),
                    "duration_minutes":
                        data.get(
                            "duration_minutes",
                            0
                        ),
                    "attendance_percentage":
                        data.get(
                            "attendance_percentage"
                        ),
                    "status":
                        data.get(
                            "status"
                        ),
                    "sessions":
                        data.get(
                            "sessions",
                            []
                        )
                }
            )

        return normalized

    return []


def calculate_live_duration(
    participant
):
    sessions = participant.get(
        "sessions",
        []
    )

    total_seconds = 0

    now = datetime.now(
        ZoneInfo("UTC")
    )

    for session in sessions:
        join_time = parse_datetime(
            session.get(
                "join_time"
            )
        )

        if join_time is None:
            continue

        leave_time = parse_datetime(
            session.get(
                "leave_time"
            )
        )

        if leave_time is None:
            leave_time = now

        duration = (
            leave_time -
            join_time
        ).total_seconds()

        if duration > 0:
            total_seconds += duration

    return total_seconds


def render_participant(
    participant
):
    name = participant.get(
        "name",
        "Unknown"
    )

    sessions = participant.get(
        "sessions",
        []
    )

    percentage = participant.get(
        "attendance_percentage"
    )

    status = participant.get(
        "status"
    )

    currently_present = (
        bool(sessions)
        and sessions[-1].get(
            "leave_time"
        ) is None
    )

    if currently_present:
        display_status = (
            "🟢 Currently Present"
        )
    else:
        display_status = (
            status or
            "⚪ Left Meeting"
        )

    duration_seconds = (
        calculate_live_duration(
            participant
        )
    )

    minutes = int(
        duration_seconds // 60
    )

    seconds = int(
        duration_seconds % 60
    )

    with st.container(
        border=True
    ):
        col1, col2, col3 = (
            st.columns(
                [2, 1, 1]
            )
        )

        with col1:
            st.markdown(
                f"### {name}"
            )

            st.caption(
                display_status
            )

        with col2:
            st.metric(
                "Sessions",
                len(sessions)
            )

        with col3:
            st.metric(
                "Duration",
                f"{minutes}m {seconds}s"
            )

        if percentage is not None:
            st.caption(
                "Attendance: "
                f"{float(percentage):.1f}%"
            )

        session_rows = []

        for session in sessions:
            session_join = (
                session.get(
                    "join_time"
                )
            )

            session_leave = (
                session.get(
                    "leave_time"
                )
            )

            join_dt = parse_datetime(
                session_join
            )

            leave_dt = parse_datetime(
                session_leave
            )

            if (
                join_dt is not None
                and leave_dt is not None
            ):
                duration = (
                    leave_dt -
                    join_dt
                ).total_seconds()

            elif join_dt is not None:
                duration = (
                    datetime.now(
                        ZoneInfo("UTC")
                    ) -
                    join_dt
                ).total_seconds()

            else:
                duration = 0

            session_rows.append(
                {
                    "Joining Time":
                        format_time(
                            session_join
                        ),
                    "Leaving Time":
                        (
                            format_time(
                                session_leave
                            )
                            if session_leave
                            else
                            "Still in meeting"
                        ),
                    "Duration":
                        f"{duration:.1f} sec"
                }
            )

        if session_rows:
            with st.expander(
                "Session History"
            ):
                st.dataframe(
                    session_rows,
                    width="stretch",
                    hide_index=True
                )


def render_meeting(
    meeting
):
    meeting_id = meeting.get(
        "meeting_id",
        "Unknown"
    )

    title = (
        meeting.get(
            "meeting_title"
        )
        or meeting_id
    )

    status = meeting.get(
        "status",
        "unknown"
    )

    participants = (
        normalize_participants(
            meeting.get(
                "participants",
                []
            )
        )
    )

    with st.container(
        border=True
    ):
        st.subheader(
            f"📋 {title}"
        )

        col1, col2, col3, col4 = (
            st.columns(4)
        )

        with col1:
            st.metric(
                "Status",
                (
                    "🟢 Active"
                    if status == "active"
                    else status.title()
                )
            )

        with col2:
            st.metric(
                "Participants",
                len(participants)
            )

        with col3:
            st.metric(
                "Low Attendance",
                meeting.get(
                    "low_attendance_count",
                    0
                )
            )

        with col4:
            if (
                meeting.get(
                    "attendance_rate"
                ) is not None
            ):
                st.metric(
                    "Attendance Rate",
                    f"{meeting['attendance_rate']:.1f}%"
                )
            else:
                st.metric(
                    "Attendance Rate",
                    "N/A"
                )

        if meeting.get(
            "start_time"
        ):
            st.caption(
                "Started: "
                + format_datetime(
                    meeting[
                        "start_time"
                    ]
                )
                + " IST"
            )

        if meeting.get(
            "expected_attendees"
        ):
            st.caption(
                "Expected attendees: "
                + str(
                    meeting.get(
                        "total_expected",
                        0
                    )
                )
            )

            st.caption(
                "Present: "
                + str(
                    meeting.get(
                        "present_count",
                        0
                    )
                )
                + " | Absent: "
                + str(
                    meeting.get(
                        "absent_count",
                        0
                    )
                )
            )

        if participants:
            st.markdown(
                "#### Live Participants"
            )

            for participant in (
                participants
            ):
                render_participant(
                    participant
                )
        else:
            st.info(
                "No participants detected yet."
            )

        if status == "active":
            if st.button(
                "⏹ Stop Meeting",
                key=f"stop_{meeting_id}",
                type="secondary"
            ):
                try:
                    manager_request(
                        "DELETE",
                        "/meetings/"
                        + meeting_id
                    )

                    st.success(
                        "Meeting stopped and report saved."
                    )

                    st.rerun()

                except HTTPError as error:
                    try:
                        message = (
                            error.read()
                            .decode(
                                "utf-8"
                            )
                        )

                        st.error(
                            message
                        )

                    except Exception:
                        st.error(
                            "Could not stop meeting."
                        )

                except Exception as error:
                    st.error(
                        f"Could not stop meeting: {error}"
                    )


def main():
    st.title(
        "🤖 Start Meeting Bot"
    )

    st.caption(
        "Start and monitor multiple Google Meet attendance bots."
    )

    if not manager_is_running():
        st.warning(
            "Meeting manager is not running."
        )

        if st.button(
            "Start Meeting Manager",
            type="primary"
        ):
            if start_manager():
                st.success(
                    "Meeting manager started."
                )

                st.rerun()

        st.divider()

    st.subheader(
        "Start New Meeting"
    )

    meeting_title = st.text_input(
        "Meeting Name",
        placeholder=(
            "Optional — e.g. Project Kickoff"
        )
    )

    meet_link = st.text_input(
        "Google Meet Link",
        placeholder=(
            "https://meet.google.com/abc-defg-hij"
        )
    )

    roster_text = st.text_area(
        "Expected Attendees",
        placeholder=(
            "Enter one attendee name per line.\n"
            "Example:\n"
            "Rahul Sharma\n"
            "Priya Singh\n"
            "Aman Verma"
        ),
        height=140
    )

    expected_attendees = [
        name.strip()
        for name in roster_text.splitlines()
        if name.strip()
    ]

    if st.button(
        "▶ Start Bot",
        type="primary"
    ):
        if not meet_link.strip():
            st.error(
                "Please enter a Google Meet link."
            )

        elif not meet_link.startswith(
            "https://meet.google.com/"
        ):
            st.error(
                "Please enter a valid Google Meet link."
            )

        elif not start_manager():
            pass

        else:
            try:
                report = manager_request(
                    "POST",
                    "/meetings",
                    {
                        "meet_link":
                            meet_link.strip(),

                        "meeting_title":
                            meeting_title.strip(),

                        "expected_attendees":
                            expected_attendees
                    }
                )

                st.success(
                    "Bot joined the meeting successfully."
                )

                st.caption(
                    "Meeting ID: "
                    + report.get(
                        "meeting_id",
                        "Unknown"
                    )
                )

                st.rerun()

            except HTTPError as error:
                try:
                    message = (
                        error.read()
                        .decode(
                            "utf-8"
                        )
                    )

                    try:
                        parsed = json.loads(
                            message
                        )

                        st.error(
                            parsed.get(
                                "error",
                                message
                            )
                        )

                    except Exception:
                        st.error(
                            message
                        )

                except Exception:
                    st.error(
                        "Could not start meeting."
                    )

            except URLError:
                st.error(
                    "Meeting manager is not reachable."
                )

            except Exception as error:
                st.error(
                    f"Could not start meeting: {error}"
                )

    st.divider()

    st.subheader(
        "Active Meetings"
    )

    if st.button(
        "🔄 Refresh Meetings"
    ):
        st.rerun()

    meetings = get_meetings()

    if not meetings:
        st.info(
            "No active meetings."
        )

    else:
        st.caption(
            f"{len(meetings)} meeting(s) currently being tracked."
        )

        for meeting in meetings:
            render_meeting(
                meeting
            )


if __name__ == "__main__":
    main()