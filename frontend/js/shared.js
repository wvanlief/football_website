/**
 * shared.js - Canonical Shared Frontend Utilities for FindFootball
 * 
 * Provides centralized implementations for:
 * - COUNTRY_FLAGS & getFlagUrl (handles national flags + club crest fallbacks)
 * - resolveTimezone (sessionStorage-cached geo-IP sniffer with Intl API fallback)
 * - getRatingClass, getRatingText, getRatingIcon (consistent Watchability tiers)
 * - showToast (debounced notification toast)
 * - openMatchDetails (modal inspector with progress bar animations & tournament routing)
 */

const COUNTRY_FLAGS = {
    "Spain": "es", "Argentina": "ar", "France": "fr", "England": "gb-eng",
    "Brazil": "br", "Portugal": "pt", "Colombia": "co", "Netherlands": "nl",
    "Germany": "de", "Norway": "no", "Japan": "jp", "Turkey": "tr",
    "Uruguay": "uy", "Switzerland": "ch", "Senegal": "sn", "Mexico": "mx",
    "USA": "us", "Canada": "ca", "Morocco": "ma", "Algeria": "dz",
    "Croatia": "hr", "Ecuador": "ec", "Austria": "at", "Paraguay": "py",
    "South Korea": "kr", "Australia": "au", "Scotland": "gb-sct",
    "Iran": "ir", "Uzbekistan": "uz", "Qatar": "qa",
    "South Africa": "za", "Haiti": "ht", "Curaçao": "cw", "Cape Verde": "cv",
    "Panama": "pa", "Ghana": "gh", "New Zealand": "nz", "Jordan": "jo",
    "Czechia": "cz", "Bosnia and Herzegovina": "ba", "Côte d'Ivoire": "ci",
    "Tunisia": "tn", "Poland": "pl", "Belgium": "be", "Egypt": "eg",
    "Saudi Arabia": "sa", "Iraq": "iq", "Jamaica": "jm", "Sweden": "se",
    "Democratic Republic of the Congo": "cd", "Italy": "it", "Denmark": "dk",
    "Serbia": "rs", "Ukraine": "ua", "Wales": "gb-wls", "Chile": "cl",
    "Peru": "pe", "Venezuela": "ve", "Bolivia": "bo", "Greece": "gr",
    "Romania": "ro", "Hungary": "hu", "Slovakia": "sk", "Slovenia": "si",
    "Albania": "al", "Georgia": "ge", "Ireland": "ie", "Republic of Ireland": "ie",
    "Northern Ireland": "gb-nir", "Finland": "fi", "Iceland": "is"
};

/**
 * Returns a crest/flag URL for national teams or clubs.
 * Supports direct logo URLs, API-Football IDs, flagcdn country codes, and static fallbacks.
 */
function getFlagUrl(target, size = 'w40') {
    if (!target) return '/static/badges/default.png';
    let teamName = null;
    let url = null;
    let apiId = null;

    if (typeof target === 'object') {
        url = target.logo_url;
        teamName = target.name || target.team;
        apiId = target.api_id;
    } else if (typeof target === 'string') {
        teamName = target;
    }

    if (url && url.startsWith('http')) {
        return url;
    }
    if (apiId) {
        return `https://media.api-sports.io/football/teams/${apiId}.png`;
    }
    if (url && url.startsWith('/static/badges/') && !url.endsWith('default.png')) {
        const matchId = url.match(/\/static\/badges\/(\d+)\.png/);
        if (matchId) {
            return `https://media.api-sports.io/football/teams/${matchId[1]}.png`;
        }
    }
    if (teamName) {
        const code = COUNTRY_FLAGS[teamName];
        if (code) return `https://flagcdn.com/${size}/${code}.png`;
    }
    return (url && !url.endsWith('default.png')) ? url : '/static/badges/default.png';
}

/**
 * Resolves user timezone.
 * Caches in sessionStorage so navigating across pages performs at most 1 geo-IP call per session.
 * Falls back to browser Intl API if geo-IP request fails.
 */
async function resolveTimezone(selectedTimezone = 'local') {
    if (selectedTimezone && selectedTimezone !== 'local') {
        return selectedTimezone;
    }

    const cachedTz = sessionStorage.getItem('findfootball-resolved-timezone');
    if (cachedTz) {
        return cachedTz;
    }

    try {
        const geoRes = await fetch('https://ipapi.co/json/');
        if (geoRes.ok) {
            const geoData = await geoRes.json();
            if (geoData.timezone) {
                sessionStorage.setItem('findfootball-resolved-timezone', geoData.timezone);
                console.log(`Detected timezone from IP lookup: ${geoData.timezone} (${geoData.country_name || ''})`);
                return geoData.timezone;
            }
        }
    } catch (err) {
        console.warn("Geo-IP timezone lookup failed, falling back to browser Intl API:", err);
    }

    try {
        const intlTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (intlTz) {
            sessionStorage.setItem('findfootball-resolved-timezone', intlTz);
            return intlTz;
        }
    } catch (e) {}

    return 'UTC';
}

/**
 * Watchability Tier Classification Helpers
 */
function getRatingClass(score) {
    if (score >= 71.7) return 'must-watch';
    if (score >= 65.0) return 'recommended';
    if (score >= 45.0) return 'average';
    return 'skip';
}

function getRatingText(score) {
    if (score >= 71.7) return 'Must Watch';
    if (score >= 65.0) return 'Recommended';
    if (score >= 45.0) return 'Average';
    return 'Skip';
}

function getRatingIcon(score) {
    if (score >= 71.7) return 'fa-solid fa-trophy';
    if (score >= 65.0) return 'fa-solid fa-fire';
    if (score >= 45.0) return 'fa-solid fa-chart-simple';
    return 'fa-solid fa-face-meh';
}

/**
 * Toast Notification Helper
 */
function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerText = message;
    toast.classList.add('show');
    if (window._toastTimeout) {
        clearTimeout(window._toastTimeout);
    }
    window._toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

/**
 * Match Details Modal Inspector
 * Supports pre-populated match object or fixture ID lookup.
 */
async function openMatchDetails(matchOrId, currentTz = null) {
    const matchModal = document.getElementById('match-modal');
    const modalContainer = document.getElementById('modal-details-container');
    if (!matchModal || !modalContainer) return;

    let match = matchOrId;
    if (typeof matchOrId === 'number' || typeof matchOrId === 'string' || (matchOrId && !matchOrId.watchability)) {
        modalContainer.innerHTML = '<div class="loading-spinner" style="padding: 2rem; text-align: center;"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading details...</div>';
        matchModal.classList.add('open');
        const tz = currentTz || (await resolveTimezone('local'));
        const fixtureId = (typeof matchOrId === 'object') ? matchOrId.id : matchOrId;
        try {
            const res = await fetch(`/api/fixtures/${fixtureId}?tz=${encodeURIComponent(tz)}`);
            if (!res.ok) throw new Error("Failed to fetch fixture details");
            match = await res.json();
        } catch (err) {
            console.error("Failed to fetch match details", err);
            modalContainer.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Failed to load match details.</div>';
            return;
        }
    }

    if (!match || !match.home_team || !match.away_team) return;

    const overallScore = match.watchability ? match.watchability.overall : 50;
    const ratingClass = getRatingClass(overallScore);
    const ratingText = getRatingText(overallScore);
    const ratingIcon = getRatingIcon(overallScore);

    const homePlayers = match.home_team.players || [];
    const awayPlayers = match.away_team.players || [];
    const allPlayers = [...homePlayers, ...awayPlayers];

    let playersHtml = '';
    if (allPlayers.length > 0) {
        playersHtml = `
            <div class="players-section">
                <h4 class="section-title"><i class="fa-solid fa-bolt"></i> Spotlight Form Players</h4>
                <div class="players-grid">
                    ${allPlayers.slice(0, 4).map(p => `
                        <div class="player-card">
                            <div class="player-info">
                                <span class="player-name">${p.name}</span>
                                <span class="player-meta">${p.position || ''}</span>
                            </div>
                            <span class="player-form-badge">Form: ${typeof p.form === 'number' ? p.form.toFixed(1) : p.form}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    let reasonsHtml = '';
    if (match.reasons && match.reasons.length > 0) {
        reasonsHtml = `
            <div class="why-watch-section">
                <h4 class="section-title"><i class="fa-solid fa-circle-exclamation"></i> Match Analysis & Context</h4>
                <ul class="reasons-list">
                    ${match.reasons.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    const homeName = match.home_team.name || match.home_team;
    const awayName = match.away_team.name || match.away_team;
    const homeFlag = getFlagUrl(match.home_team);
    const awayFlag = getFlagUrl(match.away_team);
    const stageStr = match.stage || '';
    const dateStr = match.formatted_date || (match.formatted_time ? `${match.formatted_time}` : '');
    const headerSub = [stageStr, dateStr].filter(Boolean).join(' &bull; ');

    const compScore = match.watchability ? match.watchability.competitiveness : 50;
    const oddsScore = match.watchability ? match.watchability.odds : 50;
    const formScore = match.watchability ? match.watchability.form : 50;
    const narrScore = match.watchability ? match.watchability.narrative : 50;

    modalContainer.innerHTML = `
        <div class="modal-header">
            <span class="stage-tag group-click-link" style="cursor: ${match.group_name || match.stage === 'Regular Season' ? 'pointer' : 'default'}">${headerSub}</span>
            <div class="modal-match-title">
                <img src="${homeFlag}" class="modal-flag team-nav-link" data-name="${homeName}" alt="" style="cursor: pointer;">
                <span class="team-nav-link" data-name="${homeName}" style="cursor: pointer;">${homeName}</span>
                <span>vs</span>
                <span class="team-nav-link" data-name="${awayName}" style="cursor: pointer;">${awayName}</span>
                <img src="${awayFlag}" class="modal-flag team-nav-link" data-name="${awayName}" alt="" style="cursor: pointer;">
            </div>
            <div class="modal-watchability-header ${ratingClass}">
                <span class="score-val"><i class="${ratingIcon}"></i> ${ratingText}</span>
                <span class="score-label">${ratingText} WATCHABILITY</span>
            </div>
        </div>

        <div class="metrics-breakdown">
            <div class="metric-bar-group">
                <div class="metric-label-row">
                    <span>ELO Competitiveness</span>
                    <span>${compScore}%</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width: 0%" data-width="${compScore}%"></div>
                </div>
            </div>
            
            <div class="metric-bar-group">
                <div class="metric-label-row">
                    <span>Odds Competitiveness</span>
                    <span>${oddsScore}%</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width: 0%" data-width="${oddsScore}%"></div>
                </div>
            </div>
            
            <div class="metric-bar-group">
                <div class="metric-label-row">
                    <span>Player & Team Form</span>
                    <span>${formScore}%</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width: 0%" data-width="${formScore}%"></div>
                </div>
            </div>
            
            <div class="metric-bar-group">
                <div class="metric-label-row">
                    <span>Tournament Stakes</span>
                    <span>${narrScore}%</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width: 0%" data-width="${narrScore}%"></div>
                </div>
            </div>
        </div>

        ${reasonsHtml}
        ${playersHtml}
    `;

    // Bind navigation clicks inside modal
    const modalStageTag = modalContainer.querySelector('.stage-tag');
    if (modalStageTag && (match.group_name || match.stage === "Regular Season")) {
        modalStageTag.style.cursor = 'pointer';
        modalStageTag.addEventListener('click', () => {
            if (match.tournament_id) {
                localStorage.setItem('findfootball-tournament-id', match.tournament_id);
            }
            const targetPath = match.group_name ? match.group_name : 'standings';
            window.location.href = `/group/${targetPath}`;
        });
    }

    modalContainer.querySelectorAll('.team-nav-link').forEach(el => {
        el.addEventListener('click', () => {
            if (match.tournament_id) {
                localStorage.setItem('findfootball-tournament-id', match.tournament_id);
            }
            window.location.href = `/team/${encodeURIComponent(el.getAttribute('data-name'))}`;
        });
    });

    matchModal.classList.add('open');

    // Animate progress bars
    setTimeout(() => {
        const fills = modalContainer.querySelectorAll('.bar-fill');
        fills.forEach(fill => {
            fill.style.width = fill.getAttribute('data-width');
        });
    }, 100);
}

// Global modal close handling
document.addEventListener('DOMContentLoaded', () => {
    const matchModal = document.getElementById('match-modal');
    if (matchModal) {
        const modalClose = matchModal.querySelector('.modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                matchModal.classList.remove('open');
            });
        }
        window.addEventListener('click', (e) => {
            if (e.target === matchModal) {
                matchModal.classList.remove('open');
            }
        });
    }
});

// Attach canonical utilities to window
window.COUNTRY_FLAGS = COUNTRY_FLAGS;
window.getFlagUrl = getFlagUrl;
window.resolveTimezone = resolveTimezone;
window.getRatingClass = getRatingClass;
window.getRatingText = getRatingText;
window.getRatingIcon = getRatingIcon;
window.showToast = showToast;
window.openMatchDetails = openMatchDetails;
