document.addEventListener('DOMContentLoaded', () => {
    // Country flag mapping using flagcdn codes
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
        "Democratic Republic of the Congo": "cd"
    };

    function getFlagUrl(countryName, size = 'w40') {
        const code = COUNTRY_FLAGS[countryName];
        if (code) {
            return `https://flagcdn.com/${size}/${code}.png`;
        }
        return 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"><circle cx="12" cy="12" r="10" fill="%23666"/></svg>';
    }

    // Parse Country name from URL path
    const pathParts = window.location.pathname.split('/');
    const countryName = decodeURIComponent(pathParts[pathParts.length - 1]);
    document.title = `${countryName} Profile | MatchWatch`;

    // DOM Elements
    const refreshBtn = document.getElementById('refresh-btn');
    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    
    const countryHero = document.getElementById('country-hero');
    const countryDashboard = document.getElementById('country-dashboard');
    const formIndicators = document.getElementById('country-form-indicators');
    const spotlightPlayersList = document.getElementById('spotlight-players-list');
    const countryMatchesContainer = document.getElementById('country-matches-container');

    // Modal
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local state
    let activeFixtures = null;
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';

    // Initialize Page
    selectedTimezone = localStorage.getItem('matchwatch-timezone') || 'local';
    timezoneSelect.value = selectedTimezone;



    // Timezone Switcher Event Listener
    timezoneSelect.addEventListener('change', () => {
        selectedTimezone = timezoneSelect.value;
        localStorage.setItem('matchwatch-timezone', selectedTimezone);
        resolveAndTimezoneFetch();
        showToast(`Timezone set to ${timezoneSelect.options[timezoneSelect.selectedIndex].text}!`);
    });

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    async function resolveAndTimezoneFetch() {
        if (selectedTimezone === 'local') {
            try {
                const geoRes = await fetch('https://ipapi.co/json/');
                if (geoRes.ok) {
                    const geoData = await geoRes.json();
                    if (geoData.timezone) {
                        resolvedTimezone = geoData.timezone;
                        console.log(`Detected timezone: ${resolvedTimezone}`);
                    } else {
                        throw new Error("Timezone missing");
                    }
                } else {
                    throw new Error("IP Service error");
                }
            } catch (err) {
                resolvedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
                console.log(`Fell back to browser timezone: ${resolvedTimezone}`);
            }
        } else {
            resolvedTimezone = selectedTimezone;
        }
        await fetchCountryDetails();
    }


    refreshBtn.addEventListener('click', async () => {
        if (!confirm("Are you sure you want to refresh the schedule database? This will reset all mock games and scores.")) return;
        try {
            refreshBtn.classList.add('fa-spin');
            const res = await fetch('/api/refresh', { method: 'POST' });
            if (res.ok) {
                showToast("Database refreshed successfully!");
                await fetchCountryDetails();
            }
        } catch (err) {
            console.error(err);
        } finally {
            refreshBtn.classList.remove('fa-spin');
        }
    });

    modalClose.addEventListener('click', () => {
        matchModal.classList.remove('open');
    });

    matchModal.addEventListener('click', (e) => {
        if (e.target === matchModal) {
            matchModal.classList.remove('open');
        }
    });


    // Fetch Country Profile data
    async function fetchCountryDetails() {
        try {
            const res = await fetch(`/api/country/${encodeURIComponent(countryName)}?tz=${encodeURIComponent(resolvedTimezone)}`);
            if (!res.ok) {
                countryHero.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Country profile not found.</div>';
                countryMatchesContainer.innerHTML = '';
                return;
            }
            const data = await res.json();
            
            renderHero(data);
            renderDashboard(data);
            renderSchedule(data.future_matches);
        } catch (err) {
            console.error("Failed to load country details", err);
            countryHero.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading country profile.</div>';
        }
    }

    function renderHero(data) {
        countryHero.innerHTML = `
            <div class="country-hero-flag-bg" style="background-image: url('${getFlagUrl(data.name, 'w320')}');"></div>
            <div class="country-hero-content">
                <div class="country-hero-header">
                    <img src="${getFlagUrl(data.name, 'w80')}" class="hero-avatar-flag" alt="">
                    <div>
                        <h2>${data.name.toUpperCase()}</h2>
                        <span class="group-rank-badge">
                            <i class="fa-solid fa-ranking-star"></i> Group ${data.group_name} &bull; Rank #${data.group_rank}
                        </span>
                    </div>
                </div>
                <div class="hero-elo-metric">
                    <span class="label">ENGINE ELO VALUE</span>
                    <span class="value">${data.elo}</span>
                </div>
            </div>
        `;
    }

    function renderDashboard(data) {
        // Form
        formIndicators.innerHTML = '';
        data.form.forEach(res => {
            const dot = document.createElement('div');
            dot.className = `form-dot-indicator ${res.toLowerCase()}`;
            dot.innerText = res;
            formIndicators.appendChild(dot);
        });

        // Spotlight players
        spotlightPlayersList.innerHTML = '';
        if (data.players.length === 0) {
            spotlightPlayersList.innerHTML = '<p class="text-muted">No form player details found.</p>';
        } else {
            data.players.forEach(p => {
                const playerCard = document.createElement('div');
                playerCard.className = 'player-form-row';
                playerCard.innerHTML = `
                    <div class="player-form-info">
                        <span class="player-name">${p.name}</span>
                        <span class="player-meta">${p.position}</span>
                    </div>
                    <div class="player-form-bar-wrapper">
                        <div class="player-form-bar-fill" style="width: ${p.form}%"></div>
                        <span class="player-form-percent">${p.form.toFixed(1)}</span>
                    </div>
                `;
                spotlightPlayersList.appendChild(playerCard);
            });
        }
        countryDashboard.style.display = 'grid';
    }

    function renderSchedule(matches) {
        countryMatchesContainer.innerHTML = '';
        if (matches.length === 0) {
            countryMatchesContainer.innerHTML = '<div class="loading-spinner"><p>No upcoming matches scheduled.</p></div>';
            return;
        }

        matches.forEach(match => {
            const ratingClass = getRatingClass(match.watchability.overall);
            const ratingText = getRatingText(match.watchability.overall);
            const ratingIcon = getRatingIcon(match.watchability.overall);
            
            const card = document.createElement('div');
            card.className = `match-card ${ratingClass}`;
            card.innerHTML = `
                <div class="card-flag-bg home-flag-bg" style="background-image: url('${getFlagUrl(match.home_team.name, 'w320')}');"></div>
                <div class="card-flag-bg away-flag-bg" style="background-image: url('${getFlagUrl(match.away_team.name, 'w320')}');"></div>
                <div class="tile-date-title"><i class="fa-regular fa-calendar"></i> ${match.formatted_date} &bull; ${match.formatted_time}</div>
                <div class="card-header">
                    <span class="stage-tag clickable" data-group="${match.group_name || ''}">${match.stage}</span>
                    <span class="score-badge ${ratingClass}">
                        <i class="${ratingIcon}"></i> ${ratingText}
                    </span>
                </div>
                <div class="card-matchup">
                    <div class="team-box home clickable-team" data-name="${match.home_team.name}">
                        <div class="team-identity home-identity">
                            <img src="${getFlagUrl(match.home_team.name)}" class="team-flag" alt="">
                            <span class="team-name" title="${match.home_team.name}">${match.home_team.name}</span>
                        </div>
                        <span class="elo-val">ELO ${match.home_team.elo}</span>
                    </div>
                    
                    <div class="match-info-center">
                        ${match.status === 'Finished' 
                            ? `<span class="match-score">${match.score}</span>` 
                            : (match.status === 'Live'
                                ? `<span class="match-score live">${match.score}</span><span class="live-indicator"><span class="live-dot"></span>Live</span>`
                                : `<span class="match-time">${match.formatted_time}</span>`
                              )
                        }
                        <span class="match-vs">vs</span>
                    </div>
                    
                    <div class="team-box away clickable-team" data-name="${match.away_team.name}">
                        <div class="team-identity away-identity">
                            <span class="team-name" title="${match.away_team.name}">${match.away_team.name}</span>
                            <img src="${getFlagUrl(match.away_team.name)}" class="team-flag" alt="">
                        </div>
                        <span class="elo-val">ELO ${match.away_team.elo}</span>
                    </div>
                </div>
                <div class="card-footer">
                    <div class="odds-row">
                        <span>H: <span class="odds-val">${match.odds.home.toFixed(2)}</span></span>
                        <span>D: <span class="odds-val">${match.odds.draw.toFixed(2)}</span></span>
                        <span>A: <span class="odds-val">${match.odds.away.toFixed(2)}</span></span>
                    </div>
                    ${match.reasons.length > 0 
                        ? `<p class="narrative-snippet"><i class="fa-solid fa-circle-info"></i> ${match.reasons[0]}</p>`
                        : ''
                    }
                </div>
            `;
            
            // Navigate to group page if stage tag clicked
            const stageTag = card.querySelector('.stage-tag');
            if (match.group_name) {
                stageTag.classList.add('clickable');
                stageTag.addEventListener('click', (e) => {
                    e.stopPropagation();
                    window.location.href = `/group/${match.group_name}`;
                });
            }

            // Click teams to navigate country pages
            card.querySelectorAll('.clickable-team').forEach(teamBox => {
                teamBox.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const teamName = teamBox.getAttribute('data-name');
                    window.location.href = `/country/${encodeURIComponent(teamName)}`;
                });
            });

            card.addEventListener('click', () => openMatchDetails(match));
            countryMatchesContainer.appendChild(card);
        });
    }

    // Modal Details Panel
    function openMatchDetails(match) {
        const ratingClass = getRatingClass(match.watchability.overall);
        const ratingText = getRatingText(match.watchability.overall);
        const ratingIcon = getRatingIcon(match.watchability.overall);
        
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
                                    <span class="player-meta">${p.position}</span>
                                </div>
                                <span class="player-form-badge">Form: ${p.form.toFixed(1)}</span>
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

        modalContainer.innerHTML = `
            <div class="modal-header">
                <span class="stage-tag group-click-link" style="cursor: ${match.group_name ? 'pointer' : 'default'}">${match.stage} &bull; ${match.formatted_date}</span>
                <div class="modal-match-title">
                    <img src="${getFlagUrl(match.home_team.name)}" class="modal-flag team-nav-link" data-name="${match.home_team.name}" alt="" style="cursor: pointer;">
                    <span class="team-nav-link" data-name="${match.home_team.name}" style="cursor: pointer;">${match.home_team.name}</span>
                    <span>vs</span>
                    <span class="team-nav-link" data-name="${match.away_team.name}" style="cursor: pointer;">${match.away_team.name}</span>
                    <img src="${getFlagUrl(match.away_team.name)}" class="modal-flag team-nav-link" data-name="${match.away_team.name}" alt="" style="cursor: pointer;">
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
                        <span>${match.watchability.competitiveness}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: 0%" data-width="${match.watchability.competitiveness}%"></div>
                    </div>
                </div>
                
                <div class="metric-bar-group">
                    <div class="metric-label-row">
                        <span>Odds Competitiveness</span>
                        <span>${match.watchability.odds}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: 0%" data-width="${match.watchability.odds}%"></div>
                    </div>
                </div>
                
                <div class="metric-bar-group">
                    <div class="metric-label-row">
                        <span>Player & Team Form</span>
                        <span>${match.watchability.form}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: 0%" data-width="${match.watchability.form}%"></div>
                    </div>
                </div>
                
                <div class="metric-bar-group">
                    <div class="metric-label-row">
                        <span>Tournament Stakes</span>
                        <span>${match.watchability.narrative}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: 0%" data-width="${match.watchability.narrative}%"></div>
                    </div>
                </div>
            </div>

            ${reasonsHtml}
            ${playersHtml}
        `;

        // Bind clicks in modal
        if (match.group_name) {
            modalContainer.querySelector('.stage-tag').addEventListener('click', () => {
                window.location.href = `/group/${match.group_name}`;
            });
        }

        modalContainer.querySelectorAll('.team-nav-link').forEach(el => {
            el.addEventListener('click', () => {
                window.location.href = `/country/${encodeURIComponent(el.getAttribute('data-name'))}`;
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

    function getRatingClass(score) {
        if (score >= 85) return 'must-watch';
        if (score >= 70) return 'recommended';
        if (score >= 50) return 'average';
        return 'skip';
    }

    function getRatingText(score) {
        if (score >= 85) return 'Must Watch';
        if (score >= 70) return 'Recommended';
        if (score >= 50) return 'Average';
        return 'Skip';
    }

    function getRatingIcon(score) {
        if (score >= 85) return 'fa-solid fa-trophy';
        if (score >= 70) return 'fa-solid fa-fire';
        if (score >= 50) return 'fa-solid fa-chart-simple';
        return 'fa-solid fa-face-meh';
    }

    function showToast(message) {
        toast.innerText = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
