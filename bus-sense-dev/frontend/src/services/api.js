/**
 * REST API client for Smart City Ingestion Backend.
 */

export const BACKEND_URL = window.location.port === '5173' 
  ? 'http://localhost:8000' 
  : '';

export function getFullEvidenceUrl(path) {
  if (!path) return null;
  if (path.startsWith('http')) return path;
  return `${BACKEND_URL}${path.startsWith('/') ? '' : '/'}${path}`;
}

export async function fetchStats() {
  const res = await fetch(`${BACKEND_URL}/api/stats`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchPotholes(severity = null, limit = 100) {
  const url = severity 
    ? `${BACKEND_URL}/api/potholes?severity=${encodeURIComponent(severity)}&limit=${limit}`
    : `${BACKEND_URL}/api/potholes?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const items = await res.json();
  return items.map(p => ({
    ...p,
    evidence_image: getFullEvidenceUrl(p.evidence_image)
  }));
}

export async function fetchViolations(violationType = null, limit = 100) {
  const url = violationType
    ? `${BACKEND_URL}/api/violations?violation_type=${encodeURIComponent(violationType)}&limit=${limit}`
    : `${BACKEND_URL}/api/violations?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const items = await res.json();
  return items.map(v => ({
    ...v,
    evidence_image: getFullEvidenceUrl(v.evidence_image)
  }));
}

export async function fetchPlates(searchQuery = '', limit = 100) {
  const url = searchQuery
    ? `${BACKEND_URL}/api/plates?q=${encodeURIComponent(searchQuery)}&limit=${limit}`
    : `${BACKEND_URL}/api/plates?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const items = await res.json();
  return items.map(pl => ({
    ...pl,
    evidence_image: getFullEvidenceUrl(pl.evidence_image)
  }));
}

export async function fetchMetrics(limit = 100) {
  const res = await fetch(`${BACKEND_URL}/api/metrics?limit=${limit}`);
  if (!res.ok) return [];
  return await res.json();
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}
