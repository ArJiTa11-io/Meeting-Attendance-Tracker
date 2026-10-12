const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BROWSER_PROFILE = path.join(
    __dirname,
    "browser-profile"
);

const OUTPUT_DIRECTORY = path.join(
    __dirname,
    "output"
);

const ACTIVE_DIRECTORY = path.join(
    OUTPUT_DIRECTORY,
    "active"
);

const REPORTS_DIRECTORY = path.join(
    OUTPUT_DIRECTORY,
    "reports"
);

fs.mkdirSync(OUTPUT_DIRECTORY, {
    recursive: true
});

fs.mkdirSync(ACTIVE_DIRECTORY, {
    recursive: true
});

fs.mkdirSync(REPORTS_DIRECTORY, {
    recursive: true
});

function getMeetingId(meetLink) {
    if (!meetLink) {
        return null;
    }

    const match = String(meetLink).match(
        /meet\.google\.com\/([^/?#]+)/
    );

    return match ? match[1] : null;
}

function calculateDurationSeconds(
    sessions
) {
    return sessions.reduce(
        (total, session) => {
            if (!session.join_time) {
                return total;
            }

            const joinTime =
                new Date(
                    session.join_time
                ).getTime();

            const leaveTime =
                session.leave_time
                    ? new Date(
                          session.leave_time
                      ).getTime()
                    : Date.now();

            return (
                total +
                Math.max(
                    0,
                    (leaveTime -
                        joinTime) /
                        1000
                )
            );
        },
        0
    );
}

async function createBrowserContext() {
    console.log(
        "Starting authenticated Chrome context..."
    );

    const context =
        await chromium.launchPersistentContext(
            BROWSER_PROFILE,
            {
                headless: false,
                channel: "chrome"
            }
        );

    await context.grantPermissions(
        [
            "camera",
            "microphone"
        ],
        {
            origin:
                "https://meet.google.com"
        }
    );

    console.log(
        "Camera and microphone permissions granted."
    );

    console.log(
        "Browser context ready."
    );

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

        this.meetingId =
            meetingId ||
            getMeetingId(meetLink);

        this.meetingTitle =
            meetingTitle ||
            this.meetingId;

        this.expectedAttendees =
            Array.isArray(
                expectedAttendees
            )
                ? expectedAttendees
                : [];

        this.startedAt = null;
        this.endedAt = null;

        this.sessions = {};
        this.activeParticipants =
            new Map();

        this.polling = false;
        this.pollingPromise = null;
        this.meetingEnded = false;

        this.status = "starting";

        this.activeFile = path.join(
            ACTIVE_DIRECTORY,
            `${this.meetingId}.json`
        );

        this.reportFile = null;
    }

    async prepareMeeting() {
        if (!this.meetingId) {
            throw new Error(
                "Invalid Google Meet link."
            );
        }

        console.log(
            `[${this.meetingId}] Opening Google Meet...`
        );

        await this.page.goto(
            this.meetLink,
            {
                waitUntil:
                    "domcontentloaded",
                timeout: 30000
            }
        );

        console.log(
            `[${this.meetingId}] Meet opened.`
        );

        await this.page.waitForTimeout(
            5000
        );

        await this.disableMicrophone();

        await this.disableCamera();

        console.log(
            `[${this.meetingId}] Looking for Join now button...`
        );

        const joinButton =
            this.page.getByRole(
                "button",
                {
                    name: /join now/i
                }
            );

        await joinButton.waitFor({
            state: "visible",
            timeout: 15000
        });

        await joinButton.click();

        console.log(
            `[${this.meetingId}] Bot joined the meeting.`
        );

        await this.page.waitForTimeout(
            5000
        );

        await this.openPeoplePanel();

        this.startedAt =
            new Date();

        this.status = "active";

        const timestamp =
            this.startedAt
                .toISOString()
                .replace(
                    /[:.]/g,
                    "-"
                );

        this.reportFile =
            path.join(
                REPORTS_DIRECTORY,
                `${this.meetingId}_${timestamp}.json`
            );

        this.saveAttendance(
            "active"
        );
    }

    async disableMicrophone() {
        try {
            const micButton =
                this.page.getByRole(
                    "button",
                    {
                        name: "Turn off microphone"
                    }
                );

            if (
                await micButton.isVisible({
                    timeout: 5000
                })
            ) {
                await micButton.click();
            }
        } catch (error) {}
    }

    async disableCamera() {
        try {
            const cameraButton =
                this.page.getByRole(
                    "button",
                    {
                        name: "Turn off camera"
                    }
                );

            if (
                await cameraButton.isVisible({
                    timeout: 5000
                })
            ) {
                await cameraButton.click();
            }
        } catch (error) {}
    }

    async openPeoplePanel() {
        try {
            await this.page.keyboard.press(
                "Control+Alt+P"
            );

            await this.page.waitForTimeout(
                3000
            );

            console.log(
                `[${this.meetingId}] People panel opened.`
            );
        } catch (error) {
            console.log(
                `[${this.meetingId}] Could not open People panel.`
            );
        }
    }

    async getParticipants() {
        if (
            !this.page ||
            this.page.isClosed()
        ) {
            return [];
        }

        try {
            return await this.page
                .locator("span.zWGUib")
                .evaluateAll(
                    elements =>
                        elements
                            .map(
                                element =>
                                    element
                                        .parentElement
                                        ?.innerText
                                        ?.trim()
                            )
                            .filter(Boolean)
                );
        } catch (error) {
            return [];
        }
    }

    async pollParticipants() {
        const participants =
            await this.getParticipants();

        const currentParticipants =
            new Set(
                participants
            );

        const now =
            new Date();

        for (
            const participant of
            currentParticipants
        ) {
            if (
                participant.includes(
                    "(You)"
                ) ||
                participant ===
                    "Adhrav Rai"
            ) {
                continue;
            }

            if (
                !this.activeParticipants.has(
                    participant
                )
            ) {
                if (
                    !this.sessions[
                        participant
                    ]
                ) {
                    this.sessions[
                        participant
                    ] = {
                        sessions: []
                    };
                }

                const session = {
                    join_time:
                        now.toISOString(),
                    leave_time: null
                };

                this.sessions[
                    participant
                ].sessions.push(
                    session
                );

                this.activeParticipants.set(
                    participant,
                    session
                );

                console.log(
                    `[${this.meetingId}] JOINED:`,
                    participant,
                    session.join_time
                );
            }
        }

        for (
            const [
                participant,
                session
            ] of this.activeParticipants
        ) {
            if (
                !currentParticipants.has(
                    participant
                )
            ) {
                session.leave_time =
                    now.toISOString();

                console.log(
                    `[${this.meetingId}] LEFT:`,
                    participant,
                    session.leave_time
                );

                this.activeParticipants.delete(
                    participant
                );
            }
        }

        this.saveAttendance(
            "active"
        );
    }

    getMeetingDurationSeconds() {
        if (!this.startedAt) {
            return 0;
        }

        const endTime =
            this.endedAt ||
            new Date();

        return Math.max(
            0,
            (
                endTime.getTime() -
                this.startedAt.getTime()
            ) / 1000
        );
    }

    getParticipantReport(
        participant,
        data
    ) {
        const durationSeconds =
            calculateDurationSeconds(
                data.sessions
            );

        const meetingDurationSeconds =
            this.getMeetingDurationSeconds();

        const attendancePercentage =
            meetingDurationSeconds > 0
                ? Math.min(
                      100,
                      (
                          durationSeconds /
                          meetingDurationSeconds
                      ) *
                          100
                  )
                : 0;

        let status =
            "Low Attendance";

        if (
            attendancePercentage >=
            90
        ) {
            status = "Present";
        } else if (
            attendancePercentage >=
            75
        ) {
            status =
                "Partially Present";
        }

        const firstSession =
            data.sessions[0];

        const lastSession =
            data.sessions[
                data.sessions.length - 1
            ];

        return {
            name: participant,
            email: "",
            join_time:
                firstSession?.join_time ||
                null,
            leave_time:
                lastSession?.leave_time ||
                null,
            duration_minutes:
                Number(
                    (
                        durationSeconds /
                        60
                    ).toFixed(1)
                ),
            attendance_percentage:
                Number(
                    attendancePercentage.toFixed(
                        1
                    )
                ),
            status,
            sessions:
                data.sessions
        };
    }

    buildParticipants() {
        return Object.entries(
            this.sessions
        ).map(
            ([
                participant,
                data
            ]) =>
                this.getParticipantReport(
                    participant,
                    data
                )
        );
    }

    createReport(
        status = "active",
        endTime = null
    ) {
        if (
            endTime
        ) {
            this.endedAt =
                endTime;
        }

        const participants =
            this.buildParticipants();

        const meetingDurationSeconds =
            this.getMeetingDurationSeconds();

        const presentAttendees =
            participants.filter(
                participant =>
                    participant.status ===
                        "Present" ||
                    participant.status ===
                        "Partially Present"
            );

        const absentAttendees =
            this.expectedAttendees.filter(
                expected =>
                    !participants.some(
                        participant =>
                            participant.name ===
                            expected
                    )
            );

        const totalExpected =
            this.expectedAttendees.length;

        const presentCount =
            presentAttendees.length;

        const absentCount =
            absentAttendees.length;

        const attendanceRate =
            totalExpected > 0
                ? Number(
                      (
                          (presentCount /
                              totalExpected) *
                          100
                      ).toFixed(1)
                  )
                : null;

        const absentRate =
            totalExpected > 0
                ? Number(
                      (
                          (absentCount /
                              totalExpected) *
                          100
                      ).toFixed(1)
                  )
                : null;

        const lowAttendanceCount =
            participants.filter(
                participant =>
                    participant.status ===
                    "Low Attendance"
            ).length;

        return {
            meeting_id:
                this.meetingId,

            meeting_title:
                this.meetingTitle,

            date:
                this.startedAt
                    ? this.startedAt
                          .toISOString()
                          .split("T")[0]
                    : null,

            start_time:
                this.startedAt
                    ? this.startedAt.toISOString()
                    : null,

            end_time:
                this.endedAt
                    ? this.endedAt.toISOString()
                    : null,

            duration_minutes:
                Number(
                    (
                        meetingDurationSeconds /
                        60
                    ).toFixed(1)
                ),

            total_participants:
                participants.length,

            low_attendance_count:
                lowAttendanceCount,

            expected_attendees:
                this.expectedAttendees,

            present_attendees:
                presentAttendees.map(
                    participant =>
                        participant.name
                ),

            absent_attendees:
                absentAttendees,

            total_expected:
                totalExpected,

            present_count:
                presentCount,

            absent_count:
                absentCount,

            attendance_rate:
                attendanceRate,

            absent_rate:
                absentRate,

            status,

            last_updated:
                new Date().toISOString(),

            participants
        };
    }

    saveAttendance(
        status = "active"
    ) {
        const report =
            this.createReport(
                status
            );

        fs.writeFileSync(
            this.activeFile,
            JSON.stringify(
                report,
                null,
                2
            )
        );

        if (
            this.reportFile
        ) {
            fs.writeFileSync(
                this.reportFile,
                JSON.stringify(
                    report,
                    null,
                    2
                )
            );
        }
    }

    async finalize(
        status = "completed"
    ) {
        if (
            this.meetingEnded
        ) {
            return this.createReport(
                status,
                this.endedAt
            );
        }

        this.meetingEnded =
            true;

        this.polling =
            false;

        this.endedAt =
            new Date();

        for (
            const [
                participant,
                session
            ] of this.activeParticipants
        ) {
            if (
                !session.leave_time
            ) {
                session.leave_time =
                    this.endedAt.toISOString();
            }

            console.log(
                `[${this.meetingId}] LEFT:`,
                participant,
                session.leave_time
            );
        }

        this.activeParticipants.clear();

        this.status =
            status;

        const report =
            this.createReport(
                status,
                this.endedAt
            );

        fs.writeFileSync(
            this.activeFile,
            JSON.stringify(
                report,
                null,
                2
            )
        );

        if (
            this.reportFile
        ) {
            fs.writeFileSync(
                this.reportFile,
                JSON.stringify(
                    report,
                    null,
                    2
                )
            );
        }

        if (
            fs.existsSync(
                this.activeFile
            )
        ) {
            fs.unlinkSync(
                this.activeFile
            );
        }

        return report;
    }
}

async function main() {
    const meetLink =
        process.argv[2];

    if (!meetLink) {
        console.log(
            "Please provide a Google Meet link."
        );

        console.log(
            "Example: node meeting-bot/bot.js https://meet.google.com/abc-defg-hij"
        );

        return;
    }

    const meetingId =
        getMeetingId(
            meetLink
        );

    if (!meetingId) {
        console.log(
            "Invalid Google Meet link."
        );

        return;
    }

    const context =
        await createBrowserContext();

    const page =
        await context.newPage();

    const tracker =
        new MeetingTracker({
            page,
            context,
            meetLink,
            meetingId,
            meetingTitle:
                meetingId,
            expectedAttendees: []
        });

    try {
        await tracker.prepareMeeting();

        tracker.polling =
            true;

        while (
            !tracker.meetingEnded
        ) {
            if (
                tracker.page.isClosed()
            ) {
                break;
            }

            await tracker.pollParticipants();

            await tracker.page.waitForTimeout(
                10000
            );
        }
    } catch (error) {
        console.error(
            "Bot error:",
            error
        );
    } finally {
        await tracker.finalize(
            "completed"
        );

        if (
            !page.isClosed()
        ) {
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

if (
    require.main === module
) {
    main();
}