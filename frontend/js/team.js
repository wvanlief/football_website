document.addEventListener('DOMContentLoaded', () => {
    // Parse Team name from URL path
    const pathParts = window.location.pathname.split('/');
    const teamName = decodeURIComponent(pathParts[pathParts.length - 1]);
    document.title = `${teamName} Profile | findfootball.games`;

    // DOM Elements
    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    
    const teamHero = document.getElementById('team-hero');
    const teamDashboard = document.getElementById('team-dashboard');
    const formIndicators = document.getElementById('team-form-indicators');
    const spotlightPlayersList = document.getElementById('spotlight-players-list');
    const teamMatchesContainer = document.getElementById('team-matches-container');

    // Modal
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local state
    let activeFixtures = null;
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';

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

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    async function resolveAndTimezoneFetch() {
        resolvedTimezone = await resolveTimezone(selectedTimezone);
        await fetchTeamDetails();
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

    // Fetch Team Profile data
    async function fetchTeamDetails() {
        try {
            const tournamentId = localStorage.getItem('findfootball-tournament-id') || '';
            const url = `/api/country/${encodeURIComponent(teamName)}?tz=${encodeURIComponent(resolvedTimezone)}${tournamentId ? `&tournament_id=${tournamentId}` : ''}`;
            const res = await fetch(url);
            
            if (!res.ok) {
                teamHero.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Team profile not found.</div>';
                teamMatchesContainer.innerHTML = '';
                return;
            }
            const data = await res.json();
            
            renderHero(data);
            renderDashboard(data);
            renderSchedule(data.future_matches);
        } catch (err) {
            console.error("Failed to load team details", err);
            teamHero.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading team profile.</div>';
        }
    }

    function renderHero(data) {
        let badgeHtml = '';
        if (data.group_name) {
            badgeHtml = `<i class="fa-solid fa-ranking-star"></i> Group ${data.group_name} &bull; Rank #${data.group_rank}`;
        } else if (data.group_rank) {
            badgeHtml = `<i class="fa-solid fa-ranking-star"></i> Standings Rank #${data.group_rank}`;
        } else {
            badgeHtml = `<i class="fa-solid fa-shield-halved"></i> Active Participant`;
        }

        let scoringBadge = '';
        if (data.is_high_scoring) {
            scoringBadge = `<span class="group-rank-badge high-scoring-badge" style="background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.4); color: #fbbf24; margin-top: 0.4rem; display: inline-flex; align-items: center; gap: 4px;"><i class="fa-solid fa-fire"></i> High-Scoring Attack (avg: ${data.avg_goals_scored.toFixed(2)})</span>`;
        }

        teamHero.innerHTML = `
            <div class="country-hero-flag-bg" style="background-image: url('${getFlagUrl(data, 'w320')}');"></div>
            <div class="country-hero-content">
                <div class="country-hero-header">
                    <img src="${getFlagUrl(data, 'w80')}" class="hero-avatar-flag" alt="">
                    <div>
                        <h2>${data.name.toUpperCase()}</h2>
                        <div style="display: flex; flex-direction: column; align-items: flex-start;">
                            <span class="group-rank-badge">
                                ${badgeHtml}
                            </span>
                            ${scoringBadge}
                        </div>
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
        if (data.form && data.form.length > 0) {
            data.form.forEach(res => {
                const dot = document.createElement('div');
                dot.className = `form-dot-indicator ${res.toLowerCase()}`;
                dot.innerText = res;
                formIndicators.appendChild(dot);
            });
        } else {
            formIndicators.innerHTML = '<p class="text-muted">No recent match results.</p>';
        }

        // Spotlight players
        spotlightPlayersList.innerHTML = '';
        if (!data.players || data.players.length === 0) {
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
        teamDashboard.style.display = 'grid';
    }

    function renderSchedule(matches) {
        teamMatchesContainer.innerHTML = '';
        if (matches.length === 0) {
            teamMatchesContainer.innerHTML = '<div class="loading-spinner"><p>No upcoming matches scheduled.</p></div>';
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
                    <span class="stage-tag">${match.stage}</span>
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
            
            // Navigate to group/standings page if stage tag clicked
            const stageTag = card.querySelector('.stage-tag');
            if (match.group_name) {
                stageTag.classList.add('clickable');
                stageTag.addEventListener('click', (e) => {
                    e.stopPropagation();
                    window.location.href = `/group/${match.group_name}`;
                });
            }

            // Click teams to navigate team pages
            card.querySelectorAll('.clickable-team').forEach(teamBox => {
                teamBox.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const name = teamBox.getAttribute('data-name');
                    window.location.href = `/team/${encodeURIComponent(name)}`;
                });
            });

            card.addEventListener('click', () => openMatchDetails(match));
            teamMatchesContainer.appendChild(card);
        });
    }
});
