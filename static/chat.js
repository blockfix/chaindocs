function sendMessage() {
  const input = document.getElementById('input');
  const message = input.value.trim();
  if (!message) return;

  const messages = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'message';
  div.textContent = message;
  messages.appendChild(div);
  input.value = '';
  messages.scrollTop = messages.scrollHeight;
}
