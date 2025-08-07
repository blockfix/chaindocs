 codex/add-futuristic-glass-chat-ui
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
=======
const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const chat = document.getElementById('chat');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  // Append user message
  appendMessage('user', text);
  input.value = '';

  // Placeholder for assistant response
  const assistantEl = appendMessage('assistant', '');

  // Stream response from server
  const response = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    assistantEl.innerHTML = marked.parse(buffer);
    chat.scrollTop = chat.scrollHeight;
  }
});

function appendMessage(role, content) {
  const wrapper = document.createElement('div');
  if (role === 'user') {
    wrapper.className = 'text-right';
  }
  const bubble = document.createElement('div');
  if (role === 'user') {
    bubble.className = 'inline-block bg-indigo-600 text-white px-4 py-2 rounded-xl';
    bubble.textContent = content;
  } else {
    bubble.className = 'prose prose-invert';
    bubble.innerHTML = content;
  }
  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
 main
}
