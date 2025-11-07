// Fetch the latest Data Dragon version
let cachedVersion = null;

export async function getLatestDDragonVersion() {
    if (cachedVersion) return cachedVersion;
    
    try {
        const response = await fetch('https://ddragon.leagueoflegends.com/api/versions.json');
        const versions = await response.json();
        cachedVersion = versions[0]; // First value is the most recent
        return cachedVersion;
    } catch (error) {
        console.error('Failed to fetch Data Dragon version:', error);
        return '15.21.1'; // Fallback version
    }
}

export async function getProfileIconUrl(profileIconId) {
    if (!profileIconId) return '/default-icon.png';
    
    const version = await getLatestDDragonVersion();
    return `https://ddragon.leagueoflegends.com/cdn/${version}/img/profileicon/${profileIconId}.png`;
}
