document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chat-input');
    const chatBox = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');

    // Load previous messages from localStorage and display them
    loadMessages();

    sendBtn.addEventListener('click', function() {
        sendMessage(chatInput.value);
    });

    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
          sendMessage(chatInput.value);
        }
    });

    function loadMessages() {
        const messages = JSON.parse(localStorage.getItem('chatMessages')) || [];
        messages.forEach((messageObj) => {
            displayMessage(messageObj.message, messageObj.type);
        });
    }

    function saveMessage(message, type) {
        const messages = JSON.parse(localStorage.getItem('chatMessages')) || [];
        messages.push({ message, type });
        localStorage.setItem('chatMessages', JSON.stringify(messages));
    }

    function displayMessage(messageText, type) {
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';

        const messageElement = document.createElement('div');
        messageElement.textContent = messageText;
        messageElement.className = type === 'user' ? 'user-message' : 'bot-message';
        messageContainer.appendChild(messageElement);

        chatBox.appendChild(messageContainer);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function sendMessage(message, callback) {
        if (message.trim() === '') return;

        displayMessage(message, 'user');
        saveMessage(message, 'user');
        chatInput.value = '';

        browser.tabs.query({ active: true, currentWindow: true }, function (tabs) {
            var activeTab = tabs[0];
            browser.tabs.sendMessage(activeTab.id, { message: "getPageContent" }, function (response) {
                if (response && response.pageContent) {
                    const payload = {
                        userMessage: message,
                        pageContent: response.pageContent,
                        pageTitle: response.pageTitle
                    };
                    sendPostRequest(payload, "/question", function(responseMessage) {
                        displayMessage(responseMessage, 'bot');
                        saveMessage(responseMessage, 'bot');
                        if (callback) {
                            callback(response.pageContent);
                        }
                    });
                }
            });
        });
    }

    function sendPostRequest(payload, path, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://localhost:8080" + path, true);
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                var status = xhr.status;
                if (status === 0 || (status >= 200 && status < 400)) {
                    var botResponse = JSON.parse(xhr.responseText);
                    callback(botResponse.response);
                } else {
                    console.error(xhr.statusText);
                }
            }
        };
        xhr.send(JSON.stringify(payload));
    }
});
