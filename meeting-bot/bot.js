const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

async function main() {
    const meetLink = process.argv[2];

    if (!meetLink) {
        console.log("Please provide a Google Meet link.");
        console.log("Example: node meeting-bot/bot.js https://meet.google.com/abc-defg-hij");
        return;
    }

    const meetingId = meetLink
        .split("meet.google.com/")[1]
        ?.split(/[/?#]/)[0];

    const context = await chromium.launchPersistentContext(
        "./meeting-bot/browser-profile",
        {
            headless: false,
            channel: "chrome"
        }
    );

    const page = await context.newPage();

    await page.goto(meetLink);

    console.log("Meet opened.");

    await page.waitForTimeout(5000);

    try {
        const micButton = page.getByRole("button", {
            name: "Turn off microphone"
        });

        if (await micButton.isVisible()) {
            await micButton.click();
        }
    } catch (error) {}

    try {
        const cameraButton = page.getByRole("button", {
            name: "Turn off camera"
        });

        if (await cameraButton.isVisible()) {
            await cameraButton.click();
        }
    } catch (error) {}

    const joinButton = page.getByRole("button", {
        name: /join now/i
    });

    await joinButton.waitFor({
        state: "visible",
        timeout: 15000
    });

    await joinButton.click();

    console.log("Bot joined the meeting.");

    const meetingPage = context.pages().find(
        currentPage => currentPage.url().includes("meet.google.com")
    );

    if (!meetingPage) {
        console.log("Meeting page not found.");
        return;
    }

    await meetingPage.waitForTimeout(5000);

    await meetingPage.keyboard.press("Control+Alt+P");

    await meetingPage.waitForTimeout(3000);

    console.log("People panel opened.");

    const outputDirectory = path.join(
        __dirname,
        "output"
    );

    const outputFile = path.join(
        outputDirectory,
        "attendance.json"
    );

    fs.mkdirSync(outputDirectory, {
        recursive: true
    });

    const sessions = {};
    const activeParticipants = new Map();

    function saveAttendance(status = "active") {
        const attendanceData = {
            meeting_id: meetingId,
            status: status,
            last_updated: new Date().toISOString(),
            participants: sessions
        };

        fs.writeFileSync(
            outputFile,
            JSON.stringify(attendanceData, null, 2)
        );
    }

    saveAttendance();

    while (true) {
        const participants = await meetingPage
            .locator("span.zWGUib")
            .evaluateAll(elements =>
                elements
                    .map(element => element.parentElement?.innerText?.trim())
                    .filter(Boolean)
            );

        const currentParticipants = new Set(participants);

        const now = new Date();

        for (const participant of currentParticipants) {
            if (
                participant.includes("(You)") ||
                participant === "Adhrav Rai"
            ) {
                continue;
            }

            if (!activeParticipants.has(participant)) {
                if (!sessions[participant]) {
                    sessions[participant] = {
                        sessions: []
                    };
                }

                const session = {
                    join_time: now.toISOString(),
                    leave_time: null
                };

                sessions[participant].sessions.push(session);
                activeParticipants.set(participant, session);

                console.log(
                    "JOINED:",
                    participant,
                    session.join_time
                );

                saveAttendance();
            }
        }

        for (const [participant, session] of activeParticipants) {
            if (!currentParticipants.has(participant)) {
                session.leave_time = now.toISOString();

                console.log(
                    "LEFT:",
                    participant,
                    session.leave_time
                );

                activeParticipants.delete(participant);

                saveAttendance();
            }
        }

        saveAttendance();

        console.log("\nCurrent participants:");

        for (const participant of currentParticipants) {
            console.log("-", participant);
        }

        console.log("\nSession data:");
        console.log(JSON.stringify(sessions, null, 2));

        await meetingPage.waitForTimeout(10000);
    }
}

main();