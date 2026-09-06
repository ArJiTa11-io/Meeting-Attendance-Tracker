"""
Part A - Data Processing
Reads a Google Meet participant CSV, cleans the data, and calculates
attendance duration per participant (handling multiple join/leave sessions).

Input CSV columns expected: Name, Email, Join Time, Leave Time
Output: a clean pandas DataFrame (and CSV) with one row per participant:
Name, Email, Date, Total Duration (minutes), Sessions
"""

import pandas as pd


def read_csv(file_path):
    """Step 1: Read the raw CSV file."""
    df = pd.read_csv(file_path)
    return df


def clean_data(df):
    """Step 2: Clean names/emails and parse date-time columns."""
    df = df.copy()

    # Clean whitespace and casing issues
    df["Name"] = df["Name"].str.strip().str.title()
    df["Email"] = df["Email"].str.strip().str.lower()

    # Drop rows with missing essential data
    df = df.dropna(subset=["Name", "Email", "Join Time", "Leave Time"])

    # Convert to actual datetime objects
    df["Join Time"] = pd.to_datetime(df["Join Time"])
    df["Leave Time"] = pd.to_datetime(df["Leave Time"])

    return df


def calculate_duration(df):
    """Step 3: Calculate total attendance duration per participant,
    correctly handling multiple join/leave sessions (rejoins)."""

    # Duration of each individual session, in minutes
    df["Session Duration (min)"] = (
        (df["Leave Time"] - df["Join Time"]).dt.total_seconds() / 60
    )

    # Group by participant (Email is the reliable identifier)
    summary = df.groupby(["Name", "Email"]).agg(
        Date=("Join Time", lambda x: x.dt.date.iloc[0]),
        Total_Duration_Min=("Session Duration (min)", "sum"),
        Sessions=("Session Duration (min)", "count"),
    ).reset_index()

    summary["Total_Duration_Min"] = summary["Total_Duration_Min"].round(1)

    return summary


def process(file_path):
    df = read_csv(file_path)
    df = clean_data(df)
    summary = calculate_duration(df)
    return summary


if __name__ == "__main__":
    result = process("sample_meet_report.csv")
    print(result.to_string(index=False))
    result.to_csv("cleaned_attendance_output.csv", index=False)
    print("\nSaved to cleaned_attendance_output.csv")
