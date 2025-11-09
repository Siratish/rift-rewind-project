import { API_BASE } from './config.jsx';

export async function fetchSummoner(summonerName, region) {
  if (!API_BASE) {
    throw new Error('API base URL not configured');
  }
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ summonerName, region }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(err.message || 'Failed to fetch summoner');
  }
  return res.json();
}
