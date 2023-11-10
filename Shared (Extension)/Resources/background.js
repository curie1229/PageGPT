// background.js

// Event listener to handle messages from the popup or content script
browser.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  if (message.message === "checkExecutionState") {
    const executed = sessionExists();
    sendResponse({ executed });
  } else if (message.message === "setExecutionState") {
    setSessionFlag();
  }
});

function sessionExists() {
  // Check if the session flag exists in session storage
  return !!sessionStorage.getItem("codeExecuted");
}

function setSessionFlag() {
  // Set the session flag in session storage to indicate that the code has been executed
  sessionStorage.setItem("codeExecuted", "true");
}
