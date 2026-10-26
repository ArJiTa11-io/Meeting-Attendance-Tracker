const { chromium } = require("playwright");
const path = require("path");

const BROWSER_PROFILE = path.join(
    __dirname,
    "browser-profile-test"
);

(async () => {
    const context = await chromium.launchPersistentContext(
        BROWSER_PROFILE,
        {
            headless: false,
            channel: "chrome",
            chromiumSandbox: true
        }
    );

    const page = context.pages()[0] || await context.newPage();

    await page.goto("https://meet.google.com/");

    console.log("Check whether Google Meet recognizes your login.");
    console.log("Press Ctrl+C in the terminal when finished.");
})();