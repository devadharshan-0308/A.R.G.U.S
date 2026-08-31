/**
 * Reconnecting WebSocket service for live real-time Smart City incident feeds.
 */

import { getFullEvidenceUrl } from './api';

export class SmartCityWebSocket {
  constructor(url, onMessage, onStatusChange) {
    this.url = url;
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
    this.ws = null;
    this.reconnectTimer = null;
    this.isManualClose = false;
    this.reconnectInterval = 2500;
  }

  connect() {
    this.isManualClose = false;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.onStatusChange('CONNECTING');

      // In development mode (Vite port 5173), connect directly to backend port 8000
      let defaultWsUrl = 'ws://localhost:8000/ws/live';
      if (window.location.port !== '5173') {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        defaultWsUrl = `${protocol}//${window.location.host}/ws/live`;
      }

      const targetUrl = this.url || defaultWsUrl;

      this.ws = new WebSocket(targetUrl);

      this.ws.onopen = () => {
        this.onStatusChange('CONNECTED');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.evidence_image) {
            data.evidence_image = getFullEvidenceUrl(data.evidence_image);
          }
          if (this.onMessage) {
            this.onMessage(data);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      this.ws.onclose = () => {
        this.onStatusChange('DISCONNECTED');
        if (!this.isManualClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        this.onStatusChange('DISCONNECTED');
        this.ws.close();
      };
    } catch (err) {
      this.onStatusChange('DISCONNECTED');
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectInterval);
  }

  disconnect() {
    this.isManualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
    }
    this.onStatusChange('DISCONNECTED');
  }
}
