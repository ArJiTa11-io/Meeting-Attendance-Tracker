# 📋 Meeting Attendance Tracker

A Streamlit-based meeting attendance tracker that uses a Node.js/Playwright Google Meet bot to observe meeting participants and produce attendance reports.

> **Deployment note:** This application controls a real browser session to join Google Meet. It is not a static Streamlit dashboard. Deploy the Streamlit UI, Node.js meeting manager, Playwright/Chrome runtime, persistent storage, and authenticated browser profile together on a machine you control. A basic serverless or ephemeral Streamlit hosting environment may not support this workflow reliably.

## ✨ Features

- 🤖 Start and monitor Google Meet attendance tracking from the Streamlit interface.
- Provide a meeting title and Google Meet link.
- Optionally provide an expected-attendee roster (one attendee per line) to calculate present/absent metrics.
- Track participant join/leave activity and rejoin sessions when detected by the bot.
- Save active meeting state separately from historical meeting reports.
- View historical meeting reports, participant details, and session history.
- Dashboard with attendance metrics and trends based on available stored reports.
- Support multiple meeting tabs through a shared browser context/meeting manager, subject to runtime capacity and Google Meet/browser limitations.
- 👥 **Manage Attendees:** a master list of everyone expected at meetings (name, email, joining date, working period), set up once. The dashboard compares each meeting against it to work out who was Absent.
- 📅 **Calendar drill-down:** click a meeting day on the Dashboard calendar and the Present / Partially Present / Low Attendance / Absent chart switches to that day's meeting.
- 📈 **Latest-meeting KPIs:** attendance rate, absent rate and low-attendee count for the latest meeting, each compared with the meeting before it.

Actual measurements depend on what the bot can observe in the Google Meet interface. Do not treat the output as an official Google attendance record.

## 🧰 Technology

- Python
- Streamlit
- Pandas
- Node.js
- Playwright
- Chromium/Google Chrome
- JSON files for active state and historical reports

## 📁 Project layout

The key files and folders are expected to look similar to:

```text
Meeting-Attendance-Tracker/
├── app.py
├── attendees.json             # master attendee list (Manage Attendees)
├── pages/
│   ├── 0_🤖_Start_Meeting_Bot.py
│   ├── 1_📊_Dashboard.py
│   ├── 2_📅_Meeting_History.py
│   └── 3_👥_Manage_Attendees.py
├── meeting-bot/
│   ├── bot.js
│   ├── meeting-manager.js
│   ├── browser-profile/       # local authenticated browser profile; do not commit
│   └── output/
│       ├── active/            # live reports; generated at runtime
│       └── reports/           # historical JSON reports
├── requirements.txt
├── package.json
├── package-lock.json
└── README.md
```

Names may differ slightly if your local branch has changed. Keep the UI report paths aligned with the backend output directories.

## ✅ Requirements

Install the following on the host machine:

- Python 3.10+ (Python 3.11 is a reasonable deployment target)
- Node.js LTS
- npm
- Google Chrome or a compatible Chromium browser supported by your Playwright setup
- A persistent writable disk for the browser profile and JSON reports

💻 Local setup on Windows 0. Before you start 🧱

Install these first, then check them in a terminal:

powershell
py --version
node --version
git --version

Each command should print a version number. If one says "not recognized", install that tool (Python 3.10+, Node.js LTS, or Git) and open a new terminal.

💡 Tip: every command below must be run inside the project folder. To open a folder in the terminal, type cd followed by a space and the folder path, for example cd D:\projects\Meeting-Attendance-Tracker. Typing the path alone does not work and gives a "term is not recognized" error. In VS Code you can also right-click the folder and choose Open in Integrated Terminal.

1. Clone the repository 📥
   powershell
   git clone <YOUR_REPOSITORY_URL>
   cd Meeting-Attendance-Tracker
2. Create and activate a Python environment 🐍
   powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt

If PowerShell blocks activation, run the environment's Python directly or follow your organization's execution-policy guidance. Do not disable security controls globally just to activate a virtual environment.

3. Install Node.js dependencies 📦
   powershell
   npm install

Run this from the directory containing package.json. If the Node package file is inside meeting-bot, run npm install from that directory instead.

4. Prepare the authenticated browser profile 🔐

The bot uses a persistent browser profile so it can reuse a signed-in Google account. On the machine that will run the bot:

Start the browser using the project's configured persistent profile.
Sign in to the Google account that is permitted to join the intended meetings.
Complete any required account security checks.
Close the browser cleanly before starting the manager.

The exact command for initializing the profile depends on the checked-in bot.js/meeting-manager.js implementation. Do not copy a personal browser profile from another computer. Never commit meeting-bot/browser-profile/ or credentials/cookies to Git.

5. Start the app 🚀
   powershell
   streamlit run app.py

Open the local URL printed by Streamlit, commonly http://localhost:8501.

In the current setup, the Start Meeting Bot page is expected to start the Node.js manager if it is not already running. If your current version requires manual startup, open a second terminal and run:

powershell
node meeting-bot/meeting-manager.js

Use the startup approach implemented in your current branch; avoid starting multiple manager processes against the same browser profile.

## 🧭 How to use

1. Open **Manage Attendees** and add the people expected at your meetings (name, email, joining date, working period). Do this once, and update it when the team changes.
2. Open **Start Meeting Bot**.
3. Enter a recognizable meeting title.
4. Paste the full Google Meet URL.
5. If absence reporting is required, enter the expected attendee roster, one person per line. Use names consistently with the names shown in Meet.
6. Start tracking and allow the browser to open/join the meeting.
7. Keep the host process and browser session running while tracking is active.
8. Open **Dashboard** to review metrics derived from saved reports.
9. Open **Meeting History** to select a completed report and inspect participant/session details.

### 📊 Attendance interpretation

- The bot records participants it can detect through the Meet interface.
- **Absent rate requires an expected-attendee roster.** Without a roster, the system cannot reliably infer who was invited but never joined.
- Rejoin sessions may be listed separately; the total attendance duration should be based on the sum of observed sessions if that is how the current report processor calculates it.
- "Low Attendance" and "Partially Present" are determined by the thresholds implemented in the current project code. Verify these thresholds before using the reports for formal decisions.
- Reports are only as accurate as the visible participant list and polling interval. Validate results against a real meeting before relying on them.

### 🔴 How "Absent" is calculated

The dashboard works out the absent count in this order:

1. If the report already contains `absent_count` and `total_expected`, it uses those.
2. Otherwise it compares the meeting's participants with the Manage Attendees list (`attendees.json`).
3. If neither exists, it shows Low Attendance in place of Absent and prints a note saying so.

## 💾 Data and storage

Typical runtime paths:

- `meeting-bot/output/active/` — live reports for meetings in progress.
- `meeting-bot/output/reports/` — historical JSON reports.
- `meeting-bot/browser-profile/` — persistent browser profile and sign-in state.
- `attendees.json` — master attendee list, edited from the Manage Attendees page.

Back up historical reports if they must be retained. Ensure the app process has read/write access to the output directories. Do not expose raw report files or browser profile data publicly.

## 🌐 Deployment checklist

Before deploying:

- [ ] Test start, join, live tracking, stop/finalize, and report generation on the target host.
- [ ] Confirm Chrome/Chromium and Playwright work in the target environment.
- [ ] Confirm the browser profile remains signed in after a restart.
- [ ] Confirm persistent disk is attached and report files survive redeploys/restarts.
- [ ] Confirm `attendees.json` is on persistent storage and survives redeploys.
- [ ] Keep the Streamlit app and Node manager on the same host or configure a secure, reachable manager service.
- [ ] Configure the manager to bind to loopback/private networking unless remote access is explicitly secured.
- [ ] Do not expose the manager API publicly without authentication and network controls.
- [ ] Add `browser-profile/`, `.env`, secrets, and generated runtime output to `.gitignore` as appropriate.
- [ ] Use HTTPS for any publicly accessible UI and restrict access to authorized users.
- [ ] Test simultaneous meetings at the expected scale; do not assume unlimited concurrency.
- [ ] Inform meeting participants as required by your organization's policies and applicable law.

## 🛠️ Common issues

### 📅 Meetings do not appear in Meeting History

1. Confirm a report JSON file was generated under `meeting-bot/output/reports/`.
2. Confirm the Meeting History page reads that same directory.
3. Refresh the page; report caching may delay new reports briefly.
4. Check the Node manager terminal for errors during finalization.

### 🤖 The bot does not join the meeting

- Confirm the URL is a valid Google Meet link.
- Check that the configured browser profile is signed in and can join the meeting manually.
- Check host/admission settings and whether the account is allowed into the meeting.
- Review Playwright/Chrome errors in the terminal.
- Google Meet's UI can change, which may require selector updates.

### 🔒 Browser/profile is already in use

- Stop duplicate manager processes.
- Close any Chrome process using the same persistent profile before restarting.
- Do not run two managers against the same profile directory.

### 👥 No absent attendees are shown

- Add the expected people on the **Manage Attendees** page.
- Supply an expected-attendee roster for that meeting.
- Check that attendee names in the roster match the names the bot observes.

### 📉 Dashboard metrics look incomplete

- Confirm historical JSON files exist and contain the fields the dashboard expects.
- Avoid manually editing generated JSON unless you understand the schema.
- Use real test meetings to validate calculations.

## 🛡️ Privacy and security

The browser profile can contain Google sign-in state, cookies, and other sensitive browser data. Historical reports may contain participant names, timestamps, and attendance patterns.

- Restrict access to the host and output directory.
- Do not commit browser profiles, cookies, credentials, API tokens, or private meeting URLs.
- Do not publish raw attendance JSON files.
- Retain/delete attendance records according to your organization's policy.
- Obtain any required consent before tracking meetings.

## ⚠️ Limitations

- The bot depends on the Google Meet web interface and Playwright selectors, which can change.
- Attendance capture is observational and may miss brief joins/leaves between polls.
- The system does not know the full invited roster unless one is supplied.
- Reliable deployment requires a persistent browser runtime and storage.
- Multiple simultaneous meetings consume browser and CPU/memory resources and must be load-tested.
- This README describes the intended/current project structure; verify commands and file paths against the exact commit you deploy.

## 🗺️ Status & Roadmap

- ✅ Done: the bot records real meetings, plus the Dashboard, Meeting History and Manage Attendees pages.
- 🚧 In progress: testing and preparing for deployment.
- 🔭 Planned: hosting the dashboard and bot together.

## 🤝 Contributors

- Adhrav
- Arjita

## 💬 Feedback

Found a bug or have an idea? We'd love to hear it. 🎉

Open an issue in the [Issues tab](https://github.com/ArJiTa11-io/Meeting-Attendance-Tracker/issues) with what you did, what you expected, and what happened (a screenshot helps). Every issue gets read. 🐛

## 📄 License

Add the license that applies to your project before distributing it.
