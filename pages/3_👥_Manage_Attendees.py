import json
import os

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTENDEES_FILE = os.path.join(PROJECT_ROOT, "attendees.json")

st.set_page_config(page_title="Manage Attendees", page_icon="👥", layout="wide")

st.title("👥 Manage Attendees")
st.caption(
    "This is the master list of everyone expected to attend meetings. "
    "Every meeting's attendance is checked against this list — anyone "
    "on here who doesn't show up in a meeting gets marked **Absent**."
)


def load_attendees():
    if not os.path.exists(ATTENDEES_FILE):
        return []
    try:
        with open(ATTENDEES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_attendees(attendees):
    with open(ATTENDEES_FILE, "w", encoding="utf-8") as f:
        json.dump(attendees, f, indent=2)


attendees = load_attendees()

st.divider()


# Add new attendee


st.subheader("Add a new attendee")

with st.form("add_attendee_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        new_name = st.text_input("Name")
        new_joining_date = st.date_input("Joining Date")

    with col2:
        new_email = st.text_input("Email")
        new_working_period = st.selectbox(
            "Working Period",
            ["Full-time", "Part-time", "Intern", "Contract"],
        )

    submitted = st.form_submit_button("Add Attendee", type="primary")

    if submitted:
        if not new_name.strip():
            st.error("Name is required.")
        elif any(a["name"].strip().lower() == new_name.strip().lower() for a in attendees):
            st.error(f"'{new_name}' is already in the list.")
        else:
            attendees.append(
                {
                    "name": new_name.strip(),
                    "email": new_email.strip(),
                    "joining_date": new_joining_date.isoformat(),
                    "working_period": new_working_period,
                }
            )
            save_attendees(attendees)
            st.success(f"Added {new_name}.")
            st.rerun()

st.divider()


# Current list + remove


st.subheader(f"Current attendee list ({len(attendees)})")

if not attendees:
    st.info("No attendees added yet. Use the form above to add the first one.")
else:
    for i, person in enumerate(attendees):
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 1])

            col1.write(f"**{person['name']}**")
            col2.write(person.get("email", "—"))
            col3.write(person.get("joining_date", "—"))
            col4.write(person.get("working_period", "—"))

            with col5:
                if st.button("Remove", key=f"remove_{i}"):
                    attendees.pop(i)
                    save_attendees(attendees)
                    st.rerun()