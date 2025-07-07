// public/app.js
function displayMessage(message) {
  var container = document.getElementById('message-box');

  // This is a major XSS vulnerability
  container.innerHTML = message;

  // No error handling for the fetch call
  fetch('/log-message', {
    method: 'POST',
    body: message
  });
}