// Knob objects (kept so we can call setValue later)
let prod_knob = null;
let hyd_knob = null;
let focus_knob = null;
let post_knob = null;

document.addEventListener("DOMContentLoaded", function () {
    makeKnobs();
    loadProductivityScore();
});

// Listen for classification results from share.js
window.addEventListener('classificationResult', (event) => {
    const { productivity_score } = event.detail;
    if (productivity_score !== undefined && prod_dial) {
        prod_dial.setValue(productivity_score);
    }
});

// Load initial productivity score
async function loadProductivityScore() {
    try {
        const response = await fetch('/get_productivity_score');
        const data = await response.json();
        if (data.productivity_score !== undefined && prod_dial) {
            prod_dial.setValue(data.productivity_score);
        }
    } catch (error) {
        console.error('Error loading productivity score:', error);
    }
}

function makeKnobs() {
    prod_knob  = createKnob('prod_dial');
    hyd_knob   = createKnob('hydration_dial');
    focus_knob = createKnob('focus_dial');
    post_knob  = createKnob('posture_dial');
}

function createKnob(parentDivID) {
    // Create knob element, 300 x 300 px in size.
    const knob = pureknob.createKnob(300, 300);

    // Set properties.
    knob.setProperty('angleStart', -0.75 * Math.PI);
    knob.setProperty('angleEnd', 0.75 * Math.PI);
    knob.setProperty('colorFG', '#f06161');
    knob.setProperty('trackWidth', 0.4);
    knob.setProperty('valMin', 0);
    knob.setProperty('valMax', 100);
    knob.setProperty('readonly', true);

    // Set initial value.
    knob.setValue(0);

    // Add the DOM node to the page.
    const elem = document.getElementById(parentDivID);
    elem.appendChild(knob.node());

    // Return the knob object (not the node) so setValue stays accessible.
    return knob;
}

// ── WebSocket score updates ──────────────────────────────────────────────────

let _ws = null;
let _wsActive = false;

function connectScoreSocket() {
    const WS_URL = 'ws://localhost:8765/ws';
    _wsActive = true;

    function connect() {
        if (!_wsActive) return;
        _ws = new WebSocket(WS_URL);

        _ws.addEventListener('message', (event) => {
            let msg;
            try { msg = JSON.parse(event.data); } catch { return; }

            if (msg.type !== 'score') return;

            const posture   = msg.posture   ?? null;
            const hydration = msg.hydration ?? null;
            const focus     = msg.focus     ?? null;

            if (posture   !== null) post_knob.setValue(posture);
            if (hydration !== null) hyd_knob.setValue(hydration);
            if (focus     !== null) focus_knob.setValue(focus);

            // Productivity = average of available scores
            const scores = [posture, hydration, focus].filter(v => v !== null);
            if (scores.length > 0) {
                const avg = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
                prod_knob.setValue(avg);
            }
        });

        _ws.addEventListener('close', () => {
            if (_wsActive) setTimeout(connect, 3000);
        });
    }

    connect();
}

function disconnectScoreSocket() {
    _wsActive = false;
    if (_ws) { _ws.close(); _ws = null; }
    // Reset dials to 0
    [prod_knob, hyd_knob, focus_knob, post_knob].forEach(k => k && k.setValue(0));
}