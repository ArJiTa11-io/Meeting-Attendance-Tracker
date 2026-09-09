import pandas as pd


STATUS_THRESHOLDS = [
    (90, "Present"),
    (75, "Partially Present"),
    (0, "Low Attendance"),
]


def read_csv(file_path):
    """Step 1: Read the raw CSV file."""
    df = pd.read_csv(file_path)
    return df


def validate_rows(df):
    
    errors = []
    df = df.copy()
    df["_row_num"] = df.index + 2  
   
    missing_name = df["Name"].isna() | (df["Name"].astype(str).str.strip() == "")
    for i in df[missing_name]["_row_num"]:
        errors.append(f"Row {i}: missing name - skipped")
    df = df[~missing_name]

  
    missing_time = df["Join Time"].isna() | df["Leave Time"].isna()
    for i in df[missing_time]["_row_num"]:
        errors.append(f"Row {i}: missing join/leave time - skipped")
    df = df[~missing_time]

   
    df["Join Time"] = pd.to_datetime(df["Join Time"], errors="coerce")
    df["Leave Time"] = pd.to_datetime(df["Leave Time"], errors="coerce")

    bad_timestamp = df["Join Time"].isna() | df["Leave Time"].isna()
    for i in df[bad_timestamp]["_row_num"]:
        errors.append(f"Row {i}: unreadable timestamp - skipped")
    df = df[~bad_timestamp]

    
    leave_before_join = df["Leave Time"] < df["Join Time"]
    for i in df[leave_before_join]["_row_num"]:
        errors.append(f"Row {i}: leave time before join time - skipped")
    df = df[~leave_before_join]

    
    zero_duration = df["Leave Time"] == df["Join Time"]
    for i in df[zero_duration]["_row_num"]:
        errors.append(f"Row {i}: zero duration session - skipped")
    df = df[~zero_duration]

   
    dup_mask = df.duplicated(subset=["Name", "Email", "Join Time", "Leave Time"], keep="first")
    for i in df[dup_mask]["_row_num"]:
        errors.append(f"Row {i}: duplicate session - skipped")
    df = df[~dup_mask]

    df = df.drop(columns=["_row_num"])
    return df, errors


def clean_data(df):
    
    df = df.copy()
    df["Name"] = df["Name"].str.strip().str.title()
    df["Email"] = df["Email"].str.strip().str.lower()
    return df


def calculate_attendance(df, meeting_duration_min=None):
    
    df = df.copy()
    df["Session Duration (min)"] = (
        (df["Leave Time"] - df["Join Time"]).dt.total_seconds() / 60
    )

    if meeting_duration_min is None:
        meeting_duration_min = (
            (df["Leave Time"].max() - df["Join Time"].min()).total_seconds() / 60
        )

    summary = df.groupby(["Name", "Email"]).agg(
        Date=("Join Time", lambda x: x.dt.date.iloc[0]),
        **{"Join Time": ("Join Time", "min")},
        **{"Leave Time": ("Leave Time", "max")},
        **{"Duration (min)": ("Session Duration (min)", "sum")},
        Sessions=("Session Duration (min)", "count"),
    ).reset_index()

    summary["Duration (min)"] = summary["Duration (min)"].round(1)

 
    summary["Attendance %"] = (
        (summary["Duration (min)"] / meeting_duration_min) * 100
    ).clip(upper=100).round(1)

  
    def get_status(pct):
        for cutoff, label in STATUS_THRESHOLDS:
            if pct >= cutoff:
                return label
        return "Absent"

    summary["Status"] = summary["Attendance %"].apply(get_status)

    return summary, meeting_duration_min


def process(file_path, meeting_duration_min=None):
    df = read_csv(file_path)
    df, errors = validate_rows(df)
    df = clean_data(df)
    summary, used_duration = calculate_attendance(df, meeting_duration_min)
    return summary, errors, used_duration


if __name__ == "__main__":
    result, errors, meeting_duration = process("sample_meet_report_with_errors.csv")

    print(f"Meeting duration used for % calculation: {meeting_duration:.1f} min\n")

    if errors:
        print("Rows skipped during validation:")
        for e in errors:
            print(" -", e)
        print()

    print(result.to_string(index=False))
    result.to_csv("cleaned_attendance_output.csv", index=False)
    print("\nSaved to cleaned_attendance_output.csv")