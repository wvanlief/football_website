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
    let lastFeedUpdatedAt = null;

    function formatRelativeTime(dateStr) {
        if (!dateStr) return 'Live Sync';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return 'Live Sync';
        const now = new Date();
        const diffSeconds = Math.max(0, Math.floor((now - date) / 1000));
        
        if (diffSeconds < 60) {
            return 'Data updated just now';
        }
        const diffMinutes = Math.floor(diffSeconds / 60);
        if (diffMinutes === 1) {
            return 'Data updated 1 min ago';
        }
        if (diffMinutes < 60) {
            return `Data updated ${diffMinutes} min ago`;
        }
        const diffHours = Math.floor(diffMinutes / 60);
        if (diffHours === 1) {
            return 'Data updated 1 hr ago';
        }
        if (diffHours < 24) {
            return `Data updated ${diffHours} hrs ago`;
        }
        const diffDays = Math.floor(diffHours / 24);
        return `Data updated ${diffDays}d ago`;
    }

    function updateFreshnessIndicator() {
        const freshnessEl = document.getElementById('freshness-text');
        if (!freshnessEl) return;
        if (!lastFeedUpdatedAt) {
            freshnessEl.textContent = 'Live Sync';
            return;
        }
        freshnessEl.textContent = formatRelativeTime(lastFeedUpdatedAt);
    }

    // Periodically update freshness relative text
    setInterval(updateFreshnessIndicator, 30000);

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

    function processHydratedFixtures(fixturesList, userTz) {
        let todayFixtures = [];
        let tomorrowFixtures = [];
        let weekFixtures = [];
        let finishedFixtures = [];
        let scheduledFixtures = [];

        let now = new Date();
        let todayStr = new Intl.DateTimeFormat('en-CA', { timeZone: userTz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
        
        let tomorrowDate = new Date(now);
        tomorrowDate.setDate(tomorrowDate.getDate() + 1);
        let tomorrowStr = new Intl.DateTimeFormat('en-CA', { timeZone: userTz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(tomorrowDate);

        let maxDate = new Date(now);
        maxDate.setDate(maxDate.getDate() + 8);
        let maxDateStr = new Intl.DateTimeFormat('en-CA', { timeZone: userTz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(maxDate);

        (fixturesList || []).forEach(fdata => {
            let matchDateStr = todayStr;
            if (fdata.date) {
                try {
                    let d = new Date(fdata.date);
                    matchDateStr = new Intl.DateTimeFormat('en-CA', { timeZone: userTz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
                } catch(e) {}
            }

            if (fdata.status === "Finished") {
                finishedFixtures.push(fdata);
                return;
            }

            if (matchDateStr >= todayStr) {
                scheduledFixtures.push({ matchDateStr, fdata });
            }

            if (matchDateStr === todayStr) {
                todayFixtures.push(fdata);
            } else if (matchDateStr === tomorrowStr) {
                tomorrowFixtures.push(fdata);
            } else if (matchDateStr > tomorrowStr && matchDateStr <= maxDateStr) {
                weekFixtures.push(fdata);
            }
        });

        // Sort today and tomorrow by ascending kick-off time
        todayFixtures.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
        tomorrowFixtures.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
        // Sort finished descending by date
        finishedFixtures.sort((a, b) => (b.date || "").localeCompare(a.date || ""));

        let isOffseason = false;
        let offseasonNotice = null;

        if (todayFixtures.length === 0 && tomorrowFixtures.length === 0 && weekFixtures.length === 0 && scheduledFixtures.length > 0) {
            isOffseason = true;
            scheduledFixtures.sort((a, b) => a.matchDateStr.localeCompare(b.matchDateStr));
            let firstMatchDate = scheduledFixtures[0].matchDateStr;
            
            // Calculate 8-day block starting from firstMatchDate
            let firstDateObj = new Date(firstMatchDate + 'T00:00:00');
            let blockEndDateObj = new Date(firstDateObj);
            blockEndDateObj.setDate(blockEndDateObj.getDate() + 8);
            let blockEndDateStr = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(blockEndDateObj);

            let upcomingBlock = [];
            scheduledFixtures.forEach(item => {
                if (item.matchDateStr >= firstMatchDate && item.matchDateStr <= blockEndDateStr) {
                    upcomingBlock.push(item.fdata);
                }
            });
            upcomingBlock.sort((a, b) => ((b.watchability && b.watchability.overall) || 0) - ((a.watchability && a.watchability.overall) || 0));
            weekFixtures = upcomingBlock.slice(0, 8);

            let formattedFirstDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(firstDateObj);
            offseasonNotice = `Off-season: Showing next upcoming matches starting ${formattedFirstDate}.`;
        } else {
            let highQualityGems = weekFixtures.filter(f => (f.watchability && f.watchability.overall >= 70.0));
            highQualityGems.sort((a, b) => ((b.watchability && b.watchability.overall) || 0) - ((a.watchability && a.watchability.overall) || 0));
            if (highQualityGems.length >= 3) {
                weekFixtures = highQualityGems.slice(0, 8);
            } else {
                weekFixtures.sort((a, b) => ((b.watchability && b.watchability.overall) || 0) - ((a.watchability && a.watchability.overall) || 0));
                weekFixtures = weekFixtures.slice(0, 5);
            }
        }

        return {
            today: todayFixtures,
            tomorrow: tomorrowFixtures,
            this_week: weekFixtures,
            finished: finishedFixtures.slice(0, 30),
            is_offseason: isOffseason,
            offseason_notice: offseasonNotice
        };
    }

    async function fetchFixtures() {
        const todayHeader = document.querySelector('#col-today h2');
        const tomorrowHeader = document.querySelector('#col-tomorrow h2');
        if (todayHeader) todayHeader.textContent = getFormattedDateString(resolvedTimezone, 0);
        if (tomorrowHeader) tomorrowHeader.textContent = getFormattedDateString(resolvedTimezone, 1);

        const hydratedElement = document.getElementById('initial-fixtures-data');
        if (hydratedElement && hydratedElement.textContent.trim()) {
            try {
                const parsed = JSON.parse(hydratedElement.textContent);
                if (parsed && parsed.fixtures && parsed.fixtures.length > 0) {
                    activeFixtures = processHydratedFixtures(parsed.fixtures, resolvedTimezone);
                    if (parsed.updated_at) {
                        lastFeedUpdatedAt = parsed.updated_at;
                        updateFreshnessIndicator();
                    }
                    renderAllColumns();
                    return;
                }
            } catch(e) {
                console.warn("Failed to parse inline hydrated fixtures:", e);
            }
        }

        const cacheKey = 'findfootball-cached-fixtures-v5';
        const cachedSession = sessionStorage.getItem(cacheKey);

        if (cachedSession) {
            try {
                activeFixtures = JSON.parse(cachedSession);
                if (activeFixtures && activeFixtures.updated_at) {
                    lastFeedUpdatedAt = activeFixtures.updated_at;
                    updateFreshnessIndicator();
                }
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

        try {
            const res = await fetch(`/api/fixtures?tz=${encodeURIComponent(resolvedTimezone)}`);
            const data = await res.json();
            activeFixtures = data;
            if (data && data.updated_at) {
                lastFeedUpdatedAt = data.updated_at;
                updateFreshnessIndicator();
            }
            sessionStorage.setItem(cacheKey, JSON.stringify(data));
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

        renderHeroSpotlight(filteredToday, filteredWeek, filteredTomorrow);
        renderColumn(lists.today, filteredToday, false, 'Today');
        renderColumn(lists.tomorrow, filteredTomorrow, false, 'Tomorrow');
        renderColumn(lists.this_week, filteredWeek, true, 'This Week');
        renderResultsBar(filteredFinished);

        window.openMatchInSideInspector = openMatchInSideInspector;
        window.openMatchDetails = openMatchDetails;
        window.getFlagUrl = getFlagUrl;
    }

    // Curated Fallbacks when local database is off-season or has sparse fixtures
    const HERO_FALLBACK_TODAY = [
        {
            home_team: { name: 'Spain', elo: 2064 },
            away_team: { name: 'Argentina', elo: 2095 },
            competition_name: 'Finalissima',
            competition_badge: '🏆',
            formatted_time: '19:00',
            stage: 'Grand Final',
            watchability: { overall: 92 },
            odds: { home: 2.35, draw: 3.25, away: 2.85 },
            reasons: ['World Champions Clash: Reigning Euro Champions Spain vs World Cup Champions Argentina.']
        },
        {
            home_team: { name: 'Arsenal', elo: 1985 },
            away_team: { name: 'Chelsea', elo: 1940 },
            competition_name: 'Premier League',
            competition_badge: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
            formatted_time: '17:30',
            stage: 'Matchday 4',
            watchability: { overall: 88 },
            odds: { home: 1.95, draw: 3.60, away: 3.80 },
            reasons: ['London Derby with high xG output & title race implications.']
        },
        {
            home_team: { name: 'Real Madrid', elo: 2040 },
            away_team: { name: 'Bayern Munich', elo: 2010 },
            competition_name: 'Champions League',
            competition_badge: '⭐',
            formatted_time: '21:00',
            stage: 'Semi-Final',
            watchability: { overall: 86 },
            odds: { home: 2.10, draw: 3.50, away: 3.30 },
            reasons: ['European Classic: 20 European Cups combined in heavyweight clash.']
        }
    ];

    const HERO_FALLBACK_WEEK = [
        {
            home_team: { name: 'Manchester City', elo: 2055 },
            away_team: { name: 'Liverpool', elo: 2015 },
            competition_name: 'Premier League',
            competition_badge: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
            formatted_time: 'Wed 20:00',
            stage: 'Matchday 5',
            watchability: { overall: 91 },
            odds: { home: 2.05, draw: 3.65, away: 3.40 },
            reasons: ['Top of the table title clash featuring two top-3 attack lines.']
        },
        {
            home_team: { name: 'Inter Milan', elo: 1970 },
            away_team: { name: 'Juventus', elo: 1950 },
            competition_name: 'Serie A',
            competition_badge: '🇮🇹',
            formatted_time: 'Fri 20:45',
            stage: 'Derby d\'Italia',
            watchability: { overall: 87 },
            odds: { home: 2.20, draw: 3.15, away: 3.40 },
            reasons: ['Derby d\'Italia with ultra-close ELO differential and high tactical drama.']
        }
    ];

    // 'Best Match Today' Hero Component (Issue #67)
    function renderHeroSpotlight(todayFixtures, weekFixtures, tomorrowFixtures) {
        const mount = document.getElementById('hero-match-spotlight');
        if (!mount) return;

        const sortByScore = (list) => [...list].sort((a, b) => {
            const scoreA = (a.watchability && a.watchability.overall) || a.watchability_score || 0;
            const scoreB = (b.watchability && b.watchability.overall) || b.watchability_score || 0;
            return scoreB - scoreA;
        });

        let todayList = (todayFixtures && todayFixtures.length > 0) ? sortByScore(todayFixtures).slice(0, 3) : [];
        if (todayList.length < 3) {
            todayList = HERO_FALLBACK_TODAY;
        }

        let weekList = (weekFixtures && weekFixtures.length > 0) ? sortByScore(weekFixtures).slice(0, 2) : [];
        if (weekList.length < 2 && tomorrowFixtures && tomorrowFixtures.length > 0) {
            weekList = sortByScore(tomorrowFixtures).slice(0, 2);
        }
        if (weekList.length < 2) {
            weekList = HERO_FALLBACK_WEEK;
        }

        const topToday = todayList[0] || HERO_FALLBACK_TODAY[0];
        const today2 = todayList[1] || HERO_FALLBACK_TODAY[1];
        const today3 = todayList[2] || HERO_FALLBACK_TODAY[2];

        const topWeek = weekList[0] || HERO_FALLBACK_WEEK[0];
        const week2 = weekList[1] || HERO_FALLBACK_WEEK[1];

        const topTodayScore = Math.round(topToday.watchability?.overall || 92);
        const topTodayClass = getRatingClass(topTodayScore);
        const topHomeFlag = getFlagUrl(topToday.home_team, 'w320');
        const topAwayFlag = getFlagUrl(topToday.away_team, 'w320');

        const topWeekScore = Math.round(topWeek.watchability?.overall || 91);
        const topWeekClass = getRatingClass(topWeekScore);
        const weekHomeFlag = getFlagUrl(topWeek.home_team, 'w320');
        const weekAwayFlag = getFlagUrl(topWeek.away_team, 'w320');

        const renderVertCard = (m, rank) => {
            const score = Math.round(m.watchability?.overall || 85);
            const rClass = getRatingClass(score);
            const hFlag = getFlagUrl(m.home_team, 'w320');
            const aFlag = getFlagUrl(m.away_team, 'w320');

            return `
                <div class="hero-card-base hero-vert-card ${rClass}" data-match-data='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
                    <div class="hero-flag-bg home" style="background-image: url('${hFlag}');"></div>
                    <div class="hero-flag-bg away" style="background-image: url('${aFlag}');"></div>

                    <div class="hero-card-header">
                        <span class="hero-kicker-tag">#${rank} · ${m.competition_name || 'League'}</span>
                        <span class="hero-score-badge ${rClass}">${score}%</span>
                    </div>

                    <div class="hero-vert-matchup">
                        <div class="hero-vert-team-row">
                            <img src="${getFlagUrl(m.home_team)}" class="hero-crest-img" alt="">
                            <span>${m.home_team.name}</span>
                        </div>
                        <div class="hero-vert-team-row">
                            <img src="${getFlagUrl(m.away_team)}" class="hero-crest-img" alt="">
                            <span>${m.away_team.name}</span>
                        </div>
                    </div>

                    <div class="hero-vert-footer">
                        <span><i class="fa-regular fa-clock"></i> ${m.formatted_time || '19:00'}</span>
                        <span style="color: var(--text-secondary); font-weight: 700;">Inspect ›</span>
                    </div>
                </div>
            `;
        };

        mount.innerHTML = `
            <div class="hero-spotlight-container">
                <!-- 1) Big Hero Card (Today #1) -->
                <div class="hero-card-base hero-card-featured ${topTodayClass}" data-match-data='${JSON.stringify(topToday).replace(/'/g, "&apos;")}'>
                    <div class="hero-flag-bg home" style="background-image: url('${topHomeFlag}');"></div>
                    <div class="hero-flag-bg away" style="background-image: url('${topAwayFlag}');"></div>

                    <div class="hero-card-header">
                        <span class="hero-kicker-tag"><i class="fa-solid fa-crown"></i> Best Match Today</span>
                        <span class="hero-score-badge ${topTodayClass}">${topTodayScore}%</span>
                    </div>

                    <div class="hero-featured-matchup">
                        <div class="hero-featured-team home clickable-team" data-name="${topToday.home_team.name}">
                            <div class="hero-featured-identity">
                                <img src="${getFlagUrl(topToday.home_team)}" class="hero-crest-img" alt="">
                                <span class="hero-featured-name">${topToday.home_team.name}</span>
                            </div>
                            <span class="hero-featured-elo">ELO ${topToday.home_team.elo || 2064}</span>
                        </div>

                        <div class="hero-featured-center">
                            <span class="hero-featured-score-big">${topTodayScore}</span>
                            <span class="hero-featured-time-label">${topToday.formatted_time || '19:00'}</span>
                        </div>

                        <div class="hero-featured-team away clickable-team" data-name="${topToday.away_team.name}">
                            <div class="hero-featured-identity">
                                <img src="${getFlagUrl(topToday.away_team)}" class="hero-crest-img" alt="">
                                <span class="hero-featured-name">${topToday.away_team.name}</span>
                            </div>
                            <span class="hero-featured-elo">ELO ${topToday.away_team.elo || 2095}</span>
                        </div>
                    </div>

                    <div class="hero-featured-footer">
                        <span>${topToday.competition_name || 'Finalissima'} · ${topToday.stage || 'Final'}</span>
                        <span style="color: var(--text-secondary); font-weight: 700;">Tactical Breakdown ›</span>
                    </div>
                </div>

                <!-- 2) Vertical Today Card #2 -->
                ${renderVertCard(today2, 2)}

                <!-- 3) Vertical Today Card #3 -->
                ${renderVertCard(today3, 3)}

                <!-- 4) Right Column: Next 7 Days (1 Big + 1 Small) -->
                <div class="hero-right-column">
                    <!-- Top Big Row (Next 7 Days #1) -->
                    <div class="hero-week-big-card ${topWeekClass}" data-match-data='${JSON.stringify(topWeek).replace(/'/g, "&apos;")}'>
                        <div class="hero-flag-bg home" style="background-image: url('${weekHomeFlag}');"></div>
                        <div class="hero-flag-bg away" style="background-image: url('${weekAwayFlag}');"></div>

                        <div class="hero-card-header">
                            <span class="hero-kicker-tag week"><i class="fa-solid fa-calendar-star"></i> Next 7 Days · ${topWeek.formatted_time || 'Wed 20:00'}</span>
                            <span class="hero-score-badge ${topWeekClass}">${topWeekScore}%</span>
                        </div>

                        <div class="hero-week-matchup">
                            <div class="hero-week-team-item">
                                <img src="${getFlagUrl(topWeek.home_team)}" class="hero-crest-img" alt="">
                                <span>${topWeek.home_team.name}</span>
                            </div>
                            <span class="hero-week-vs-tag">vs</span>
                            <div class="hero-week-team-item">
                                <span>${topWeek.away_team.name}</span>
                                <img src="${getFlagUrl(topWeek.away_team)}" class="hero-crest-img" alt="">
                            </div>
                        </div>
                    </div>

                    <!-- Bottom Small Single Strip (Next 7 Days #2) -->
                    <div class="hero-week-small-strip ${getRatingClass(week2.watchability?.overall || 87)}" data-match-data='${JSON.stringify(week2).replace(/'/g, "&apos;")}'>
                        <div class="hero-week-small-left">
                            <span class="hero-week-small-time">${week2.formatted_time || 'Fri 20:45'}</span>
                            <img src="${getFlagUrl(week2.home_team)}" class="hero-crest-img" style="width: 18px; height: 18px;" alt="">
                            <div class="hero-week-small-names">
                                <span>${week2.home_team.name}</span>
                                <span style="color: var(--text-muted); font-size: 0.65rem;">v</span>
                                <span>${week2.away_team.name}</span>
                            </div>
                            <img src="${getFlagUrl(week2.away_team)}" class="hero-crest-img" style="width: 18px; height: 18px;" alt="">
                        </div>
                        <span class="hero-score-badge ${getRatingClass(week2.watchability?.overall || 87)}">${Math.round(week2.watchability?.overall || 87)}%</span>
                    </div>
                </div>
            </div>
        `;

        // Bind interactive clicks on cards
        mount.querySelectorAll('[data-match-data]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                try {
                    const matchData = JSON.parse(el.getAttribute('data-match-data'));
                    const inspector = document.getElementById('proto-inspector');
                    if (inspector && window.innerWidth >= 1100) {
                        openMatchInSideInspector(matchData, el);
                    } else {
                        openMatchDetails(matchData);
                    }
                } catch (err) {
                    console.error("Failed to parse hero match data", err);
                }
            });
        });

        // Bind clickable teams
        mount.querySelectorAll('.clickable-team').forEach(teamBox => {
            teamBox.addEventListener('click', (e) => {
                e.stopPropagation();
                const teamName = teamBox.getAttribute('data-name');
                if (teamName) {
                    window.location.href = `/team/${encodeURIComponent(teamName)}`;
                }
            });
        });

        mount.style.display = 'block';
    }

    // Render a list of fixtures in a column
    function renderColumn(container, fixtures, showDate = false, columnType = '') {
        container.innerHTML = '';
        if (fixtures.length === 0) {
            const isFiltered = activeCompFilter && activeCompFilter !== 'all' && activeCompFilter !== 'upcoming';
            const filterLabel = activeCompFilter === 'hot' ? 'Hot Matches' : activeCompFilter;
            
            let messageTitle = 'No Matches Scheduled';
            let messageSub = 'Check upcoming fixtures in This Week or explore the Calendar.';
            let iconClass = 'fa-regular fa-calendar-xmark';

            if (isFiltered) {
                messageTitle = 'No Matches in This View';
                messageSub = `No ${columnType ? columnType + ' ' : ''}fixtures found for "${filterLabel}".`;
                iconClass = 'fa-solid fa-filter-circle-xmark';
            } else if (columnType === 'Today') {
                messageTitle = 'No Matches Today';
                messageSub = 'No live or scheduled matches today. Check upcoming fixtures.';
                iconClass = 'fa-regular fa-calendar';
            } else if (columnType === 'Tomorrow') {
                messageTitle = 'No Matches Tomorrow';
                messageSub = 'No matches scheduled tomorrow. Check upcoming fixtures.';
                iconClass = 'fa-regular fa-calendar-days';
            }

            container.innerHTML = `
                <div class="empty-state-card glass">
                    <div class="empty-state-icon-wrapper">
                        <i class="${iconClass}"></i>
                    </div>
                    <h4>${messageTitle}</h4>
                    <p>${messageSub}</p>
                </div>
            `;
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
            const compName = match.competition_name || '';
            const matchRegion = match.region || (['Copa Libertadores', 'Copa Sudamericana', 'Brasileirão', 'MLS', 'Major League Soccer', 'Argentina', 'Liga Profesional', 'CONCACAF'].some(c => compName.includes(c)) ? 'Americas' : 'Europe');
            card.className = `match-card ${ratingClass}`;
            card.setAttribute('data-region', matchRegion);
            card.setAttribute('data-competition', compName);
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

            card.addEventListener('click', (e) => {
                const inspector = document.getElementById('proto-inspector');
                if (inspector) {
                    openMatchInSideInspector(match, card);
                } else {
                    openMatchDetails(match);
                }
            });
            container.appendChild(card);
        });
    }

    // Docked Side Inspector Panel Renderer
    function openMatchInSideInspector(match, cardElement) {
        const inspector = document.getElementById('proto-inspector');
        if (!inspector) return;

        if (cardElement) {
            document.querySelectorAll('.match-card').forEach(c => c.classList.remove('selected-pane-card'));
            cardElement.classList.add('selected-pane-card');
        }

        const ratingClass = getRatingClass(match.watchability.overall);
        const homeFlag = getFlagUrl(match.home_team);
        const awayFlag = getFlagUrl(match.away_team);

        const driversList = match.reasons && match.reasons.length > 0
            ? match.reasons.map(r => `<li><i class="fa-solid fa-check"></i> ${r}</li>`).join('')
            : `<li><i class="fa-solid fa-check"></i> High Attack xG Expected (> 2.4)</li>
               <li><i class="fa-solid fa-check"></i> Close ELO Differential (< 50 pts)</li>`;

        const homeOdds = match.odds ? match.odds.home.toFixed(2) : '2.14';
        const drawOdds = match.odds ? match.odds.draw.toFixed(2) : '4.20';
        const awayOdds = match.odds ? match.odds.away.toFixed(2) : '4.04';

        inspector.innerHTML = `
            <div class="inspector-card glass">
                <div class="inspector-header">
                    <span class="competition-badge">${match.competition_badge || '⚽'} ${match.competition_name || 'Top League'}</span>
                    <span class="inspector-watchability-pill ${ratingClass}"><i class="fa-solid fa-fire"></i> ${match.watchability.overall}% Rating</span>
                </div>

                <div class="inspector-stage">${match.stage || 'Regular Season'}</div>

                <div class="inspector-matchup">
                    <div class="inspector-team">
                        <img src="${homeFlag}" alt="${match.home_team.name}">
                        <h4>${match.home_team.name}</h4>
                        <span class="inspector-elo">ELO ${match.home_team.elo}</span>
                    </div>
                    <div class="inspector-vs">${match.status === 'Finished' || match.status === 'Live' ? match.score : 'VS'}</div>
                    <div class="inspector-team">
                        <img src="${awayFlag}" alt="${match.away_team.name}">
                        <h4>${match.away_team.name}</h4>
                        <span class="inspector-elo">ELO ${match.away_team.elo}</span>
                    </div>
                </div>

                <div class="inspector-section">
                    <h4><i class="fa-solid fa-bolt"></i> Watchability Drivers</h4>
                    <ul class="driver-tags">
                        ${driversList}
                    </ul>
                </div>

                <div class="inspector-section">
                    <h4><i class="fa-solid fa-chart-pie"></i> Implied Probabilities</h4>
                    <div class="prob-bar">
                        <div class="prob-seg seg-home" style="width: 42%;" title="Home Win: 42%">42%</div>
                        <div class="prob-seg seg-draw" style="width: 28%;" title="Draw: 28%">28%</div>
                        <div class="prob-seg seg-away" style="width: 30%;" title="Away Win: 30%">30%</div>
                    </div>
                </div>

                <div class="inspector-section">
                    <h4><i class="fa-solid fa-arrow-trend-up"></i> Live Bookmaker Odds</h4>
                    <div class="odds-preview-box">
                        <span>H: <strong>${homeOdds}</strong></span>
                        <span>D: <strong>${drawOdds}</strong></span>
                        <span>A: <strong>${awayOdds}</strong></span>
                    </div>
                </div>
            </div>
        `;
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

    // Expose global filterMatchesByName function for Drawer & Navigation controls
    window.filterMatchesByName = function(leagueName) {
        const cards = document.querySelectorAll('.match-card');
        const lname = (leagueName || '').toLowerCase();

        cards.forEach(card => {
            if (!leagueName || lname === 'all') {
                card.style.display = '';
                return;
            }
            if (lname === 'hot') {
                const scoreEl = card.querySelector('.score-badge, .score-val');
                let score = 0;
                if (scoreEl) {
                    const matchText = scoreEl.textContent.match(/(\d+)%/);
                    if (matchText) score = parseInt(matchText[1], 10);
                }
                card.style.display = (score >= 75) ? '' : 'none';
                return;
            }

            const cardRegion = (card.getAttribute('data-region') || '').toLowerCase();
            const text = (card.textContent).toLowerCase();

            if (lname === 'europe') {
                const isEurope = cardRegion === 'europe' || ['england', 'spain', 'italy', 'germany', 'belgium', 'netherlands', 'france', 'champions', 'europa', 'nations league', 'pro league', 'eredivisie', 'premier', 'la liga', 'serie a', 'bundesliga', 'copa del rey', 'fa cup', 'dfb pokal', 'coppa italia'].some(k => text.includes(k));
                card.style.display = isEurope ? '' : 'none';
                return;
            }

            if (lname === 'americas') {
                const isAmericas = cardRegion === 'americas' || ['americas', 'libertadores', 'sudamericana', 'brasileirão', 'mls', 'argentina', 'brazil', 'liga profesional', 'copa argentina', 'copa do brasil', 'concacaf'].some(k => text.includes(k));
                card.style.display = isAmericas ? '' : 'none';
                return;
            }

            if (text.includes(lname)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    };

    window.filterMatchesByKeywords = function(keywords) {
        const cards = document.querySelectorAll('.match-card');
        cards.forEach(card => {
            if (!keywords || keywords.length === 0) {
                card.style.display = '';
                return;
            }
            const text = card.textContent.toLowerCase();
            const matches = keywords.some(kw => text.includes(kw.toLowerCase()));
            card.style.display = matches ? '' : 'none';
        });
    };
});
