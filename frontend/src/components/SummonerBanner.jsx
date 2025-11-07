import React, { useEffect, useState } from 'react';
import { displayRegion } from '../utils/regions.js';
import { getProfileIconUrl } from '../utils/ddragon.js';

export default function SummonerBanner({ summoner }) {
    const displayName = summoner?.gameName || 'Summoner';
    const tag = summoner?.tagLine;
    const regionDisplay = displayRegion(summoner?.region);
    const levelText = summoner?.level ? ` • Level ${summoner.level}` : '';
    const [iconUrl, setIconUrl] = useState('/default-icon.png');
    
    useEffect(() => {
        if (summoner?.profileIconId) {
            getProfileIconUrl(summoner.profileIconId).then(setIconUrl);
        }
    }, [summoner?.profileIconId]);
    
    return (
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
                <div className="text-sm text-text-secondary">{regionDisplay}{levelText}</div>
            </div>
        </div>
    );
}