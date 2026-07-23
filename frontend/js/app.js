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

    function getFlagUrl(target, size = 'w40') {
        if (!target) return '/static/badges/default.png';
        let url = null;
        if (typeof target === 'object') {
            url = target.logo_url;
            if (!url) target = target.name || target.team;
        }
        if (typeof target === 'string') {
            const code = COUNTRY_FLAGS[target];
            if (code) return `https://flagcdn.com/${size}/${code}.png`;
        }
        if (url) {
            if (url.startsWith('/static/badges/') && !url.endsWith('default.png')) {
                const matchId = url.match(/\/static\/badges\/(\d+)\.png/);
                if (matchId) {
                    return `https://media.api-sports.io/football/teams/${matchId[1]}.png`;
                }
            }
            return url;
        }
        return '/static/badges/default.png';
    }

    // DOM Elements

    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    const resultsBarContainer = document.getElementById('results-bar-container');
    const resultsListHorizontal = document.getElementById('results-list-horizontal');

    // Country Explorer elements
    const countrySearchInput = document.getElementById('country-search');
    const searchClearBtn = document.getElementById('search-clear');
    const flagCarouselContainer = document.getElementById('flag-carousel-container');



    // Columns
    const lists = {
        today: document.getElementById('list-today'),
        tomorrow: document.getElementById('list-tomorrow'),
        this_week: document.getElementById('list-week')
    };

    // Modal
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local state
    let activeFixtures = null;
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';
    let activeCompFilter = 'all';

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

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    // Initialize Country Selection Panel
    initCountryExplorer();


    async function resolveAndTimezoneFetch() {
        if (selectedTimezone === 'local') {
            try {
                // Check viewer country & timezone via free JSON geolocation API
                const geoRes = await fetch('https://ipapi.co/json/');
                if (geoRes.ok) {
                    const geoData = await geoRes.json();
                    if (geoData.timezone) {
                        resolvedTimezone = geoData.timezone;
                        console.log(`Detected timezone from IP lookup: ${resolvedTimezone} (${geoData.country_name})`);
                    } else {
                        throw new Error("Timezone field missing in geo response");
                    }
                } else {
                    throw new Error("Geo IP service response not ok");
                }
            } catch (err) {
                // Fallback to browser local timezone
                resolvedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
                console.log(`IP lookup failed, fell back to browser timezone: ${resolvedTimezone}`);
            }
        } else {
            resolvedTimezone = selectedTimezone;
        }
        await fetchFixtures();
    }

    // Event Listeners






    // Close Modal
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



    function getFormattedDateString(timezone, offsetDays = 0) {
        const d = new Date();
        if (offsetDays !== 0) {
            d.setDate(d.getDate() + offsetDays);
        }
        return new Intl.DateTimeFormat('en-US', {
            timeZone: timezone,
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        }).format(d);
    }

    // Fetch and Load Fixtures

    async function fetchFixtures() {
        const cachedSession = sessionStorage.getItem('findfootball-cached-fixtures');
        if (cachedSession) {
            try {
                activeFixtures = JSON.parse(cachedSession);
                renderAllColumns();
            } catch (e) {}
        } else {
            Object.keys(lists).forEach(col => {
                lists[col].innerHTML = `
                    <div class="skeleton-card-container" style="display: flex; flex-direction: column; gap: 12px; padding: 4px;">
                        <div style="height: 110px; background: rgba(255,255,255,0.03); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);"></div>
                        <div style="height: 110px; background: rgba(255,255,255,0.03); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);"></div>
                    </div>
                `;
            });
        }

        const todayHeader = document.querySelector('#col-today h2');
        const tomorrowHeader = document.querySelector('#col-tomorrow h2');
        if (todayHeader) todayHeader.textContent = getFormattedDateString(resolvedTimezone, 0);
        if (tomorrowHeader) tomorrowHeader.textContent = getFormattedDateString(resolvedTimezone, 1);

        try {
            const res = await fetch(`/api/fixtures?tz=${encodeURIComponent(resolvedTimezone)}`);
            const data = await res.json();
            activeFixtures = data;
            sessionStorage.setItem('findfootball-cached-fixtures', JSON.stringify(data));
            renderAllColumns();
        } catch (err) {
            console.error("Failed to load fixtures", err);
            if (!cachedSession) {
                Object.keys(lists).forEach(col => {
                    lists[col].innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading games.</div>';
                });
            }
        }
    }

    function renderResultsBar(fixtures) {
        if (!resultsBarContainer || !resultsListHorizontal) return;

        if (!fixtures || fixtures.length === 0) {
            resultsBarContainer.style.display = 'none';
            return;
        }

        resultsBarContainer.style.display = 'flex';
        resultsListHorizontal.innerHTML = '';

        fixtures.forEach(match => {
            const card = document.createElement('div');
            card.className = 'result-ticker-card';
            card.title = `${match.home_team.name} vs ${match.away_team.name}`;
            card.innerHTML = `
                <div class="ticker-team home">
                    <img src="${getFlagUrl(match.home_team)}" class="ticker-flag" alt="${match.home_team.name}" title="${match.home_team.name}">
                </div>
                <div class="score-wrapper blurred" title="Click to reveal score">
                    <span class="score-text">${match.score}</span>
                    <div class="score-blur-overlay">Reveal</div>
                </div>
                <div class="ticker-team away">
                    <img src="${getFlagUrl(match.away_team)}" class="ticker-flag" alt="${match.away_team.name}" title="${match.away_team.name}">
                </div>
            `;

            const scoreWrapper = card.querySelector('.score-wrapper');
            scoreWrapper.addEventListener('click', (e) => {
                e.stopPropagation();
                scoreWrapper.classList.toggle('blurred');
            });

            card.addEventListener('click', () => openMatchDetails(match));
            resultsListHorizontal.appendChild(card);
        });
    }



    function renderAllColumns() {
        if (!activeFixtures) return;
        
        let noticeBanner = document.getElementById('offseason-notice-banner');
        if (activeFixtures.is_offseason && activeFixtures.offseason_notice) {
            if (!noticeBanner) {
                noticeBanner = document.createElement('div');
                noticeBanner.id = 'offseason-notice-banner';
                noticeBanner.className = 'glass';
                noticeBanner.style.cssText = 'padding: 12px 20px; margin-bottom: 1rem; border: 1px solid rgba(251, 191, 36, 0.4); background: rgba(251, 191, 36, 0.1); border-radius: 12px; color: #fbbf24; font-weight: 600; display: flex; align-items: center; gap: 10px;';
                const triptychContainer = document.querySelector('.triptych-container');
                if (triptychContainer) {
                    triptychContainer.parentNode.insertBefore(noticeBanner, triptychContainer);
                }
            }
            noticeBanner.innerHTML = `<i class="fa-solid fa-umbrella-beach"></i> <span>${activeFixtures.offseason_notice}</span>`;
            noticeBanner.style.display = 'flex';
        } else if (noticeBanner) {
            noticeBanner.style.display = 'none';
        }
        
        const filterFn = (match) => {
            if (activeCompFilter === 'all' || activeCompFilter === 'upcoming') {
                return true;
            }
            return match.competition_name === activeCompFilter;
        };

        const filteredToday = activeFixtures.today.filter(filterFn);
        const filteredTomorrow = activeFixtures.tomorrow.filter(filterFn);
        const filteredWeek = activeFixtures.this_week.filter(filterFn);
        const filteredFinished = activeFixtures.finished.filter(filterFn);

        renderColumn(lists.today, filteredToday, false);
        renderColumn(lists.tomorrow, filteredTomorrow, false);
        renderColumn(lists.this_week, filteredWeek, true);
        renderResultsBar(filteredFinished);
    }

    // Render a list of fixtures in a column
    function renderColumn(container, fixtures, showDate = false) {
        container.innerHTML = '';
        if (fixtures.length === 0) {
            container.innerHTML = '<div class="loading-spinner"><p>No matches scheduled.</p></div>';
            return;
        }

        fixtures.forEach(match => {
            const ratingClass = getRatingClass(match.watchability.overall);
            const ratingText = getRatingText(match.watchability.overall);
            const ratingIcon = getRatingIcon(match.watchability.overall);

            const badgeHtml = match.competition_name
                ? `<span class="competition-badge" title="${match.competition_name}">${match.competition_badge || '⚽'} ${match.competition_name}</span>`
                : '';

            const card = document.createElement('div');
            card.className = `match-card ${ratingClass}`;
            card.innerHTML = `
                <div class="card-flag-bg home-flag-bg" style="background-image: url('${getFlagUrl(match.home_team, 'w320')}');"></div>
                <div class="card-flag-bg away-flag-bg" style="background-image: url('${getFlagUrl(match.away_team, 'w320')}');"></div>
                ${showDate ? `<div class="tile-date-title"><i class="fa-regular fa-calendar"></i> ${match.formatted_date}</div>` : ''}
                <div class="card-header">
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span class="stage-tag">${match.stage}</span>
                        ${badgeHtml}
                    </div>
                    <span class="score-badge ${ratingClass}">
                        <i class="${ratingIcon}"></i> ${ratingText}
                    </span>
                </div>
                <div class="card-matchup">
                    <div class="team-box home clickable-team" data-name="${match.home_team.name}">
                        <div class="team-identity home-identity">
                            <img src="${getFlagUrl(match.home_team)}" class="team-flag" alt="">
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
                            <img src="${getFlagUrl(match.away_team)}" class="team-flag" alt="">
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
            container.appendChild(card);
        });
    }

    // Modal Details Panel
    function openMatchDetails(match) {
        const ratingClass = getRatingClass(match.watchability.overall);
        const ratingText = getRatingText(match.watchability.overall);
        const ratingIcon = getRatingIcon(match.watchability.overall);

        // Spotlight Players Render
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

        // Reasons HTML
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

        // Animate the progress bars inside the modal
        setTimeout(() => {
            const fills = modalContainer.querySelectorAll('.bar-fill');
            fills.forEach(fill => {
                fill.style.width = fill.getAttribute('data-width');
            });
        }, 100);
    }

    // Country Explorer Functions
    async function initCountryExplorer() {
        if (!flagCarouselContainer) return;

        try {
            const res = await fetch('/api/country');
            if (!res.ok) throw new Error("Failed to fetch countries list");

            const countries = await res.json();
            renderCountryCarousel(countries);
            renderCompetitionPills(countries);
            setupSearchFiltering();
        } catch (err) {
            console.error("Error initializing Country Explorer:", err);
            flagCarouselContainer.innerHTML = '<p class="text-muted" style="padding: 0.5rem 1rem;">Failed to load countries.</p>';
        }
    }

    function renderCountryCarousel(countries) {
        flagCarouselContainer.innerHTML = '';
        countries.forEach(country => {
            const pill = document.createElement('div');
            pill.className = 'flag-pill';
            pill.setAttribute('data-name', country.name.toLowerCase());
            pill.setAttribute('data-competition', country.competition_name || '');
            pill.setAttribute('data-upcoming', country.has_upcoming_game ? 'true' : 'false');
            
            if (country.has_upcoming_game) {
                pill.style.border = '1px solid rgba(251, 191, 36, 0.6)';
                pill.style.boxShadow = '0 0 10px rgba(251, 191, 36, 0.2)';
            }
            
            let badgeText = country.competition_badge || '⚽';
            let titleText = `${country.name} (ELO ${country.elo})`;
            if (country.competition_name) {
                titleText += `\n${badgeText} ${country.competition_name}`;
            }
            if (country.has_upcoming_game) {
                titleText += `\n🔥 Match in next 7 days`;
            }
            
            pill.title = titleText;
            pill.innerHTML = `
                <img src="${getFlagUrl(country)}" class="flag-pill-img" alt="${country.name} flag">
            `;
            pill.addEventListener('click', () => {
                if (country.tournament_id) {
                    localStorage.setItem('findfootball-tournament-id', country.tournament_id);
                }
                window.location.href = `/team/${encodeURIComponent(country.name)}`;
            });
            flagCarouselContainer.appendChild(pill);
        });
    }

    function renderCompetitionPills(countries) {
        const compFiltersContainer = document.getElementById('explorer-comp-filters');
        if (!compFiltersContainer) return;

        // Get unique competitions
        const competitions = [];
        const compNames = new Set();
        countries.forEach(c => {
            if (c.competition_name && !compNames.has(c.competition_name)) {
                compNames.add(c.competition_name);
                competitions.push({
                    name: c.competition_name,
                    badge: c.competition_badge,
                    tournamentId: c.tournament_id
                });
            }
        });

        compFiltersContainer.innerHTML = '';

        const createPill = (label, value) => {
            const btn = document.createElement('button');
            btn.className = `comp-filter-pill${activeCompFilter === value ? ' active' : ''}`;
            btn.innerHTML = label;
            btn.addEventListener('click', () => {
                compFiltersContainer.querySelectorAll('.comp-filter-pill').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeCompFilter = value;
                applyExplorerFilters();
                renderAllColumns();
            });
            return btn;
        };

        compFiltersContainer.appendChild(createPill('⚽ All Active', 'all'));
        compFiltersContainer.appendChild(createPill('🔥 Next 7 Days', 'upcoming'));

        competitions.forEach(comp => {
            compFiltersContainer.appendChild(createPill(`${comp.badge || '⚽'} ${comp.name}`, comp.name));
        });
    }

    function applyExplorerFilters() {
        const query = countrySearchInput ? countrySearchInput.value.trim().toLowerCase() : '';
        const pills = flagCarouselContainer.querySelectorAll('.flag-pill');

        pills.forEach(pill => {
            const name = pill.getAttribute('data-name');
            const comp = pill.getAttribute('data-competition');
            const upcoming = pill.getAttribute('data-upcoming') === 'true';

            let matchesQuery = name.includes(query);
            let matchesComp = false;

            if (activeCompFilter === 'all') {
                matchesComp = true;
            } else if (activeCompFilter === 'upcoming') {
                matchesComp = upcoming;
            } else {
                matchesComp = (comp === activeCompFilter);
            }

            if (matchesQuery && matchesComp) {
                pill.classList.remove('hidden');
            } else {
                pill.classList.add('hidden');
            }
        });
    }

    function setupSearchFiltering() {
        if (!countrySearchInput) return;

        countrySearchInput.addEventListener('input', () => {
            const query = countrySearchInput.value.trim().toLowerCase();
            if (searchClearBtn) {
                searchClearBtn.style.display = query ? 'flex' : 'none';
            }
            applyExplorerFilters();
        });

        if (searchClearBtn) {
            searchClearBtn.addEventListener('click', () => {
                countrySearchInput.value = '';
                searchClearBtn.style.display = 'none';
                applyExplorerFilters();
                countrySearchInput.focus();
            });
        }
    }

    // Helper functions for formatting rating categories
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
