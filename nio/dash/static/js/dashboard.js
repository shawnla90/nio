// NIO Dashboard - Live updates via HTMX + WebSocket

document.addEventListener('DOMContentLoaded', () => {
    // WebSocket connection for live updates
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'turn') {
            updateSlopGauge(data.slop_score);
            prependTurn(data);
        }
    };

    ws.onclose = () => {
        // Reconnect after 3 seconds
        setTimeout(() => window.location.reload(), 3000);
    };
});

function updateSlopGauge(score) {
    const gauge = document.getElementById('slop-gauge');
    if (gauge) {
        gauge.textContent = `${score.toFixed(1)}/100`;
        gauge.style.color = score >= 90 ? 'var(--green)' :
                           score >= 70 ? 'var(--yellow)' : 'var(--red)';
    }
}

function prependTurn(turn) {
    const feed = document.getElementById('turn-feed');
    if (!feed) return;

    const el = document.createElement('div');
    el.className = 'turn-entry';
    el.innerHTML = `
        <span class="turn-score" style="color: ${turn.slop_score >= 90 ? 'var(--green)' : turn.slop_score >= 70 ? 'var(--yellow)' : 'var(--red)'}">
            ${turn.slop_score.toFixed(1)}
        </span>
        <span class="turn-latency">${turn.latency_ms}ms</span>
        <span class="turn-time">${new Date(turn.created_at).toLocaleTimeString()}</span>
    `;

    feed.insertBefore(el, feed.firstChild);

    // Keep max 20 entries
    while (feed.children.length > 20) {
        feed.removeChild(feed.lastChild);
    }
}
