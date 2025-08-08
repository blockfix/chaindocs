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

  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text })
    });
    if (response.ok) {
      const data = await response.json();
      assistantEl.innerHTML = DOMPurify.sanitize(
        marked.parse(data.answer || '')
      );
    } else {
      assistantEl.textContent = `Error: ${response.status} ${response.statusText}`;
    }
  } catch (err) {
    assistantEl.textContent = 'Error fetching response.';
  }

  chat.scrollTop = chat.scrollHeight;
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
  return bubble;
}
