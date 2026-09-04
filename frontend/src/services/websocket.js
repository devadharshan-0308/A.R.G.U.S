/**
 * WebSocket Connection Helper for ARGUS Live Broadcast Stream (ws://localhost:8000/ws/live)
 */

export function createTelemetrySocket(onMessage, onStatusChange) {
  let ws = null;
  let reconnectTimer = null;
  let isClosedIntentionally = false;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname || 'localhost';
  // Use current host:port or fallback to port 8000
  const wsUrl = `${protocol}//${host}:8000/ws/live`;

  function connect() {
    if (onStatusChange) onStatusChange('CONNECTING');
    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (onStatusChange) onStatusChange('CONNECTED');
        console.log('⚡ Connected to ARGUS Live Telemetry WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (err) {
          console.error('Error parsing WS message:', err);
        }
      };

      ws.onerror = (err) => {
        console.warn('WS error:', err);
        if (onStatusChange) onStatusChange('ERROR');
      };

      ws.onclose = () => {
        if (onStatusChange) onStatusChange('DISCONNECTED');
        if (!isClosedIntentionally) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    } catch (err) {
      console.warn('WS Connection failed:', err);
      if (onStatusChange) onStatusChange('ERROR');
      reconnectTimer = setTimeout(connect, 4000);
    }
  }

  connect();

  return () => {
    isClosedIntentionally = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}
