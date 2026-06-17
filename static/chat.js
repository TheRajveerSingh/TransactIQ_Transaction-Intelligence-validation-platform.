// ── TransactIQ Chat Assistant ──

let chatOpen = false;
let pendingQuestion = null;
let lastQueryRows = [];
let lastQueryCols = [];

function initChat() {
  const msgs = document.getElementById('chat-messages');
  msgs.innerHTML = '';
  addBotMessage("Hi! I'm your Data Assistant. Ask me anything about your dataset — like \"show rows where amount > 5000\" or \"find orders from Mumbai\".");
}

function toggleChat() {
  chatOpen = !chatOpen;
  const box = document.getElementById('chat-box');
  if (chatOpen) { box.classList.add('open'); } else { box.classList.remove('open'); }
}

function endChat() {
  chatOpen = false;
  document.getElementById('chat-box').classList.remove('open');
  document.getElementById('chat-messages').innerHTML = '';
}

function addBotMessage(text, extraHtml = '') {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg msg-bot';
  div.innerHTML = `<div class="msg-bubble">${text}</div>${extraHtml}`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function addUserMessage(text) {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg msg-user';
  div.innerHTML = `<div class="msg-bubble">${text}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function addScopePrompt(question) {
  pendingQuestion = question;
  const scopeHtml = `
    <div class="scope-btns">
      <button class="scope-btn" onclick="runWithScope('valid')">Valid rows</button>
      <button class="scope-btn" onclick="runWithScope('invalid')">Invalid rows</button>
      <button class="scope-btn" onclick="runWithScope('both')">All rows</button>
    </div>`;
  addBotMessage("Which rows should I search?", scopeHtml);
}

async function runWithScope(scope) {
  if (!pendingQuestion) return;
  const question = pendingQuestion;
  pendingQuestion = null;
  await executeQuery(question, scope);
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';

  addUserMessage(question);

  const dataKeywords = [
    'show', 'find', 'filter', 'where', 'rows', 'amount', 'city',
    'phone', 'order', 'customer', 'payment', 'date', 'list', 'get',
    'count', 'how many', 'which', 'top', 'bottom', 'max', 'min',
    'average', 'total', 'product', 'category', 'quantity', 'email'
  ];
  const isDataQuery = dataKeywords.some(k => question.toLowerCase().includes(k));

  if (!isDataQuery) {
    await executeQuery(question, 'both');
  } else {
    addScopePrompt(question);
  }
}

async function executeQuery(question, scope) {
  addBotMessage('Searching...');

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: window.sessionId, question, scope })
    });
    const data = await res.json();

    const msgs = document.getElementById('chat-messages');
    msgs.removeChild(msgs.lastChild);

    if (data.error) {
      addBotMessage(data.error);
      return;
    }

    lastQueryRows = data.rows || [];
    lastQueryCols = data.columns || [];

    const viewBtn = data.has_table && lastQueryRows.length > 0
      ? `<div><button class="view-table-btn" onclick="openOverlay()">View table (${lastQueryRows.length} rows)</button></div>`
      : '';

    addBotMessage(data.answer, viewBtn);

  } catch(e) {
    const msgs = document.getElementById('chat-messages');
    if (msgs.lastChild) msgs.removeChild(msgs.lastChild);
    addBotMessage("Something went wrong. Please try again.");
  }
}

function openOverlay() {
  const head = document.getElementById('overlayHead');
  const body = document.getElementById('overlayBody');
  const count = document.getElementById('overlayCount');

  count.textContent = `${lastQueryRows.length} rows`;
  head.innerHTML = "<tr>" + lastQueryCols.map(c => `<th>${c}</th>`).join("") + "</tr>";
  body.innerHTML = "";
  for (const row of lastQueryRows) {
    const tr = document.createElement("tr");
    lastQueryCols.forEach(col => {
      const td = document.createElement("td");
      td.textContent = row[col] ?? "";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  }

  document.getElementById('table-overlay').classList.add('open');
}

function closeOverlay() {
  document.getElementById('table-overlay').classList.remove('open');
}

async function downloadChatCSV() {
  const res = await fetch('/download/chat-csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: lastQueryRows, columns: lastQueryCols })
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'query_results.csv'; a.click();
}

async function downloadChatPDF() {
  const res = await fetch('/download/chat-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: lastQueryRows, columns: lastQueryCols })
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'query_results.pdf'; a.click();
}