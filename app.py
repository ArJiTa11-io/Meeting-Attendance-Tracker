import streamlit as st


st.set_page_config(
    page_title="Meeting Attendance Tracker",
    page_icon="📋",
    layout="wide"
)


pages = [
    st.Page(
        "pages/0_🤖_Start_Meeting_Bot.py",
        title="Start Meeting Bot",
        icon="🤖"
    ),
    st.Page(
        "pages/1_📊_Dashboard.py",
        title="Dashboard",
        icon="📊"
    ),
    st.Page(
        "pages/2_📅_Meeting_History.py",
        title="Meeting History",
        icon="📋"
    ),
    st.Page(
        "pages/3_👥_Manage_Attendees.py",
        title="Manage Attendees",
        icon="👥"
    )
]


navigation = st.navigation(
    pages
)

navigation.run()