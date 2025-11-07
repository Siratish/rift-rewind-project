import React, { useRef, useState, useEffect } from 'react';
import { displayRegion } from '../utils/regions.js';
import { getProfileIconUrl } from '../utils/ddragon.js';

export default function ShareCardPreview({ payload }) {
    const ref = useRef(null);
    const [copied, setCopied] = useState(false);
    const [iconUrl, setIconUrl] = useState('/default-icon.png');

    const summoner = payload?.summoner || {};

    useEffect(() => {
        if (summoner?.profileIconId) {
            getProfileIconUrl(summoner.profileIconId).then(setIconUrl);
        }
    }, [summoner?.profileIconId]);

    async function downloadImage() {
        if (!ref.current) return;
        try {
            const { toPng } = await import('html-to-image');
            const dataUrl = await toPng(ref.current, { pixelRatio: 2 });
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = 'rift-trivia-card.png';
            a.click();
        } catch (e) {
            alert('Image export failed. Make sure html-to-image is installed.');
        }
    }

    function handleCopyLink() {
        navigator.clipboard.writeText(window.location.href);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    const quizFacts = payload?.quizFacts || [];

    const displayName = summoner?.gameName || 'Summoner';
    const tag = summoner?.tagLine || '';
    const regionDisplay = displayRegion(summoner?.region);
    const regionLevel = `${regionDisplay}${summoner?.level ? ` • Level ${summoner.level}` : ''}`;

    // Highlight entire words that contain numbers (e.g., "100-sS")
    function highlightNumbers(text) {
        if (!text) return text;
        // Split by whitespace but keep the separators
        const tokens = String(text).split(/(\s+)/);
        return tokens.map((tok, i) => {
            // Preserve whitespace tokens as-is
            if (tok.trim() === '') return tok;
            // If token contains any digit, highlight the whole token
            if (/\d/.test(tok)) {
                return (
                    <span key={i} className="font-extrabold text-accent-gold">{tok}</span>
                );
            }
            // Otherwise render normally
            return <span key={i}>{tok}</span>;
        });
    }

    return (
        <div>
            <div ref={ref} className="rr-card w-full max-w-[620px] mx-auto">
                {/* Vignette overlay */}
                <div className="rr-card-vignette" />

                {/* Header: profile + year badge */}
                <div className="flex items-center justify-between mb-4 relative z-10">
                    <div className="flex items-center gap-4">
                        <img
                            src={iconUrl}
                            alt="icon"
                            className="w-14 h-14 rounded-full ring-2 ring-accent-gold/40"
                        />
                        <div>
                            <div className="font-extrabold text-xl riot-gold">
                                {displayName}
                                {tag && <span className="text-base text-silver">#{tag}</span>}
                            </div>
                            <div className="text-sm text-text-secondary">{regionLevel}</div>
                        </div>
                    </div>
                    {/* Year badge removed per request */}
                </div>

                {/* Divider */}
                <div className="rr-gold-divider mb-4" />

                {/* Title */}
                <div className="font-bold text-lg riot-gold mb-3 relative z-10">Rift Trivia 2024</div>

                {/* Facts */}
                <div className="space-y-2 text-[13px] leading-relaxed text-text-secondary relative z-10">
                    {quizFacts.map((q, i) => (
                        <div
                            key={i}
                            className={`p-2 rounded ${i % 2 === 0 ? 'bg-white/[0.03]' : 'bg-white/[0.02]'}`}
                        >
                            <div className="font-semibold text-text-primary">{highlightNumbers(q.fact)}</div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="mt-4 flex flex-col gap-3">
                <button onClick={downloadImage} className="w-full btn-cta">⬇️ Download Card</button>
                <button 
                    onClick={handleCopyLink} 
                    className="w-full btn-cta"
                >
                    {copied ? '✓ Link Copied!' : '📋 Copy Link'}
                </button>
            </div>
        </div>
    );
}