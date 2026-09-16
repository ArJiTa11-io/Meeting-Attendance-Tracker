import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Meeting Attendance"
WORKSHEET_NAME = "Attendance"

PROCESSED_FILE = "data_processing/cleaned_attendance_output.csv"


def connect_to_sheet():
    """Connect to the attendance Google Sheet."""

    credentials = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )

    client = gspread.authorize(credentials)

    spreadsheet = client.open(SPREADSHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    print("Connected to Google Sheet successfully.")

    return worksheet


def read_processed_data(file_path):
    """Read the processed attendance CSV."""

    df = pd.read_csv(file_path)

    required_columns = [
        "Name",
        "Email",
        "Date",
        "Join Time",
        "Leave Time",
        "Duration (min)",
        "Sessions",
        "Attendance %",
        "Status",
    ]

    for column in required_columns:
        if column not in df.columns:
            raise ValueError(
                f"Required column '{column}' is missing from the CSV."
            )

    return df[required_columns].to_dict("records")


def validate_record(record):
    """Check whether the attendance record has required data."""

    required_fields = [
        "Name",
        "Email",
        "Date",
    ]

    for field in required_fields:
        value = record.get(field)

        if pd.isna(value) or not str(value).strip():
            print(
                f"Invalid record: {field} is missing "
                f"for {record.get('Name', 'Unknown')}"
            )
            return False

    return True


def create_record_key(record):
    """
    Create a unique key for an attendance record.

    Email + Date identifies a participant's attendance
    for a particular meeting date.
    """

    email = str(record.get("Email", "")).strip().lower()
    date = str(record.get("Date", "")).strip()

    return email, date


def prepare_rows(records):
    """Convert processed attendance records into Sheet rows."""

    rows = []

    for record in records:
        row = [
            record.get("Name", ""),
            record.get("Email", ""),
            record.get("Date", ""),
            record.get("Join Time", ""),
            record.get("Leave Time", ""),
            record.get("Duration (min)", ""),
            record.get("Sessions", ""),
            record.get("Attendance %", ""),
            record.get("Status", ""),
        ]

        rows.append(row)

    return rows


def upload_records(records):
    """Upload valid and new attendance records to Google Sheets."""

    worksheet = connect_to_sheet()

    if not records:
        print("No attendance records to upload.")
        return

    existing_rows = worksheet.get_all_records()

    existing_keys = set()

    for row in existing_rows:
        existing_keys.add(create_record_key(row))

    new_records = []

    for record in records:

        if not validate_record(record):
            continue

        record_key = create_record_key(record)

        if record_key in existing_keys:
            print(
                f"Skipping duplicate record: "
                f"{record.get('Name', 'Unknown')}"
            )
            continue

        new_records.append(record)

        # Prevent duplicate records within the current input
        existing_keys.add(record_key)

    if not new_records:
        print("No new records to upload.")
        return

    rows = prepare_rows(new_records)

    worksheet.append_rows(rows)

    print(
        f"{len(new_records)} new attendance record(s) "
        "uploaded successfully."
    )


if __name__ == "__main__":

    records = read_processed_data(PROCESSED_FILE)

    print(
        f"Found {len(records)} processed attendance record(s)."
    )

    upload_records(records)