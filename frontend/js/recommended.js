document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements

    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');

    // View Toggles
    const toggleScheduleBtn = document.getElementById('toggle-schedule-btn');
    const toggleLeaderboardBtn = document.getElementById('toggle-leaderboard-btn');
    const recommendedContainer = document.getElementById('recommended-container');



    // Modal
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local state
    let activeFixtures = null;
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';
    let activeView = localStorage.getItem('findfootball-rec-view') || 'schedule'; // 'schedule' or 'leaderboard'

    // Initialize Page
    selectedTimezone = localStorage.getItem('findfootball-timezone') || 'local';
    if (timezoneSelect) {
        timezoneSelect.value = selectedTimezone;
        // Timezone Switcher Event Listener
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
            localStorage.setItem('findfootball-rec-view', activeView);
            updateToggleButtonsUI();
            renderRecommended();
        });
    }

    if (toggleLeaderboardBtn) {
        toggleLeaderboardBtn.addEventListener('click', () => {
            activeView = 'leaderboard';
            localStorage.setItem('findfootball-rec-view', activeView);
            updateToggleButtonsUI();
            renderRecommended();
        });
    }

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();


    async function resolveAndTimezoneFetch() {
        resolvedTimezone = await resolveTimezone(selectedTimezone);
        fetchFixtures();
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



    // Fetch Recommended Fixtures
    async function fetchFixtures() {
        recommendedContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Fetching top tier matchups...</div>';
        try {
            const res = await fetch(`/api/fixtures/recommended?tz=${encodeURIComponent(resolvedTimezone)}`);
            activeFixtures = await res.json();
            renderRecommended();
        } catch (err) {
            console.error("Failed to load recommended fixtures", err);
            recommendedContainer.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading Hot List.</div>';
        }
    }

    // Render Logic based on Toggle Selection
    function renderRecommended() {
        recommendedContainer.innerHTML = '';
        if (!activeFixtures || activeFixtures.length === 0) {
            recommendedContainer.innerHTML = '<div class="loading-spinner"><p>No recommended fixtures available right now.</p></div>';
            return;
        }

        if (activeView === 'schedule') {
            renderScheduleView();
        } else {
            renderLeaderboardView();
        }
    }

    // View A: Date-grouped chronological grid
    function renderScheduleView() {
        // Sort chronologically by date
        const sorted = [...activeFixtures].sort((a, b) => new Date(a.date) - new Date(b.date));

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

            recommendedContainer.appendChild(section);
        });
    }

    // View B: Score-sorted flat leaderboard grid
    function renderLeaderboardView() {
        // Sort by watchability score descending
        const sorted = [...activeFixtures].sort((a, b) => b.watchability.overall - a.watchability.overall);

        const section = document.createElement('section');
        section.className = 'recommended-leaderboard-section';
        section.innerHTML = `<div class="recommended-grid"></div>`;

        const gridContainer = section.querySelector('.recommended-grid');
        sorted.forEach((match, index) => {
            const card = createMatchCard(match, true, index + 1);
            gridContainer.appendChild(card);
        });

        recommendedContainer.appendChild(section);
    }

    // Helper to generate a single match card
    function createMatchCard(match, showRank = false, rank = 1) {
        const ratingClass = getRatingClass(match.watchability.overall);
        const ratingText = match.watchability.tier || getRatingText(match.watchability.overall);
        const ratingIcon = getRatingIcon(match.watchability.overall);
        const contextLabel = match.watchability.context_label;
        const percentile = match.watchability.percentile;
        const topPctText = percentile ? `Top ${Math.max(1, Math.round(100 - percentile))}%` : '';

        const badgeHtml = match.competition_name
            ? `<span class="competition-badge" title="${match.competition_name}">${match.competition_badge || '⚽'} ${match.competition_name}</span>`
            : '';

        const card = document.createElement('div');
        card.className = `match-card ${ratingClass}`;

        card.innerHTML = `
            <div class="card-flag-bg home-flag-bg" style="background-image: url('${getFlagUrl(match.home_team.name, 'w320')}');"></div>
            <div class="card-flag-bg away-flag-bg" style="background-image: url('${getFlagUrl(match.away_team.name, 'w320')}');"></div>
            
            <div class="card-header">
                <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                    <span class="stage-tag">${match.stage}</span>
                    ${badgeHtml}
                    ${contextLabel ? `<span class="stage-tag" style="background: rgba(255,165,0,0.15); color: #ffaa00; border-color: rgba(255,165,0,0.4); font-weight: 600;"><i class="fa-solid fa-fire"></i> ${contextLabel}</span>` : ''}
                </div>
                <div class="header-badges">
                    ${showRank ? `<span class="rank-badge"><i class="fa-solid fa-fire"></i> Rank #${rank}</span>` : ''}
                    <span class="score-badge ${ratingClass}" title="${topPctText ? topPctText + ' overall' : ratingText}">
                        <i class="${ratingIcon}"></i> ${ratingText}${topPctText ? ` · ${topPctText}` : ''}
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

        // Navigate to group/standings page if stage tag clicked
        const stageTag = card.querySelector('.stage-tag');
        if (match.group_name || match.stage === "Regular Season") {
            stageTag.classList.add('clickable');
            stageTag.addEventListener('click', (e) => {
                e.stopPropagation();
                if (match.tournament_id) {
                    localStorage.setItem('findfootball-tournament-id', match.tournament_id);
                }
                const targetPath = match.group_name ? match.group_name : 'standings';
                window.location.href = `/group/${targetPath}`;
            });
        }

        // Click teams to navigate team detail pages
        card.querySelectorAll('.clickable-team').forEach(teamBox => {
            teamBox.addEventListener('click', (e) => {
                e.stopPropagation();
                const teamName = teamBox.getAttribute('data-name');
                if (match.tournament_id) {
                    localStorage.setItem('findfootball-tournament-id', match.tournament_id);
                }
                window.location.href = `/team/${encodeURIComponent(teamName)}`;
            });
        });

        card.addEventListener('click', () => openMatchDetails(match));
        return card;
    }

    // Toggle UI Styling Helper
    function updateToggleButtonsUI() {
        if (activeView === 'schedule') {
            toggleScheduleBtn.classList.add('active');
            toggleLeaderboardBtn.classList.remove('active');
        } else {
            toggleLeaderboardBtn.classList.add('active');
            toggleScheduleBtn.classList.remove('active');
        }
    }
});
