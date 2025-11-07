import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSummoner } from '../api.jsx';
import BackgroundParticles from './BackgroundParticles.jsx';

export default function LandingPage() {
    const [riotId, setRiotId] = useState('');
    const [region, setRegion] = useState('sg2');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();
    
    const lastYear = new Date().getFullYear() - 1;

    async function handleStart(e) {
        e && e.preventDefault();
        setError(null);
        if (!riotId) return setError('Please enter your Riot ID.');

        // Parse Riot ID into gameName and tagLine
        const [gameName, tagLine] = riotId.split('#');
        if (!gameName || !tagLine) {
            return setError('Please enter a valid Riot ID with # (e.g. SummonerName#TAG)');
        }

        setLoading(true);
        try {
            const body = await fetchSummoner(`${gameName}#${tagLine}`, region);
            // Expected response: { summoner: {...}, routing_value, year, summary_exists, final_exists }
            // Clear any old data and save new summoner response
            sessionStorage.removeItem('rr_final'); // Clear old quiz results
            sessionStorage.removeItem('rr_progress'); // Clear old progress
            sessionStorage.setItem('rr_summoner_response', JSON.stringify(body));
            navigate(`/${region}/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`);
        } catch (err) {
            setError(err.message || String(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="flex items-center justify-center px-6 pt-16 pb-6 min-h-[calc(100vh-3rem)]">
            <BackgroundParticles />
            <div className="max-w-2xl w-full rr-panel text-center">
                <h1 className="text-3xl riot-gold mb-2">Rift Trivia</h1>
                <p className="text-sm text-text-secondary mb-6">Your {lastYear} on the Rift, reimagined as a quiz.
Relive your journey through 10 questions only your stats can answer.</p>

                <form onSubmit={handleStart} className="space-y-4">
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                        <div className="flex-1 w-full">
                            <input
                                value={riotId}
                                onChange={(e) => setRiotId(e.target.value)}
                                className="w-full p-3 rounded-lg bg-white/5 placeholder:text-text-secondary/50 border border-panel-secondary focus:border-accent-gold/50 focus:outline-hidden transition-colors text-text-primary"
                                placeholder="SummonerName#TAG"
                                aria-label="Riot ID"
                            />
                        </div>

                        <div className="w-16">
                            <select
                                value={region}
                                onChange={(e) => setRegion(e.target.value)}
                                className="w-full pt-3 pb-3 rounded-lg bg-white/5 text-text-primary border border-panel-secondary focus:border-accent-gold/50 focus:outline-hidden transition-colors text-center appearance-none"
                                aria-label="Region"
                            >
                                <option value="na1">NA</option>
                                <option value="euw1">EUW</option>
                                <option value="eun1">EUNE</option>
                                <option value="kr">KR</option>
                                <option value="br1">BR</option>
                                <option value="la1">LAN</option>
                                <option value="la2">LAS</option>
                                <option value="oc1">OCE</option>
                                <option value="tr1">TR</option>
                                <option value="ru">RU</option>
                                <option value="jp1">JP</option>
                                <option value="sg2">SG</option>
                                <option value="tw2">TW</option>
                                <option value="vn2">VN</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex justify-center">
                        <button type="submit" className="btn-cta disabled:opacity-50 disabled:cursor-not-allowed" disabled={loading}>
                            {loading ? 'Starting...' : 'Start My Rift Trivia'}
                        </button>
                    </div>

                    {error && <div className="text-error-red text-sm mt-2">{error}</div>}
                </form>

            </div>
        </div>
    );
}