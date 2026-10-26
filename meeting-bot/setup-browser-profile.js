
const { chromium } = require("playwright");
const path = require("path");

const BROWSER_PROFILE = path.join(__dirname, "browser-profile");

async function setupBrowserProfile() {
    console.log("Opening the dedicated Attendance Bot Chrome profile...");

    const context = await chromium.launchPersistentContext(
        BROWSER_PROFILE,
        {
            headless: false,
            channel: "chrome"
        }
    );

    const page = context.pages()[0] || await context.newPage();

    await page.goto("https://meet.google.com/");

    console.log("\n1. Sign in to your Google account in the opened browser.");
    console.log("2. Complete any verification Google requests.");
    console.log("3. Once signed in, close this browser window.");
    console.log("Your profile will be saved for future bot runs.");

    context.on("close", () => {
        console.log("Setup browser closed.");
    });

    await new Promise((resolve) => {
        context.once("close", resolve);
    });
}

setupBrowserProfile().catch((error) => {
    console.error("Browser profile setup failed:", error);
    process.exitCode = 1;
});
