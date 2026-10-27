
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BROWSER_PROFILE = path.join(__dirname, "browser-profile");
const OUTPUT_DIRECTORY = path.join(__dirname, "output");
const ACTIVE_DIRECTORY = path.join(OUTPUT_DIRECTORY, "active");
const REPORTS_DIRECTORY = path.join(OUTPUT_DIRECTORY, "reports");

const POLL_INTERVAL_MS = 10000;
const LOW_ATTENDANCE_THRESHOLD = 50;
const PRESENT_THRESHOLD = 70;

// Set BOT_DISPLAY_NAME in your environment if the authenticated bot
// uses a different Google Meet display name.
const BOT_DISPLAY_NAME = (process.env.BOT_DISPLAY_NAME || "Adhrav Rai")
    .trim()
    .toLocaleLowerCase();

for (const directory of [
    OUTPUT_DIRECTORY,
    ACTIVE_DIRECTORY,
    REPORTS_DIRECTORY
]) {
    fs.mkdirSync(directory, { recursive: true });
}

function getMeetingId(meetLink) {
    if (!meetLink) return null;

    const match = String(meetLink).match(
        /(?:https?:\/\/)?meet\.google\.com\/([^/?#]+)/
    );

    return match ? match[1] : null;
}

function normalizeWhitespace(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function canonicalizeName(rawValue) {
    let name = normalizeWhitespace(rawValue);

    if (!name || name.length > 120) return "";

    // Reject interface/control text rather than accidentally treating
    // the entire participant tile as a person's name.
    const interfaceTerms =
        /\b(frame_person|visual_effects|backgrounds and effects|more_vert|more options|reframe|microphone|camera|leave call|present now|host controls)\b/i;

    if (interfaceTerms.test(name)) return "";

    // Remove repeated full-name sequences such as:
    // "Renu Singh Renu Singh" and "Shailesh Rai Shailesh Rai".
    const words = name.split(" ");

    for (let size = 1; size <= Math.floor(words.length / 2); size++) {
        if (words.length % size !== 0) continue;

        const firstSequence = words
            .slice(0, size)
            .join(" ")
            .toLocaleLowerCase();

        let allSequencesMatch = true;

        for (let i = size; i < words.length; i += size) {
            const sequence = words
                .slice(i, i + size)
                .join(" ")
                .toLocaleLowerCase();

            if (sequence !== firstSequence) {
                allSequencesMatch = false;
                break;
            }
        }

        if (allSequencesMatch) {
            name = words.slice(0, size).join(" ");
            break;
        }
    }

    name = normalizeWhitespace(name);

    const invalidLabels = new Set([
        "people",
        "participants",
        "chat",
        "activities",
        "meeting details",
        "messages",
        "more options",
        "microphone",
        "camera",
        "present now",
        "leave call",
        "you"
    ]);

    if (invalidLabels.has(name.toLocaleLowerCase())) return "";

    return name;
}

function participantKey(name) {
    return canonicalizeName(name).toLocaleLowerCase();
}

function isBotParticipant(name) {
    const key = participantKey(name);

    if (!key) return false;

    // Exclude the configured bot account. This is based on the
    // configured display name, not a partial match on other attendees.
    return key === BOT_DISPLAY_NAME;
}

function calculateDurationSeconds(sessions) {
    if (!Array.isArray(sessions)) return 0;

    return sessions.reduce((total, session) => {
        if (!session || !session.join_time) return total;

        const joinTime = new Date(session.join_time).getTime();

        const leaveTime = session.leave_time
            ? new Date(session.leave_time).getTime()
            : Date.now();

        if (!Number.isFinite(joinTime) || !Number.isFinite(leaveTime)) {
            return total;
        }

        return total + Math.max(0, (leaveTime - joinTime) / 1000);
    }, 0);
}

async function createBrowserContext() {
    console.log("Starting authenticated Chrome context...");

    const context = await chromium.launchPersistentContext(
        BROWSER_PROFILE,
        {
            headless: false,
            channel: "chrome"
        }
    );

    await context.grantPermissions(
        ["camera", "microphone"],
        { origin: "https://meet.google.com" }
    );

    console.log("Browser context ready.");
    return context;
}

class MeetingTracker {
    constructor({
        page,
        context,
        meetLink,
        meetingId,
        meetingTitle = "",
        expectedAttendees = []
    }) {
        this.page = page;
        this.context = context;
        this.meetLink = meetLink;
        this.meetingId = meetingId || getMeetingId(meetLink);
        this.meetingTitle = meetingTitle || this.meetingId;

        this.expectedAttendees = Array.isArray(expectedAttendees)
            ? expectedAttendees
                .map(canonicalizeName)
                .filter(Boolean)
            : [];

        this.startedAt = null;
        this.endedAt = null;

        // Store sessions by normalized participant key so casing or
        // repeated whitespace cannot create duplicate people.
        this.sessions = {};
        this.displayNames = {};
        this.activeParticipants = new Map();

        this.polling = false;
        this.pollingPromise = null;
        this.meetingEnded = false;
        this.status = "starting";

        // Do not mark everybody as having left just because one poll
        // temporarily fails to read the participant panel.
        this.consecutiveEmptyPolls = 0;

        this.activeFile = path.join(
            ACTIVE_DIRECTORY,
            `${this.meetingId}.json`
        );

        this.reportFile = null;
    }

    async prepareMeeting() {
        if (!this.meetingId) {
            throw new Error("Invalid Google Meet link.");
        }

        console.log(`[${this.meetingId}] Opening Google Meet...`);

        await this.page.goto(this.meetLink, {
            waitUntil: "domcontentloaded",
            timeout: 30000
        });

        await this.page.waitForTimeout(5000);

        await this.disableMicrophone();
        await this.disableCamera();

        const joinNow = this.page.getByRole("button", {
            name: /join now/i
        }).first();

        const askToJoin = this.page.getByRole("button", {
            name: /ask to join/i
        }).first();

        if (await joinNow.isVisible().catch(() => false)) {
            await joinNow.click();
        } else if (await askToJoin.isVisible().catch(() => false)) {
            await askToJoin.click();

            console.log(
                `[${this.meetingId}] Join request submitted; waiting for admission.`
            );

            await this.page.waitForTimeout(5000);
        } else {
            throw new Error(
                "Could not find a visible Join now or Ask to join button. " +
                "Check the Chrome window for sign-in, account selection, " +
                "permissions, or a meeting error."
            );
        }

        console.log(`[${this.meetingId}] Join action completed.`);

        await this.page.waitForTimeout(5000);
        await this.openPeoplePanel();

        this.startedAt = new Date();
        this.status = "active";

        const timestamp = this.startedAt
            .toISOString()
            .replace(/[:.]/g, "-");

        this.reportFile = path.join(
            REPORTS_DIRECTORY,
            `${this.meetingId}_${timestamp}.json`
        );

        this.saveAttendance("active");
    }

    async disableMicrophone() {
        try {
            const button = this.page.getByRole("button", {
                name: /turn off microphone/i
            }).first();

            if (await button.isVisible()) {
                await button.click();
            }
        } catch (error) {
            console.log(
                `[${this.meetingId}] Microphone state unchanged: ${error.message}`
            );
        }
    }

    async disableCamera() {
        try {
            const button = this.page.getByRole("button", {
                name: /turn off camera/i
            }).first();

            if (await button.isVisible()) {
                await button.click();
            }
        } catch (error) {
            console.log(
                `[${this.meetingId}] Camera state unchanged: ${error.message}`
            );
        }
    }

    async openPeoplePanel() {
        try {
            const peopleButton = this.page.getByRole("button", {
                name: /people|participants/i
            }).first();

            if (await peopleButton.isVisible().catch(() => false)) {
                await peopleButton.click();
            } else {
                await this.page.keyboard.press("Control+Alt+P");
            }

            await this.page.waitForTimeout(1500);

            console.log(
                `[${this.meetingId}] Attempted to open the People panel.`
            );
        } catch (error) {
            console.error(
                `[${this.meetingId}] Could not open People panel:`,
                error.message
            );
        }
    }

    
    
    async getParticipants() {
        if (!this.page || this.page.isClosed()) {
            return [];
        }

        try {
            const result = await this.page.evaluate(() => {
                const collected = [];
                const seen = new Set();

                const isVisible = (element) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();

                    return (
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        Number(style.opacity) !== 0 &&
                        rect.width > 0 &&
                        rect.height > 0
                    );
                };

                const addName = (rawName) => {
                    if (typeof rawName !== "string") return;

                    let name = rawName
                        .replace(/\s+/g, " ")
                        .trim()
                        .replace(/\s*\(You\)\s*$/i, "")
                        .replace(/\s*-\s*You\s*$/i, "")
                        .trim();

                    if (!name || name.length > 120) return;

                    // Reject obvious Google Meet controls and interface labels.
                    const invalidText =
                        /^(people|participants|chat|activities|meeting details|messages|more options|more actions|microphone|camera|leave call|present now|host controls|mic_off|devices|keep_outline|you)$/i;

                    if (invalidText.test(name)) return;

                    if (
                        /\b(pin .* to your main screen|you can't unmute someone else|turn on microphone|turn off microphone|turn on camera|turn off camera|backgrounds and effects|visual effects|reframe)\b/i.test(name)
                    ) {
                        return;
                    }

                    // Do not accept text that looks like a control description.
                    if (
                        /^(pin|unpin|mute|remove|more actions|turn on|turn off)\b/i.test(name)
                    ) {
                        return;
                    }

                    const key = name.toLocaleLowerCase();

                    if (!seen.has(key)) {
                        seen.add(key);
                        collected.push(name);
                    }
                };

                // Use specific participant-name elements only.
                // Never scrape generic buttons, list rows, or all aria-labels.
                const selectors = [
                    "span.zWGUib",
                    "[data-self-name]"
                ];

                for (const selector of selectors) {
                    document.querySelectorAll(selector).forEach(element => {
                        if (!isVisible(element)) return;

                        // Ignore elements that are themselves controls.
                        if (
                            element.matches("button, [role='button']") ||
                            element.closest("button, [role='button']")
                        ) {
                            return;
                        }

                        const text = (
                            element.innerText ||
                            element.textContent ||
                            ""
                        ).trim();

                        addName(text);

                        // Only use this attribute on the specific self-name selector.
                        if (selector === "[data-self-name]") {
                            addName(element.getAttribute("data-self-name") || "");
                        }
                    });
                }

                return {
                    names: collected,
                    diagnostics: {
                        title: document.title,
                        nameElements: document.querySelectorAll("span.zWGUib").length,
                        selfNameElements: document.querySelectorAll("[data-self-name]").length
                    }
                };
            });

            const names = new Map();

            for (const rawName of result.names) {
                const name = canonicalizeName(rawName);

                if (!name || isBotParticipant(name)) continue;

                const key = participantKey(name);

                if (key && !names.has(key)) {
                    names.set(key, name);
                }
            }

            const participants = [...names.values()];

            console.log(
                `[${this.meetingId}] Clean participant names (${participants.length}):`,
                participants
            );

            if (participants.length === 0) {
                console.warn(
                    `[${this.meetingId}] No participant names found. ` +
                    "Google Meet selector diagnostics:",
                    result.diagnostics
                );
            }

            return participants;
        } catch (error) {
            console.error(
                `[${this.meetingId}] Participant detection failed:`,
                error.message
            );

            return [];
        }
    }


    async pollParticipants() {
        if (this.meetingEnded) return;

        const participants = await this.getParticipants();

        if (participants.length === 0) {
            this.consecutiveEmptyPolls += 1;

            console.warn(
                `[${this.meetingId}] No participant names detected ` +
                `(${this.consecutiveEmptyPolls} consecutive poll(s)); ` +
                "preserving existing sessions."
            );

            // Do not falsely mark everyone as having left on a transient
            // extraction failure. Keep the report fresh, however.
            this.saveAttendance("active");
            return;
        }

        this.consecutiveEmptyPolls = 0;

        const now = new Date();
        const currentByKey = new Map();

        for (const rawName of participants) {
            const name = canonicalizeName(rawName);

            if (!name || isBotParticipant(name)) continue;

            const key = participantKey(name);
            if (!key) continue;

            if (!currentByKey.has(key)) {
                currentByKey.set(key, name);
            }
        }

        // Record new sessions, keyed by normalized name.
        for (const [key, participant] of currentByKey) {
            if (!this.activeParticipants.has(key)) {
                if (!this.sessions[key]) {
                    this.sessions[key] = { sessions: [] };
                    this.displayNames[key] = participant;
                } else if (!this.displayNames[key]) {
                    this.displayNames[key] = participant;
                }

                const session = {
                    join_time: now.toISOString(),
                    leave_time: null
                };

                this.sessions[key].sessions.push(session);
                this.activeParticipants.set(key, session);

                console.log(
                    `[${this.meetingId}] JOINED: ${participant} ` +
                    `${session.join_time}`
                );
            }
        }

        // Close sessions only after a successful non-empty participant
        // extraction. Empty/failed reads are handled above.
        for (const [key, session] of this.activeParticipants) {
            if (!currentByKey.has(key)) {
                session.leave_time = now.toISOString();

                console.log(
                    `[${this.meetingId}] LEFT: ` +
                    `${this.displayNames[key] || key} ${session.leave_time}`
                );

                this.activeParticipants.delete(key);
            }
        }

        this.saveAttendance("active");
    }

    getMeetingDurationSeconds() {
        if (!this.startedAt) return 0;

        const endTime = this.endedAt || new Date();

        return Math.max(
            0,
            (endTime.getTime() - this.startedAt.getTime()) / 1000
        );
    }

    getParticipantReport(key, data) {
        const durationSeconds = calculateDurationSeconds(data.sessions);
        const meetingDurationSeconds = this.getMeetingDurationSeconds();

        const attendancePercentage = meetingDurationSeconds > 0
            ? Math.min(
                100,
                durationSeconds / meetingDurationSeconds * 100
            )
            : 0;

        let status = "Tardy";

        if (attendancePercentage >= PRESENT_THRESHOLD) {
            status = "Present";
        } else if (attendancePercentage >= LOW_ATTENDANCE_THRESHOLD) {
            status = "Partially Present (Tardy)";
        }

        const firstSession = data.sessions[0];
        const lastSession = data.sessions[data.sessions.length - 1];

        return {
            name: this.displayNames[key] || key,
            email: "",
            join_time: firstSession?.join_time || null,
            leave_time: lastSession?.leave_time || null,
            duration_minutes: Number((durationSeconds / 60).toFixed(1)),
            attendance_percentage: Number(attendancePercentage.toFixed(1)),
            status,
            sessions: data.sessions
        };
    }

    buildParticipants() {
        return Object.entries(this.sessions).map(([key, data]) =>
            this.getParticipantReport(key, data)
        );
    }

    createReport(status = "active", endTime = null) {
        if (endTime) {
            this.endedAt = endTime;
        }

        const participants = this.buildParticipants();

        const presentAttendees = participants.filter(
            participant =>
                participant.status === "Present" ||
                participant.status === "Partially Present"
        );

        const participantKeys = new Set(
            participants.map(participant => participantKey(participant.name))
        );

        const absentAttendees = this.expectedAttendees.filter(
            expected => !participantKeys.has(participantKey(expected))
        );

        const totalExpected = this.expectedAttendees.length;
        const presentCount = presentAttendees.length;
        const absentCount = absentAttendees.length;

        // Without an expected roster, overall attendance is unknown;
        // do not substitute the observed participant count as the roster.
        const attendanceRate = totalExpected > 0
            ? Number((presentCount / totalExpected * 100).toFixed(1))
            : null;

        const absentRate = totalExpected > 0
            ? Number((absentCount / totalExpected * 100).toFixed(1))
            : null;

        const lowAttendanceCount = participants.filter(
            participant => participant.status === "Low Attendance"
        ).length;

        const meetingDurationSeconds = this.getMeetingDurationSeconds();

        return {
            meeting_id: this.meetingId,
            meeting_title: this.meetingTitle,
            date: this.startedAt
                ? this.startedAt.toISOString().split("T")[0]
                : null,
            start_time: this.startedAt
                ? this.startedAt.toISOString()
                : null,
            end_time: this.endedAt
                ? this.endedAt.toISOString()
                : null,
            duration_minutes: Number((meetingDurationSeconds / 60).toFixed(1)),
            total_participants: participants.length,
            low_attendance_count: lowAttendanceCount,
            expected_attendees: this.expectedAttendees,
            present_attendees: presentAttendees.map(p => p.name),
            absent_attendees: absentAttendees,
            total_expected: totalExpected,
            present_count: presentCount,
            absent_count: absentCount,
            attendance_rate: attendanceRate,
            absent_rate: absentRate,
            status,
            last_updated: new Date().toISOString(),
            participants
        };
    }

    saveAttendance(status = "active") {
        const report = this.createReport(status);

        fs.writeFileSync(
            this.activeFile,
            JSON.stringify(report, null, 2)
        );

        if (this.reportFile) {
            fs.writeFileSync(
                this.reportFile,
                JSON.stringify(report, null, 2)
            );
        }
    }

    async finalize(status = "completed") {
        if (this.meetingEnded) {
            return this.createReport(status, this.endedAt);
        }

        this.meetingEnded = true;
        this.polling = false;
        this.endedAt = new Date();

        for (const [key, session] of this.activeParticipants) {
            if (!session.leave_time) {
                session.leave_time = this.endedAt.toISOString();
            }

            console.log(
                `[${this.meetingId}] LEFT: ` +
                `${this.displayNames[key] || key} ${session.leave_time}`
            );
        }

        this.activeParticipants.clear();
        this.status = status;

        const report = this.createReport(status, this.endedAt);

        // Write the final historical report, then remove the active file.
        if (this.reportFile) {
            fs.writeFileSync(
                this.reportFile,
                JSON.stringify(report, null, 2)
            );
        }

        if (fs.existsSync(this.activeFile)) {
            fs.unlinkSync(this.activeFile);
        }

        return report;
    }
}

async function main() {
    const meetLink = process.argv[2];

    if (!meetLink) {
        console.log("Please provide a Google Meet link.");
        console.log(
            "Example: node meeting-bot/bot.js https://meet.google.com/abc-defg-hij"
        );
        return;
    }

    const meetingId = getMeetingId(meetLink);

    if (!meetingId) {
        console.log("Invalid Google Meet link.");
        return;
    }

    const context = await createBrowserContext();
    const page = await context.newPage();

    const tracker = new MeetingTracker({
        page,
        context,
        meetLink,
        meetingId,
        meetingTitle: meetingId,
        expectedAttendees: []
    });

    try {
        await tracker.prepareMeeting();
        tracker.polling = true;

        while (!tracker.meetingEnded) {
            if (tracker.page.isClosed()) break;

            await tracker.pollParticipants();
            await tracker.page.waitForTimeout(POLL_INTERVAL_MS);
        }
    } catch (error) {
        console.error("Bot error:", error);
    } finally {
        await tracker.finalize("completed");

        if (!page.isClosed()) {
            await page.close();
        }

        await context.close();
    }
}

module.exports = {
    MeetingTracker,
    createBrowserContext,
    getMeetingId
};

if (require.main === module) {
    main();
}
