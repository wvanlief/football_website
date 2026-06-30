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
        return 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAyNCAyNCcgd2lkdGg9JzI0JyBoZWlnaHQ9JzI0Jz48Y2lyY2xlIGN4PScxMicgY3k9JzEyJyByPScxMCcgZmlsbD0nIzY2NicvPjwvc3ZnPg==';
    }

    // Parse Group letter from URL path
    const pathParts = window.location.pathname.split('/');
    let activeGroup = decodeURIComponent(pathParts[pathParts.length - 1]).toUpperCase();

    // DOM Elements
    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    
    // View Toggles
    const toggleScheduleBtn = document.getElementById('toggle-schedule-btn');
    const toggleLeaderboardBtn = document.getElementById('toggle-leaderboard-btn');
    const groupMatchesContainer = document.getElementById('group-matches-container');
    const standingsTbody = document.getElementById('standings-tbody');

    // Modal
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local state
    let activeGroupData = null;
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';
    let activeView = localStorage.getItem('findfootball-group-view') || 'schedule'; // 'schedule' or 'leaderboard'

    // Initialize Page
    selectedTimezone = localStorage.getItem('findfootball-timezone') || 'local';
    if (timezoneSelect) {
        timezoneSelect.value = selectedTimezone;
        timezoneSelect.addEventListener('change', () => {
            selectedTimezone = timezoneSelect.value;
            localStorage.setItem('findfootball-timezone', selectedTimezone);
            resolveAndTimezoneFetch();
            showToast(`Timezone set to ${timezoneSelect.options[timezoneSelect.selectedIndex].text}!`);
        });
    }

    // Toggle Button States
    updateToggleButtonsUI();

    // View Toggle Listeners
    if (toggleScheduleBtn) {
        toggleScheduleBtn.addEventListener('click', () => {
            activeView = 'schedule';
            localStorage.setItem('findfootball-group-view', activeView);
            updateToggleButtonsUI();
            renderMatches();
        });
    }

    if (toggleLeaderboardBtn) {
        toggleLeaderboardBtn.addEventListener('click', () => {
            activeView = 'leaderboard';
            localStorage.setItem('findfootball-group-view', activeView);
            updateToggleButtonsUI();
            renderMatches();
        });
    }

    // Tab Navigation Logic
    const groupTabsNav = document.getElementById('group-tabs-nav');
    if (groupTabsNav) {
        groupTabsNav.querySelectorAll('.group-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const target = btn.getAttribute('data-group');
                switchToGroup(target);
            });
        });
    }

    function updateTabsUI() {
        if (!groupTabsNav) return;
        groupTabsNav.querySelectorAll('.group-tab-btn').forEach(btn => {
            if (btn.getAttribute('data-group') === activeGroup) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    function switchToGroup(groupName, pushState = true) {
        activeGroup = groupName.toUpperCase();
        updateTabsUI();
        
        if (activeGroup === 'THIRDS') {
            document.title = `Best 3rd Place Standings | findfootball.games`;
            document.getElementById('group-title-header').innerText = `BEST 3RD PLACE TEAMS`;
            document.getElementById('group-standings-section').style.display = 'none';
            document.getElementById('thirds-standings-section').style.display = 'block';
            document.getElementById('projected-knockout-card').style.display = 'none';
            
            // Hide matches container and toggle bar
            document.querySelector('.group-fixtures-section').style.display = 'none';
            
            if (pushState) {
                history.pushState({ group: 'thirds' }, '', `/group/thirds`);
            }
            fetchThirdsDetails();
        } else {
            document.title = `Group ${activeGroup} Standings | findfootball.games`;
            document.getElementById('group-title-header').innerText = `GROUP ${activeGroup}`;
            document.getElementById('group-standings-section').style.display = 'block';
            document.getElementById('thirds-standings-section').style.display = 'none';
            
            // Show matches container and toggle bar
            document.querySelector('.group-fixtures-section').style.display = 'block';
            
            if (pushState) {
                history.pushState({ group: activeGroup }, '', `/group/${activeGroup}`);
            }
            resolveAndTimezoneFetch();
        }
    }

    // Handle back/forward navigation
    window.addEventListener('popstate', (e) => {
        const pathParts = window.location.pathname.split('/');
        const letter = decodeURIComponent(pathParts[pathParts.length - 1]).toUpperCase();
        if (letter) {
            switchToGroup(letter, false);
        }
    });

    // Initialize tabs UI initial state
    updateTabsUI();

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
        
        if (activeGroup === 'THIRDS') {
            await fetchThirdsDetails();
        } else {
            await fetchGroupDetails();
        }
    }

    if (modalClose) {
        modalClose.addEventListener('click', () => {
            if (matchModal) matchModal.classList.remove('open');
        });
    }

    if (matchModal) {
        matchModal.addEventListener('click', (e) => {
            if (e.target === matchModal) {
                matchModal.classList.remove('open');
            }
        });
    }

    // Fetch Group details
    async function fetchGroupDetails() {
        try {
            const res = await fetch(`/api/group/${encodeURIComponent(activeGroup)}?tz=${encodeURIComponent(resolvedTimezone)}`);
            if (!res.ok) {
                groupMatchesContainer.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Group not found.</div>';
                return;
            }
            activeGroupData = await res.json();
            
            renderStandings(activeGroupData.standings);
            renderMatches();
            await fetchAndRenderProjectedMatches();
        } catch (err) {
            console.error("Failed to load group details", err);
            groupMatchesContainer.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading group.</div>';
        }
    }

    async function fetchThirdsDetails() {
        const thirdsTbody = document.getElementById('thirds-tbody');
        thirdsTbody.innerHTML = '<tr><td colspan="10" class="text-center"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading best 3rd standings...</td></tr>';
        
        try {
            const res = await fetch(`/api/group/thirds`);
            if (!res.ok) {
                thirdsTbody.innerHTML = '<tr><td colspan="10" class="text-danger text-center"><i class="fa-solid fa-triangle-exclamation"></i> Error loading standings.</td></tr>';
                return;
            }
            const data = await res.json();
            renderThirds(data);
        } catch (err) {
            console.error("Failed to load thirds standings", err);
            thirdsTbody.innerHTML = '<tr><td colspan="10" class="text-danger text-center"><i class="fa-solid fa-triangle-exclamation"></i> Error loading standings.</td></tr>';
        }
    }

    function renderThirds(thirds) {
        const thirdsTbody = document.getElementById('thirds-tbody');
        thirdsTbody.innerHTML = '';
        
        thirds.forEach((team, index) => {
            const rank = index + 1;
            const qualifyClass = rank <= 8 ? 'status-qualified-third' : 'status-eliminated-third';
            
            let statusHtml = '';
            if (team.status === 'Qualified' || (rank <= 8 && team.played >= 3)) {
                statusHtml = `<span class="qual-badge qualified"><i class="fa-solid fa-circle-check"></i> Qualified</span>`;
            } else if (team.status === 'Eliminated' || (rank > 8 && team.played >= 3)) {
                statusHtml = `<span class="qual-badge eliminated"><i class="fa-solid fa-circle-xmark"></i> Eliminated</span>`;
            } else {
                const prob = team.qualification_probability !== null ? team.qualification_probability : 50.0;
                statusHtml = `
                    <div class="chance-indicator-wrapper">
                        <span class="chance-val">${prob.toFixed(0)}% chance</span>
                    </div>
                `;
            }
            
            const tr = document.createElement('tr');
            tr.className = `standing-row ${qualifyClass}`;
            tr.innerHTML = `
                <td class="col-pos font-weight-bold">${rank}</td>
                <td class="col-team clickable-team-row" data-name="${team.name}">
                    <img src="${getFlagUrl(team.name)}" class="table-team-flag" alt="">
                    <span class="table-team-name">${team.name}</span>
                </td>
                <td class="col-stat font-weight-bold" style="color: var(--text-secondary);">Group ${team.group}</td>
                <td class="col-stat">${team.played}</td>
                <td class="col-stat">${team.won}</td>
                <td class="col-stat">${team.drawn}</td>
                <td class="col-stat">${team.lost}</td>
                <td class="col-stat">${team.goal_difference > 0 ? '+' : ''}${team.goal_difference}</td>
                <td class="col-pts font-weight-bold">${team.points}</td>
                <td class="col-status">${statusHtml}</td>
            `;
            
            tr.querySelector('.clickable-team-row').addEventListener('click', () => {
                window.location.href = `/country/${encodeURIComponent(team.name)}`;
            });
            
            thirdsTbody.appendChild(tr);
        });
    }

    async function fetchAndRenderProjectedMatches() {
        const projectedCard = document.getElementById('projected-knockout-card');
        const projectedContainer = document.getElementById('projected-matches-container');
        
        if (!projectedCard || !projectedContainer) return;
        
        if (activeGroup === 'THIRDS') {
            projectedCard.style.display = 'none';
            return;
        }
        
        projectedContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading projected matchups...</div>';
        
        try {
            const res = await fetch(`/api/bracket`);
            if (!res.ok) {
                projectedCard.style.display = 'none';
                return;
            }
            const data = await res.json();
            const groupTeams = activeGroupData.standings.map(t => t.name);
            
            const r32Matches = data.bracket.r32.filter(m => 
                (m.team1.name && groupTeams.includes(m.team1.name)) || 
                (m.team2.name && groupTeams.includes(m.team2.name))
            );
            
            if (r32Matches.length === 0) {
                projectedCard.style.display = 'none';
                return;
            }
            
            projectedCard.style.display = 'block';
            projectedContainer.innerHTML = '';
            
            r32Matches.forEach(match => {
                const matchEl = document.createElement('div');
                matchEl.className = 'projected-match-tile glass-dark';
                
                const t1 = match.team1;
                const t2 = match.team2;
                
                matchEl.innerHTML = `
                    <div class="projected-match-teams">
                        <div class="projected-team-row clickable-team" data-name="${t1.name}">
                            <img src="${getFlagUrl(t1.name)}" class="table-team-flag" alt="">
                            <span class="projected-team-name">${t1.name || "TBD"}</span>
                            <span class="projected-team-seed">(${t1.group_name || ""})</span>
                        </div>
                        <div class="projected-vs">vs</div>
                        <div class="projected-team-row clickable-team" data-name="${t2.name}">
                            <img src="${getFlagUrl(t2.name)}" class="table-team-flag" alt="">
                            <span class="projected-team-name">${t2.name || "TBD"}</span>
                            <span class="projected-team-seed">(${t2.group_name || ""})</span>
                        </div>
                    </div>
                    <div class="projected-match-footer">
                        <span class="projection-badge"><i class="fa-solid fa-robot"></i> Simulation Projection</span>
                    </div>
                `;
                
                matchEl.querySelectorAll('.clickable-team').forEach(el => {
                    el.addEventListener('click', () => {
                        const name = el.getAttribute('data-name');
                        if (name && name !== "TBD") {
                            window.location.href = `/country/${encodeURIComponent(name)}`;
                        }
                    });
                });
                
                projectedContainer.appendChild(matchEl);
            });
        } catch (err) {
            console.error("Failed to load projected matches", err);
            projectedCard.style.display = 'none';
        }
    }

    function renderStandings(standings) {
        standingsTbody.innerHTML = '';
        standings.forEach((team, index) => {
            const rank = index + 1;
            
            let statusHtml = '';
            let qualifyClass = '';
            
            if (team.status === 'Qualified') {
                statusHtml = `<span class="qual-badge qualified"><i class="fa-solid fa-circle-check"></i> Qualified</span>`;
                qualifyClass = 'status-qualified';
            } else if (team.status === 'Eliminated') {
                statusHtml = `<span class="qual-badge eliminated"><i class="fa-solid fa-circle-xmark"></i> Eliminated</span>`;
                qualifyClass = 'status-eliminated';
            } else {
                const prob = team.qualification_probability !== null ? team.qualification_probability : 50.0;
                let neededText = '';
                if (team.points_needed_top_2 !== null && team.points_needed_top_2 > 0) {
                    neededText = `<span class="needed-pts">Needs ${team.points_needed_top_2} pts</span>`;
                } else if (team.points_needed_top_2 === 0) {
                    neededText = `<span class="needed-pts text-success">Safe</span>`;
                }
                
                statusHtml = `
                    <div class="chance-indicator-wrapper">
                        <span class="chance-val">${prob.toFixed(0)}% chance</span>
                        ${neededText}
                    </div>
                `;
                
                if (prob >= 80) {
                    qualifyClass = 'status-highly-likely';
                } else if (prob <= 20) {
                    qualifyClass = 'status-unlikely';
                } else {
                    qualifyClass = 'status-contention';
                }
            }
            
            const tr = document.createElement('tr');
            tr.className = `standing-row ${qualifyClass}`;
            tr.innerHTML = `
                <td class="col-pos font-weight-bold">${rank}</td>
                <td class="col-team clickable-team-row" data-name="${team.name}">
                    <img src="${getFlagUrl(team.name)}" class="table-team-flag" alt="">
                    <span class="table-team-name">${team.name}</span>
                </td>
                <td class="col-stat">${team.played}</td>
                <td class="col-stat">${team.won}</td>
                <td class="col-stat">${team.drawn}</td>
                <td class="col-stat">${team.lost}</td>
                <td class="col-stat">${team.goal_difference > 0 ? '+' : ''}${team.goal_difference}</td>
                <td class="col-pts font-weight-bold">${team.points}</td>
                <td class="col-status">${statusHtml}</td>
            `;
            
            // Add click to navigate to country page
            tr.querySelector('.clickable-team-row').addEventListener('click', () => {
                window.location.href = `/country/${encodeURIComponent(team.name)}`;
            });
            
            standingsTbody.appendChild(tr);
        });
    }

    function renderMatches() {
        groupMatchesContainer.innerHTML = '';
        const fixtures = activeGroupData.fixtures;
        if (!fixtures || fixtures.length === 0) {
            groupMatchesContainer.innerHTML = '<div class="loading-spinner"><p>No matches scheduled in this group.</p></div>';
            return;
        }

        if (activeView === 'schedule') {
            renderScheduleView(fixtures);
        } else {
            renderLeaderboardView(fixtures);
        }
    }

    function renderScheduleView(fixtures) {
        // Sort chronologically
        const sorted = [...fixtures].sort((a, b) => new Date(a.date) - new Date(b.date));
        
        // Group by local date string
        const grouped = {};
        sorted.forEach(match => {
            const dateStr = match.formatted_date;
            if (!grouped[dateStr]) {
                grouped[dateStr] = [];
            }
            grouped[dateStr].push(match);
        });

        // Render each date section
        Object.keys(grouped).forEach(dateStr => {
            const matches = grouped[dateStr];
            
            const section = document.createElement('section');
            section.className = 'recommended-date-section';
            section.innerHTML = `
                <div class="recommended-date-header">
                    <h3><i class="fa-regular fa-calendar-days"></i> ${dateStr}</h3>
                </div>
                <div class="recommended-grid"></div>
            `;
            
            const gridContainer = section.querySelector('.recommended-grid');
            matches.forEach(match => {
                const card = createMatchCard(match, false);
                gridContainer.appendChild(card);
            });
            groupMatchesContainer.appendChild(section);
        });
    }

    function renderLeaderboardView(fixtures) {
        // Sort by watchability score descending
        const sorted = [...fixtures].sort((a, b) => b.watchability.overall - a.watchability.overall);

        const section = document.createElement('section');
        section.className = 'recommended-leaderboard-section';
        section.innerHTML = `<div class="recommended-grid"></div>`;
        
        const gridContainer = section.querySelector('.recommended-grid');
        sorted.forEach((match, index) => {
            const card = createMatchCard(match, true, index + 1);
            gridContainer.appendChild(card);
        });
        groupMatchesContainer.appendChild(section);
    }

    function createMatchCard(match, showRank = false, rank = 1) {
        const ratingClass = getRatingClass(match.watchability.overall);
        const ratingText = getRatingText(match.watchability.overall);
        const ratingIcon = getRatingIcon(match.watchability.overall);
        
        const card = document.createElement('div');
        card.className = `match-card ${ratingClass}`;
        card.innerHTML = `
            <div class="card-flag-bg home-flag-bg" style="background-image: url('${getFlagUrl(match.home_team.name, 'w320')}');"></div>
            <div class="card-flag-bg away-flag-bg" style="background-image: url('${getFlagUrl(match.away_team.name, 'w320')}');"></div>
            
            <div class="card-header">
                <span class="stage-tag">${match.stage}</span>
                <div class="header-badges">
                    ${showRank ? `<span class="rank-badge"><i class="fa-solid fa-fire"></i> Rank #${rank}</span>` : ''}
                    <span class="score-badge ${ratingClass}">
                        <i class="${ratingIcon}"></i> ${ratingText}
                    </span>
                </div>
            </div>
            
            ${showRank ? `<div class="tile-date-title"><i class="fa-regular fa-calendar"></i> ${match.formatted_date} &bull; ${match.formatted_time}</div>` : ''}
            
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
                <div class="card-extra-info">
                    ${match.reasons.length > 0 
                        ? `<p class="narrative-snippet"><i class="fa-solid fa-circle-info"></i> ${match.reasons[0]}</p>`
                        : ''
                    }
                </div>
            </div>
        `;

        card.querySelectorAll('.clickable-team').forEach(teamBox => {
            teamBox.addEventListener('click', (e) => {
                e.stopPropagation();
                window.location.href = `/country/${encodeURIComponent(teamBox.getAttribute('data-name'))}`;
            });
        });

        card.addEventListener('click', () => openMatchDetails(match));
        return card;
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
                <span class="stage-tag">${match.stage} &bull; ${match.formatted_date}</span>
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

    function updateToggleButtonsUI() {
        if (activeView === 'schedule') {
            toggleScheduleBtn.classList.add('active');
            toggleLeaderboardBtn.classList.remove('active');
        } else {
            toggleLeaderboardBtn.classList.add('active');
            toggleScheduleBtn.classList.remove('active');
        }
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
