// Switch views
const body = document.body;
const toggleBtn = document.getElementById('toggle-btn');
const closeBtn = document.getElementById('close-btn');

toggleBtn.addEventListener('click', () => {
    body.className = 'view-dashboard';
    if (window.pywebview) {
        pywebview.api.resize_window('dashboard');
    }
});

closeBtn.addEventListener('click', () => {
    body.className = 'view-dock';
    if (window.pywebview) {
        pywebview.api.resize_window('dock');
    }
});

// Update state (idle, listening, thinking)
function setState(stateStr, message = "") {
    const sweep = document.getElementById('main-dial-sweep');
    const statusText = document.getElementById('status-text');
    
    sweep.className = `dial-sweep ${stateStr}`;
    
    if (message) {
        statusText.innerText = message;
    } else {
        if (stateStr === 'idle') statusText.innerText = "Say 'hey sweetie' to begin";
        else if (stateStr === 'listening') statusText.innerText = "Listening...";
        else if (stateStr === 'thinking') statusText.innerText = "Thinking...";
    }
}

// Update transcript
function updateTranscript(text) {
    document.getElementById('transcript-container').innerText = text;
}

// Update Stats
function updateStats(cpu, mem, disk) {
    document.getElementById('cpu-sweep').setAttribute('stroke-dasharray', `${cpu}, 100`);
    document.getElementById('cpu-val').innerText = `${Math.round(cpu)}%`;

    document.getElementById('mem-sweep').setAttribute('stroke-dasharray', `${mem}, 100`);
    document.getElementById('mem-val').innerText = `${Math.round(mem)}%`;

    document.getElementById('disk-sweep').setAttribute('stroke-dasharray', `${disk}, 100`);
    document.getElementById('disk-val').innerText = `${Math.round(disk)}%`;
}

// Log entries
function addLogEntry(message) {
    const ul = document.getElementById('activity-log');
    const li = document.createElement('li');
    
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    li.innerHTML = `<span class="log-time">[${timeStr}]</span> ${message}`;
    ul.prepend(li);
}

// Quick Actions
function triggerAction(actionName) {
    addLogEntry(`Action: ${actionName} (Not implemented)`);
    if (window.pywebview) {
        pywebview.api.trigger_action(actionName);
    }
}
