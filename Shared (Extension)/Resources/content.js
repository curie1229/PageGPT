function getStructuredContent() {
    let content = [];
    // Get main content from known tags
    const contentSelectors = ['article', 'main', '.main-content', 'mw-content-text', 'p'];

    contentSelectors.forEach((selector) => {
        const elements = document.querySelectorAll(selector);
        elements.forEach((el) => {
            // Skip if the element is likely to be non-content
            if (el.matches('nav, .nav, footer, .footer, .advertisement')) {
                return;
            }
            // Add each paragraph as a separate item in the array
            content.push(el.innerText);
        });
    });

    // Clean up whitespace for each paragraph
    content = content.map(paragraph => paragraph.replace(/\s+/g, ' ').trim());

    return content;
}

function getPageTitle() {
    // Check for the title tag first
    let title = document.title;

    // Fallback to other possible selectors if the title is not descriptive
    if (!title || title === '') {
        const selectors = ['h1', '.article-title', '.post-title', '#page-title', 'header h1'];
        for (let selector of selectors) {
            const element = document.querySelector(selector);
            if (element) {
                title = element.innerText.trim();
                break;
            }
        }
    }
    return title;
}

browser.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.message === "getPageContent") {
        const pageContent = getStructuredContent();
        const pageTitle = getPageTitle(); // Call the new function to get the page title
        sendResponse({ pageContent: pageContent, pageTitle: pageTitle });
    }
    return true; // This is necessary to indicate that the response is asynchronous in some browsers
});
