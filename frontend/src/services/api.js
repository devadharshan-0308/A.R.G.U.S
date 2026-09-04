/**
 * API Service for ARGUS Backend
 * Connects to FastAPI server (http://localhost:8000)
 */

const BASE_URL = '';

export async function fetchHealth() {
  try {
    const res = await fetch(`${BASE_URL}/api/health`);
    return await res.json();
  } catch (err) {
    console.warn('Backend health check failed:', err);
    return { status: 'OFFLINE' };
  }
}

export async function fetchStats() {
  try {
    const res = await fetch(`${BASE_URL}/api/stats`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch stats:', err);
    return null;
  }
}

export async function fetchPotholes(severity = '', limit = 100) {
  try {
    const query = severity ? `?severity=${encodeURIComponent(severity)}&limit=${limit}` : `?limit=${limit}`;
    const res = await fetch(`${BASE_URL}/api/potholes${query}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch potholes:', err);
    return [];
  }
}

export async function fetchViolations(limit = 100) {
  try {
    const res = await fetch(`${BASE_URL}/api/violations?limit=${limit}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch violations:', err);
    return [];
  }
}

export async function fetchPlates(searchQuery = '', limit = 100) {
  try {
    const query = searchQuery ? `?q=${encodeURIComponent(searchQuery)}&limit=${limit}` : `?limit=${limit}`;
    const res = await fetch(`${BASE_URL}/api/plates${query}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch plates:', err);
    return [];
  }
}

export async function fetchVideos() {
  try {
    const res = await fetch(`${BASE_URL}/api/videos`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch videos list:', err);
    return [];
  }
}

export async function triggerPipeline(videoName = 'pothole.mp4', enablePotholes = true) {
  try {
    const res = await fetch(`${BASE_URL}/api/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_name: videoName, enable_potholes: enablePotholes })
    });
    return await res.json();
  } catch (err) {
    console.error('Error triggering pipeline:', err);
    return { status: 'ERROR', message: err.message };
  }
}

export async function fetchPipelineStatus() {
  try {
    const res = await fetch(`${BASE_URL}/api/pipeline/status`);
    return await res.json();
  } catch (err) {
    return { is_running: false };
  }
}

export async function fetchPwdWorkOrders() {
  try {
    const res = await fetch(`${BASE_URL}/api/pwd/work-orders`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch PWD work orders:', err);
    return { status: 'ERROR', total_orders: 0, total_budget_inr: 0, orders: [] };
  }
}

export async function dispatchMunicipalWorkOrder() {
  try {
    const res = await fetch(`${BASE_URL}/api/pwd/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return await res.json();
  } catch (err) {
    return { status: 'ERROR', message: err.message };
  }
}
