const http = require("http");

const {
    MeetingTracker,
    createBrowserContext
} = require("./bot");

const PORT = 8765;

const meetings = new Map();

let context = null;
let contextStarting = null;
let shuttingDown = false;

async function getBrowserContext() {
    if (
        context &&
        !context.isClosed()
    ) {
        return context;
    }

    if (contextStarting) {
        return contextStarting;
    }

    contextStarting =
        (async () => {
            console.log(
                "Starting authenticated Chrome context..."
            );

            const newContext =
                await createBrowserContext();

            newContext.on(
                "close",
                () => {
                    console.log(
                        "Browser context closed."
                    );

                    if (
                        context === newContext
                    ) {
                        context = null;
                    }
                }
            );

            context = newContext;

            console.log(
                "Browser context ready."
            );

            return newContext;
        })();

    try {
        return await contextStarting;
    } finally {
        contextStarting = null;
    }
}

function sendJson(
    response,
    statusCode,
    data
) {
    response.writeHead(
        statusCode,
        {
            "Content-Type":
                "application/json",
            "Access-Control-Allow-Origin":
                "*",
            "Access-Control-Allow-Methods":
                "GET,POST,DELETE,OPTIONS",
            "Access-Control-Allow-Headers":
                "Content-Type"
        }
    );

    response.end(
        JSON.stringify(data)
    );
}

function readBody(request) {
    return new Promise(
        (resolve, reject) => {
            let body = "";

            request.on(
                "data",
                chunk => {
                    body += chunk;
                }
            );

            request.on(
                "end",
                () => {
                    if (!body) {
                        resolve({});
                        return;
                    }

                    try {
                        resolve(
                            JSON.parse(body)
                        );
                    } catch (error) {
                        reject(
                            new Error(
                                "Invalid JSON body."
                            )
                        );
                    }
                }
            );

            request.on(
                "error",
                reject
            );
        }
    );
}

function getMeetingReport(
    tracker
) {
    return tracker.createReport(
        tracker.meetingEnded
            ? "completed"
            : "active",
        tracker.meetingEnded
            ? new Date()
            : null
    );
}

async function startMeeting(
    data
) {
    const meetLink =
        String(
            data.meet_link || ""
        ).trim();

    const meetingTitle =
        String(
            data.meeting_title || ""
        ).trim();

    const expectedAttendees =
        Array.isArray(
            data.expected_attendees
        )
            ? data.expected_attendees
                .map(
                    name =>
                        String(name).trim()
                )
                .filter(Boolean)
            : [];

    if (!meetLink) {
        throw new Error(
            "Google Meet link is required."
        );
    }

    if (
        !meetLink.startsWith(
            "https://meet.google.com/"
        )
    ) {
        throw new Error(
            "Invalid Google Meet link."
        );
    }

    const meetingId =
        meetLink
            .split(
                "meet.google.com/"
            )[1]
            ?.split(/[/?#]/)[0];

    if (!meetingId) {
        throw new Error(
            "Could not extract meeting ID."
        );
    }

    if (
        meetings.has(meetingId)
    ) {
        throw new Error(
            "This meeting is already being tracked."
        );
    }

    const browser =
        await getBrowserContext();

    let page;

    try {
        page =
            await browser.newPage();
    } catch (error) {
        console.log(
            "Browser context became unavailable."
        );

        context = null;

        const newBrowser =
            await getBrowserContext();

        page =
            await newBrowser.newPage();
    }

    const tracker =
        new MeetingTracker({
            page,
            context:
                context,
            meetLink,
            meetingId,
            meetingTitle,
            expectedAttendees
        });

    meetings.set(
        meetingId,
        tracker
    );

    try {
        await tracker.prepareMeeting();

        tracker.polling = true;

        tracker.pollingPromise =
            (async () => {
                while (
                    !tracker.meetingEnded
                ) {
                    if (
                        tracker.page.isClosed()
                    ) {
                        await tracker.finalize(
                            "completed"
                        );

                        meetings.delete(
                            meetingId
                        );

                        break;
                    }

                    await tracker.pollParticipants();

                    await tracker.page.waitForTimeout(
                        10000
                    );
                }
            })().catch(
                async error => {
                    console.error(
                        `[${meetingId}] Tracking error:`,
                        error
                    );

                    try {
                        await tracker.finalize(
                            "completed"
                        );
                    } catch (
                        finalizeError
                    ) {}

                    meetings.delete(
                        meetingId
                    );
                }
            );

        return getMeetingReport(
            tracker
        );
    } catch (error) {
        meetings.delete(
            meetingId
        );

        try {
            if (
                page &&
                !page.isClosed()
            ) {
                await page.close();
            }
        } catch (closeError) {}

        throw error;
    }
}

async function stopMeeting(
    meetingId
) {
    const tracker =
        meetings.get(
            meetingId
        );

    if (!tracker) {
        throw new Error(
            "Meeting is not active."
        );
    }

    const report =
        await tracker.finalize(
            "completed"
        );

    try {
        if (
            !tracker.page.isClosed()
        ) {
            await tracker.page.close();
        }
    } catch (error) {}

    meetings.delete(
        meetingId
    );

    return report;
}

async function handleRequest(
    request,
    response
) {
    const url =
        new URL(
            request.url,
            `http://127.0.0.1:${PORT}`
        );

    if (
        request.method === "OPTIONS"
    ) {
        response.writeHead(
            204,
            {
                "Access-Control-Allow-Origin":
                    "*",
                "Access-Control-Allow-Methods":
                    "GET,POST,DELETE,OPTIONS",
                "Access-Control-Allow-Headers":
                    "Content-Type"
            }
        );

        response.end();

        return;
    }

    if (
        request.method === "GET" &&
        url.pathname === "/health"
    ) {
        sendJson(
            response,
            200,
            {
                status: "ok",
                browser_context:
                    Boolean(
                        context &&
                        !context.isClosed()
                    ),
                active_meetings:
                    meetings.size
            }
        );

        return;
    }

    if (
        request.method === "GET" &&
        url.pathname === "/meetings"
    ) {
        const reports =
            Array.from(
                meetings.values()
            ).map(
                tracker =>
                    getMeetingReport(
                        tracker
                    )
            );

        sendJson(
            response,
            200,
            reports
        );

        return;
    }

    if (
        request.method === "POST" &&
        url.pathname === "/meetings"
    ) {
        try {
            const data =
                await readBody(
                    request
                );

            const report =
                await startMeeting(
                    data
                );

            sendJson(
                response,
                201,
                report
            );
        } catch (error) {
            console.error(
                "Could not start meeting:",
                error
            );

            sendJson(
                response,
                400,
                {
                    error:
                        error.message
                }
            );
        }

        return;
    }

    const meetingMatch =
        url.pathname.match(
            /^\/meetings\/([^/]+)$/
        );

    if (
        meetingMatch &&
        request.method === "GET"
    ) {
        const meetingId =
            decodeURIComponent(
                meetingMatch[1]
            );

        const tracker =
            meetings.get(
                meetingId
            );

        if (!tracker) {
            sendJson(
                response,
                404,
                {
                    error:
                        "Meeting not found."
                }
            );

            return;
        }

        sendJson(
            response,
            200,
            getMeetingReport(
                tracker
            )
        );

        return;
    }

    if (
        meetingMatch &&
        request.method === "DELETE"
    ) {
        const meetingId =
            decodeURIComponent(
                meetingMatch[1]
            );

        try {
            const report =
                await stopMeeting(
                    meetingId
                );

            sendJson(
                response,
                200,
                report
            );
        } catch (error) {
            sendJson(
                response,
                404,
                {
                    error:
                        error.message
                }
            );
        }

        return;
    }

    sendJson(
        response,
        404,
        {
            error:
                "Endpoint not found."
        }
    );
}

async function shutdown() {
    if (shuttingDown) {
        return;
    }

    shuttingDown = true;

    console.log(
        "\nStopping meeting manager..."
    );

    for (
        const [
            meetingId,
            tracker
        ] of meetings
    ) {
        try {
            console.log(
                `Finalizing ${meetingId}...`
            );

            await tracker.finalize(
                "completed"
            );

            if (
                !tracker.page.isClosed()
            ) {
                await tracker.page.close();
            }
        } catch (error) {
            console.error(
                `Could not finalize ${meetingId}:`,
                error.message
            );
        }
    }

    meetings.clear();

    if (context) {
        try {
            await context.close();
        } catch (error) {}
    }

    context = null;

    process.exit(0);
}

const server =
    http.createServer(
        handleRequest
    );

server.listen(
    PORT,
    "127.0.0.1",
    () => {
        console.log(
            `Meeting manager running on http://127.0.0.1:${PORT}`
        );
    }
);

process.on(
    "SIGINT",
    shutdown
);

process.on(
    "SIGTERM",
    shutdown
);