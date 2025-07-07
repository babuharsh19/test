// public/app.js
async function displayMessage(message) {
  const messageContainer = document.getElementById('message-box');
  if (messageContainer) {
    // Using textContent is safe against XSS attacks
    messageContainer.textContent = message;
  }
}