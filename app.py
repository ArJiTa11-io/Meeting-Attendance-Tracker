import io
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

ATTENDANCE_FILE = os.path.join(
    PROJECT_ROOT,
    "meeting-bot",
    "output",
    "attendance.json"
)

BOT_FILE = os.path.join(
    PROJECT_ROOT,
    "meeting-bot",
    "bot.js"
)

IST = ZoneInfo("Asia/Kolkata")


st.set_page_config(
    page_title="Meeting Attendance Tracker",
    page_icon="📋",
    layout="wide"
)


st.title("📋 Meeting Attendance Tracker")
st.write("Automated Google Meet attendance monitoring")


if "bot_process" not in st.session_state:
    st.session_state.bot_process = None


st.subheader("Start Meeting Bot")

meet_link = st.text_input(
    "Google Meet Link",
    placeholder="https://meet.google.com/abc-defg-hij"
)


if st.button("Start Bot", type="primary"):

    if not meet_link.strip():
        st.error("Please enter a Google Meet link.")

    elif not meet_link.startswith(
        "https://meet.google.com/"
    ):
        st.error("Please enter a valid Google Meet link.")

    elif (
        st.session_state.bot_process is not None
        and st.session_state.bot_process.poll() is None
    ):
        st.warning("Bot is already running.")

    else:
        try:
            st.session_state.bot_process = subprocess.Popen(
                [
                    "node",
                    BOT_FILE,
                    meet_link.strip()
                ],
                cwd=PROJECT_ROOT
            )

            st.success(
                "Bot started. Opening Google Meet..."
            )

        except Exception as error:
            st.error(
                f"Could not start bot: {error}"
            )


st.divider()


if os.path.exists(ATTENDANCE_FILE):

    try:

        with open(
            ATTENDANCE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            attendance_data = json.load(file)

        meeting_id = attendance_data.get(
            "meeting_id",
            "Unknown"
        )

        status = attendance_data.get(
            "status",
            "Unknown"
        )

        last_updated = attendance_data.get(
            "last_updated"
        )

        participants = attendance_data.get(
            "participants",
            {}
        )

        currently_in_meeting = 0

        for participant_data in participants.values():

            sessions = participant_data.get(
                "sessions",
                []
            )

            if sessions:

                latest_session = sessions[-1]

                if latest_session.get(
                    "leave_time"
                ) is None:
                    currently_in_meeting += 1


        meeting_date = None

        all_join_times = []

        for participant_data in participants.values():

            for session in participant_data.get(
                "sessions",
                []
            ):

                join_time = session.get(
                    "join_time"
                )

                if join_time:
                    all_join_times.append(
                        join_time
                    )

        if all_join_times:

            earliest_join = min(
                all_join_times
            )

            meeting_date = datetime.fromisoformat(
                earliest_join.replace(
                    "Z",
                    "+00:00"
                )
            ).astimezone(IST)

        elif last_updated:

            meeting_date = datetime.fromisoformat(
                last_updated.replace(
                    "Z",
                    "+00:00"
                )
            ).astimezone(IST)


        if meeting_date:

            st.markdown(
                f"""<div style="padding: 20px 24px; border-radius: 12px; border: 1px solid #444; margin-bottom: 20px; background: rgba(255, 255, 255, 0.03);">
            <div style="font-size: 14px; font-weight: 600; opacity: 0.7; letter-spacing: 1px;">MEETING DATE</div>
            <div style="font-size: 32px; font-weight: 700; margin-top: 5px;">{meeting_date.strftime("%d %B %Y")}</div>
            <div style="font-size: 15px; opacity: 0.65; margin-top: 4px;">{meeting_date.strftime("%A")}</div>
            </div>""",
                unsafe_allow_html=True
            )


        col1, col2, col3, col4 = st.columns(4)

        with col1:

            if status == "active":

                st.metric(
                    "Bot Status",
                    "🟢 Active"
                )

            else:

                st.metric(
                    "Bot Status",
                    status.title()
                )


        with col2:

            st.metric(
                "Tracked Participants",
                len(participants)
            )


        with col3:

            st.metric(
                "Currently in Meeting",
                currently_in_meeting
            )


        with col4:

            st.metric(
                "Meeting ID",
                meeting_id
            )


        if last_updated:

            updated_time = datetime.fromisoformat(
                last_updated.replace(
                    "Z",
                    "+00:00"
                )
            ).astimezone(IST)

            st.caption(
                "Last updated: "
                + updated_time.strftime(
                    "%d %b %Y, %I:%M:%S %p"
                )
                + " IST"
            )


        st.divider()


        st.subheader("Participant Attendance")


        report_rows = []


        for name, participant_data in participants.items():

            sessions = participant_data.get(
                "sessions",
                []
            )

            total_seconds = 0

            for session in sessions:

                join_time = datetime.fromisoformat(
                    session["join_time"].replace(
                        "Z",
                        "+00:00"
                    )
                )

                leave_time = session.get(
                    "leave_time"
                )

                if leave_time:

                    leave_time = datetime.fromisoformat(
                        leave_time.replace(
                            "Z",
                            "+00:00"
                        )
                    )

                    duration = (
                        leave_time - join_time
                    ).total_seconds()

                else:

                    current_time = datetime.now(
                        ZoneInfo("UTC")
                    )

                    duration = (
                        current_time - join_time
                    ).total_seconds()

                total_seconds += duration


            minutes = int(
                total_seconds // 60
            )

            seconds = int(
                total_seconds % 60
            )


            if sessions and sessions[-1].get(
                "leave_time"
            ) is None:

                participant_status = (
                    "Currently Present"
                )

            else:

                participant_status = (
                    "Left Meeting"
                )


            report_rows.append(
                {
                    "Participant": name,
                    "Sessions": len(sessions),
                    "Duration": (
                        f"{minutes}m {seconds}s"
                    ),
                    "Status": participant_status
                }
            )


        csv_df = pd.DataFrame(
            report_rows
        )


        if not csv_df.empty:

            csv_data = csv_df.to_csv(
                index=False
            ).encode("utf-8")


            excel_buffer = io.BytesIO()


            with pd.ExcelWriter(
                excel_buffer,
                engine="openpyxl"
            ) as writer:

                csv_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Attendance"
                )


            excel_data = excel_buffer.getvalue()


            col1, col2 = st.columns(2)


            with col1:

                st.download_button(
                    label="⬇ Download CSV",
                    data=csv_data,
                    file_name=(
                        f"attendance_"
                        f"{meeting_id}.csv"
                    ),
                    mime="text/csv",
                    width="stretch"
                )


            with col2:

                st.download_button(
                    label="⬇ Download Excel",
                    data=excel_data,
                    file_name=(
                        f"attendance_"
                        f"{meeting_id}.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    width="stretch"
                )


        st.divider()


        if not participants:

            st.info(
                "No participants have been detected yet."
            )


        for name, participant_data in participants.items():

            sessions = participant_data.get(
                "sessions",
                []
            )

            total_seconds = 0

            session_rows = []


            for session in sessions:

                join_time = datetime.fromisoformat(
                    session["join_time"].replace(
                        "Z",
                        "+00:00"
                    )
                )

                join_time_ist = join_time.astimezone(
                    IST
                )

                leave_time = session.get(
                    "leave_time"
                )


                if leave_time:

                    leave_time = datetime.fromisoformat(
                        leave_time.replace(
                            "Z",
                            "+00:00"
                        )
                    )

                    leave_time_ist = leave_time.astimezone(
                        IST
                    )

                    duration = (
                        leave_time - join_time
                    ).total_seconds()

                    leave_display = (
                        leave_time_ist.strftime(
                            "%I:%M:%S %p"
                        )
                    )

                else:

                    current_time = datetime.now(
                        IST
                    )

                    duration = (
                        current_time
                        - join_time_ist
                    ).total_seconds()

                    leave_display = (
                        "Still in meeting"
                    )


                total_seconds += duration


                session_rows.append(
                    {
                        "Join": join_time_ist.strftime(
                            "%I:%M:%S %p"
                        ),
                        "Leave": leave_display,
                        "Duration": (
                            f"{duration:.1f} sec"
                        )
                    }
                )


            minutes = int(
                total_seconds // 60
            )

            seconds = int(
                total_seconds % 60
            )


            if sessions and sessions[-1].get(
                "leave_time"
            ) is None:

                participant_status = (
                    "🟢 In Meeting"
                )

            else:

                participant_status = (
                    "⚪ Left Meeting"
                )


            with st.container(
                border=True
            ):

                st.markdown(
                    f"### {name}"
                )

                st.caption(
                    participant_status
                )

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        f"**Sessions:** "
                        f"{len(sessions)}"
                    )

                with col2:

                    st.write(
                        f"**Total Duration:** "
                        f"{minutes}m "
                        f"{seconds}s"
                    )

                st.dataframe(
                    session_rows,
                    width="stretch",
                    hide_index=True
                )


    except Exception as error:

        st.error(
            f"Could not read attendance data: "
            f"{error}"
        )

else:

    st.info(
        "Start the bot to begin collecting "
        "attendance data."
    )


if st.button("🔄 Refresh Data"):

    st.rerun()