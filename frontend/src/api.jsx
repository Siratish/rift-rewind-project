export async function fetchSummoner(riotId, region) {
  const API_BASE = import.meta.env.REACT_APP_API_BASE || import.meta.env.VITE_API_BASE || '';
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ riotId, region }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(err.message || 'Failed to fetch summoner');
  }
  return res.json();
}
