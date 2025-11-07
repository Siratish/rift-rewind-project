// Utility to map internal region codes to display names shown in the UI
// Example: na1 -> NA, sg2 -> SG
export function displayRegion(code) {
  if (!code) return '';
  const map = {
    na1: 'NA',
    euw1: 'EUW',
    eun1: 'EUNE',
    kr: 'KR',
    br1: 'BR',
    la1: 'LAN',
    la2: 'LAS',
    oc1: 'OCE',
    tr1: 'TR',
    ru: 'RU',
    jp1: 'JP',
    sg2: 'SG',
    tw2: 'TW',
    vn2: 'VN',
  };
  const key = String(code).toLowerCase();
  return map[key] || String(code).toUpperCase();
}
