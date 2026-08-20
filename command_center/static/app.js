// Command Center Frontend Logic

const ws = new WebSocket(`ws://${location.host}/ws`);
let currentTab = 'chat';
let pendingConfirmation = null;

// === WebSocket ===

ws.onopen = () => {
    console.log('Connected to command center');
    setInterval(() => ws.send(JSON.stringify({type: 'ping'})), 30000);
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'pong') return;
    
    addLogEntry(msg.type, msg.data);
    
    switch(msg.type) {
        case 'thinking':
            addMessage('thinking', `[Step ${msg.data.step}] ${msg.data.message}`);
            updateStatus('running', `Step ${msg.data.step}`);
            break;
        case 'response':
            addMessage('assistant', msg.data.content);
            break;
        case 'tool_call':
            addMessage('tool', formatToolCall(msg.data));
            break;
        case 'tool_result':
            addMessage('tool', formatToolResult(msg.data), true);
            break;
        case 'error':
            addMessage('error', msg.data.error);
            updateStatus('error', 'Error');
            break;
        case 'confirmation_request':
            showConfirmation(msg.data);
            break;
        case 'emergency_stop':
            updateStatus('stopped', 'Stopped');
            document.getElementById('stopBtn').style.display = 'none';
            break;
        case 'chat':
            addMessage('user', msg.data.user);
            addMessage('assistant', msg.data.assistant);
            break;
    }
    
    fetchStatus();
};

ws.onclose = () => {
    addMessage('error', 'Connection to command center lost. Refresh the page.');
    updateStatus('error', 'Disconnected');
};

// === Chat ===

function addMessage(type, content, isResult = false) {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerHTML = isResult ? content : escapeHtml(content);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatToolCall(data) {
    const argsStr = JSON.stringify(data.args, null, 2);
    return `<span class="tool-name">🔧 ${data.tool}</span>\n<pre>${escapeHtml(argsStr)}</pre>`;
}

function formatToolResult(data) {
    const resultStr = JSON.stringify(data.result, null, 2);
    return `<span class="tool-name">✅ ${data.tool} result:</span>\n<div class="tool-result"><pre>${escapeHtml(resultStr)}</pre></div>`;
}

// === Input ===

function handleInputKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendInput();
    }
    
    const ta = event.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
}

async function sendInput() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const autoConfirm = document.getElementById('autoConfirm').checked;
    
    addMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    
    document.getElementById('stopBtn').style.display = 'inline-block';
    
    if (mode === 'task') {
        const res = await fetch('/api/task', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({goal: text, auto_confirm: autoConfirm})
        });
        const data = await res.json();
        if (data.error) {
            addMessage('error', data.error);
            document.getElementById('stopBtn').style.display = 'none';
        }
    } else {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        const data = await res.json();
        if (data.error) addMessage('error', data.error);
        document.getElementById('stopBtn').style.display = 'none';
    }
}

// === Confirmation ===

function showConfirmation(data) {
    pendingConfirmation = data;
    const overlay = document.getElementById('confirmOverlay');
    const detail = document.getElementById('confirmDetail');
    
    detail.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Tool:</strong> ${escapeHtml(data.tool)}</div>
        <div><strong>Arguments:</strong></div>
        <pre>${escapeHtml(JSON.stringify(data.args, null, 2))}</pre>
    `;
    
    overlay.classList.add('active');
}

async function respondConfirmation(approved) {
    document.getElementById('confirmOverlay').classList.remove('active');
    await fetch('/api/confirm', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({approved: approved, step: pendingConfirmation?.step || 0})
    });
    pendingConfirmation = null;
}

// === Emergency Stop ===

async function emergencyStop() {
    await fetch('/api/stop', {method: 'POST'});
    updateStatus('stopped', 'Stopped');
    document.getElementById('stopBtn').style.display = 'none';
}

// === Tabs ===

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
    currentTab = tab;
    
    if (tab === 'tasks') fetchTasks();
}

// === Action Log ===

function addLogEntry(type, data) {
    const log = document.getElementById('actionLog');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const time = new Date().toLocaleTimeString();
    let content = '';
    
    switch(type) {
        case 'thinking':
            content = `[Step ${data.step}] ${data.message || ''}`;
            break;
        case 'tool_call':
            content = `<strong>${data.tool}</strong>\n${JSON.stringify(data.args, null, 2)}`;
            break;
        case 'tool_result':
            content = `<strong>${data.tool}</strong> →\n${JSON.stringify(data.result, null, 2)}`;
            break;
        case 'response':
            content = data.content || '';
            break;
        case 'error':
            content = data.error || JSON.stringify(data);
            break;
        case 'confirmation_request':
            content = `Tool: ${data.tool}\nArgs: ${JSON.stringify(data.args, null, 2)}`;
            break;
        default:
            content = JSON.stringify(data, null, 2);
    }
    
    entry.innerHTML = `
        <div class="log-type">${type.replace(/_/g, ' ')} · ${time}</div>
        <div class="log-content"><pre>${escapeHtml(content)}</pre></div>
    `;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// === Status ===

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('statSteps').textContent = data.step_count || 0;
        document.getElementById('statActions').textContent = data.action_count || 0;
        
        if (data.is_running) {
            updateStatus('running', `Running (Step ${data.step_count})`);
        } else if (data.emergency_stopped) {
            updateStatus('stopped', 'Stopped');
            document.getElementById('stopBtn').style.display = 'none';
        } else if (!document.getElementById('statusText').textContent.includes('Error')) {
            updateStatus('idle', 'Idle');
            document.getElementById('stopBtn').style.display = 'none';
        }
    } catch(e) {}
}

function updateStatus(state, text) {
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    dot.className = `status-dot ${state}`;
    txt.textContent = text;
}

// === Tools ===

async function fetchTools() {
    try {
        const [catRes, toolRes] = await Promise.all([
            fetch('/api/tools/categories'),
            fetch('/api/tools')
        ]);
        const categories = await catRes.json();
        const allTools = await toolRes.json();
        
        const list = document.getElementById('toolsList');
        list.innerHTML = '';
        
        for (const [category, tools] of Object.entries(categories)) {
            tools.forEach(toolName => {
                const toolDef = allTools.find(t => t.name === toolName);
                const item = document.createElement('div');
                item.className = 'tool-item';
                item.innerHTML = `
                    <span class="tool-category">${category}</span>
                    <span class="tool-name">${toolName}</span>
                    ${toolDef?.requires_confirmation ? '<span class="tool-confirm">⚠ confirm</span>' : ''}
                `;
                list.appendChild(item);
            });
        }
    } catch(e) {
        console.error('Failed to fetch tools:', e);
        document.getElementById('toolsList').innerHTML = '<span style="color: var(--text-muted)">Failed to load tools</span>';
    }
}

// === Device Status ===

async function fetchDeviceStatus() {
    const el = document.getElementById('deviceStatus');
    let html = '';
    
    try {
        const res = await fetch('/api/phone/status');
        const data = await res.json();
        if (data.connected) {
            const count = data.devices.length;
            html += `<div style="color: var(--success)">📱 Phone: Connected (${count} device${count > 1 ? 's' : ''})</div>`;
        } else {
            html += `<div style="color: var(--text-muted)">📱 Phone: Not connected</div>`;
        }
    } catch(e) {
        html += `<div style="color: var(--text-muted)">📱 Phone: Not connected</div>`;
    }
    
    html += `<div style="color: var(--success); margin-top: 4px;">💻 Computer: Active</div>`;
    el.innerHTML = html;
}

// === Tasks ===

async function fetchTasks() {
    try {
        const res = await fetch('/api/tasks');
        const tasks = await res.json();
        const list = document.getElementById('taskList');
        
        if (!tasks || tasks.length === 0) {
            list.innerHTML = '<div style="color: var(--text-muted); padding: 20px; text-align: center;">No tasks yet.</div>';
            return;
        }
        
        list.innerHTML = '';
        tasks.forEach(task => {
            const item = document.createElement('div');
            item.className = 'task-item';
            item.onclick = () => loadTaskDetails(task.id);
            item.innerHTML = `
                <div class="task-goal">${escapeHtml(task.goal)}</div>
                <div class="task-status ${task.status}">${task.status} · ${new Date(task.created_at * 1000).toLocaleString()}</div>
            `;
            list.appendChild(item);
        });
    } catch(e) {
        console.error('Failed to fetch tasks:', e);
    }
}

async function loadTaskDetails(taskId) {
    try {
        const res = await fetch(`/api/task/${taskId}`);
        const task = await res.json();
        const list = document.getElementById('taskList');
        list.innerHTML = `
            <div style="margin-bottom: 12px;">
                <button class="btn" onclick="fetchTasks()">← Back</button>
            </div>
            <div class="task-item">
                <div class="task-goal">${escapeHtml(task.goal)}</div>
                <div class="task-status ${task.status}">${task.status}</div>
            </div>
            ${task.result ? `<div class="log-entry response" style="margin-top: 12px;">
                <div class="log-type">Result</div>
                <div class="log-content"><pre>${escapeHtml(task.result)}</pre></div>
            </div>` : ''}
        `;
    } catch(e) {}
}

// === Conversation ===

async function clearConversation() {
    if (!confirm('Clear all conversation history?')) return;
    await fetch('/api/conversation', {method: 'DELETE'});
    document.getElementById('messages').innerHTML = '';
    document.getElementById('actionLog').innerHTML = '';
    addMessage('assistant', 'Conversation cleared. Ready for a new task.');
}

// === Facts ===

async function fetchFacts() {
    try {
        const res = await fetch('/api/facts');
        const facts = await res.json();
        const el = document.getElementById('factsList');
        
        if (!facts || facts.length === 0) {
            el.innerHTML = '<span style="color: var(--text-muted)">No facts stored.</span>';
            return;
        }
        
        el.innerHTML = facts.map(f => 
            `<div style="margin-bottom: 4px;"><strong>${escapeHtml(f.key)}</strong>: ${escapeHtml(f.value)} <span style="color:var(--text-muted)">(${f.category})</span></div>`
        ).join('');
    } catch(e) {}
}

// === Model Info ===

async function fetchModelInfo() {
    try {
        const res = await fetch('/api/models');
        const data = await res.json();
        if (data.models && data.models.length > 0) {
            document.getElementById('modelText').textContent = data.models[0];
        }
    } catch(e) {}
}

// === Init ===

async function init() {
    addMessage('assistant', 'Welcome to your Autonomous Agent Command Center. I can control your computer, phone, and filesystem.\n\nGive me a task to execute, or switch to Simple Chat mode for direct conversation.');
    
    fetchTools();
    fetchDeviceStatus();
    fetchFacts();
    fetchModelInfo();
    
    setInterval(fetchStatus, 2000);
    setInterval(fetchDeviceStatus, 10000);
}

init();
