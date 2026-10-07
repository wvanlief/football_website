document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements

    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    const resultsBarContainer = document.getElementById('results-bar-container');
    const resultsListHorizontal = document.getElementById('results-list-horizontal');

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
    let scorePollSequence = 0;
    let lastAppliedScorePoll = 0;
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
    // Provider scores change when the live job runs, about every 5 minutes.
    setInterval(pollLiveScores, 5 * 60 * 1000);

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

    async function resolveAndTimezoneFetch() {
        resolvedTimezone = await resolveTimezone(selectedTimezone);
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
        const ymd = addCalendarDays(ymdInTimeZone(new Date(), timezone), offsetDays);
        const [year, month, day] = ymd.split('-').map(Number);
        const utcNoon = new Date(Date.UTC(year, month - 1, day, 12));
        return new Intl.DateTimeFormat('en-US', {
            timeZone: 'UTC',
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        }).format(utcNoon);
    }

    // Fetch and Load Fixtures

    function processHydratedFixtures(feedOrList, userTz) {
        const todayStr = ymdInTimeZone(new Date(), userTz);
        const matchDateStrOf = (fdata) => {
            if (!fdata.date) return todayStr;
            try {
                const parsed = parseFixtureDate(fdata.date);
                if (parsed) return ymdInTimeZone(parsed, userTz);
            } catch (e) {}
            return todayStr;
        };
        const localizeUpcoming = (rows) => {
            const kept = [];
            (rows || []).forEach(raw => {
                const fdata = localizeFixtureDisplay(raw, userTz);
                if (fdata.status === "Finished") return;
                if (matchDateStrOf(fdata) >= todayStr) kept.push(fdata);
            });
            return kept;
        };

        const grouped = feedOrList && !Array.isArray(feedOrList) && (
            Array.isArray(feedOrList.this_week) ||
            Array.isArray(feedOrList.today) ||
            Array.isArray(feedOrList.tomorrow)
        );
        if (grouped) {
            const finishedFixtures = (feedOrList.finished || []).map(raw => localizeFixtureDisplay(raw, userTz));
            finishedFixtures.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
            return {
                today: localizeUpcoming(feedOrList.today),
                tomorrow: localizeUpcoming(feedOrList.tomorrow),
                this_week: localizeUpcoming(feedOrList.this_week),
                finished: finishedFixtures.slice(0, 30),
                is_offseason: !!feedOrList.is_offseason,
                offseason_notice: feedOrList.offseason_notice || null
            };
        }

        let todayFixtures = [];
        let tomorrowFixtures = [];
        let weekFixtures = [];
        let finishedFixtures = [];
        let scheduledFixtures = [];
        const tomorrowStr = addCalendarDays(todayStr, 1);
        const maxDateStr = addCalendarDays(todayStr, 8);

        (feedOrList || []).forEach(raw => {
            const fdata = localizeFixtureDisplay(raw, userTz);
            const matchDateStr = matchDateStrOf(fdata);

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

        todayFixtures.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
        tomorrowFixtures.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
        finishedFixtures.sort((a, b) => (b.date || "").localeCompare(a.date || ""));

        let isOffseason = false;
        let offseasonNotice = null;

        if (todayFixtures.length === 0 && tomorrowFixtures.length === 0 && weekFixtures.length === 0 && scheduledFixtures.length > 0) {
            isOffseason = true;
            scheduledFixtures.sort((a, b) => a.matchDateStr.localeCompare(b.matchDateStr));
            const firstMatchDate = scheduledFixtures[0].matchDateStr;
            const blockEndDateStr = addCalendarDays(firstMatchDate, 8);
            weekFixtures = scheduledFixtures
                .filter(item => item.matchDateStr >= firstMatchDate && item.matchDateStr <= blockEndDateStr)
                .map(item => item.fdata);
            const [year, month, day] = firstMatchDate.split('-').map(Number);
            const formattedFirstDate = new Intl.DateTimeFormat('en-US', {
                timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric'
            }).format(new Date(Date.UTC(year, month - 1, day, 12)));
            offseasonNotice = `Off-season: Showing next upcoming matches starting ${formattedFirstDate}.`;
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
                const alreadyGrouped = parsed && !Array.isArray(parsed) && (
                    Array.isArray(parsed.this_week) || Array.isArray(parsed.today) || Array.isArray(parsed.tomorrow)
                );
                if (alreadyGrouped) {
                    activeFixtures = processHydratedFixtures(parsed, resolvedTimezone);
                    if (parsed.updated_at) {
                        lastFeedUpdatedAt = parsed.updated_at;
                        updateFreshnessIndicator();
                    }
                    renderAllColumns();
                    return;
                }
                if (parsed && parsed.updated_at) {
                    lastFeedUpdatedAt = parsed.updated_at;
                    updateFreshnessIndicator();
                }
            } catch(e) {
                console.warn("Failed to parse inline hydrated fixtures:", e);
            }
        }

        const cacheKey = `findfootball-cached-fixtures-v6-${resolvedTimezone}`;
        const cachedSession = sessionStorage.getItem(cacheKey);

        if (cachedSession) {
            try {
                const cachedPayload = JSON.parse(cachedSession);
                activeFixtures = processHydratedFixtures(cachedPayload, resolvedTimezone);
                if (cachedPayload && cachedPayload.updated_at) {
                    lastFeedUpdatedAt = cachedPayload.updated_at;
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
            activeFixtures = processHydratedFixtures(data, resolvedTimezone);
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

    function rememberLiveScore(row) {
        if (!activeFixtures || row.id == null) return;
        ['today', 'tomorrow', 'this_week', 'finished'].forEach(key => {
            (activeFixtures[key] || []).forEach(match => {
                if (match.id === row.id) {
                    match.status = row.status;
                    match.score = row.score;
                }
            });
        });
    }

    function applyLiveScoreToCard(card, row) {
        if (!card || (row.status !== 'Live' && row.status !== 'Finished')) return;
        const center = card.querySelector('.match-info-center');
        if (!center) return;
        const vs = center.querySelector('.match-vs');
        center.querySelectorAll('.match-score, .live-indicator').forEach(node => node.remove());
        if (row.score) {
            center.querySelectorAll('.match-time').forEach(node => node.remove());
        }
        if (row.score || !center.querySelector('.match-time')) {
            const scoreEl = document.createElement('span');
            scoreEl.className = row.status === 'Live' ? 'match-score live' : 'match-score';
            scoreEl.textContent = row.score || 'Score unavailable';
            if (vs) center.insertBefore(scoreEl, vs);
            else center.appendChild(scoreEl);
        }
        if (row.status === 'Live') {
            const indicator = document.createElement('span');
            indicator.className = 'live-indicator';
            const dot = document.createElement('span');
            dot.className = 'live-dot';
            indicator.append(dot, document.createTextNode('Live'));
            if (vs) center.insertBefore(indicator, vs);
            else center.appendChild(indicator);
        }
    }

    async function pollLiveScores() {
        const sequence = ++scorePollSequence;
        try {
            const res = await fetch('/api/fixtures/scores');
            if (!res.ok) return;
            const rows = await res.json();
            if (!Array.isArray(rows) || sequence < lastAppliedScorePoll) return;
            lastAppliedScorePoll = sequence;
            rows.forEach(row => {
                rememberLiveScore(row);
                document.querySelectorAll('.match-card').forEach(card => {
                    if (card.getAttribute('data-fixture-id') === String(row.id)) {
                        applyLiveScoreToCard(card, row);
                    }
                });
            });
        } catch (err) {
            console.warn('Live score poll failed', err);
        }
    }

    window.pollLiveScores = pollLiveScores;

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
                const noticeIcon = document.createElement('i');
                noticeIcon.className = 'fa-solid fa-umbrella-beach';
                noticeBanner.append(noticeIcon, document.createElement('span'));
                const triptychContainer = document.querySelector('.triptych-container');
                if (triptychContainer) {
                    triptychContainer.parentNode.insertBefore(noticeBanner, triptychContainer);
                }
            }
            noticeBanner.querySelector('span').textContent = activeFixtures.offseason_notice;
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
    }

    function matchWatchability(match) {
        if (!match) return 0;
        if (match.watchability && match.watchability.overall != null) return match.watchability.overall;
        return match.watchability_score || 0;
    }

    function sortByWatchability(list) {
        return [...(list || [])].sort((a, b) => matchWatchability(b) - matchWatchability(a));
    }

    function formatNextMatchLine(match) {
        if (!match || !match.home_team || !match.away_team) {
            return 'No upcoming fixtures are scheduled in this window.';
        }
        const when = [match.formatted_date_short || match.formatted_date, match.formatted_time]
            .filter(Boolean)
            .join(' · ');
        const line = `${match.home_team.name} vs ${match.away_team.name}`;
        return when ? `Next match: ${line} · ${when}` : `Next match: ${line}`;
    }

    function earliestUpcoming(tomorrowFixtures, weekFixtures) {
        const pool = [...(tomorrowFixtures || []), ...(weekFixtures || [])];
        pool.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
        return pool[0] || null;
    }

    function createHeroElement(tagName, className, text) {
        const element = document.createElement(tagName);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function createHeroFlagBackground(side, url) {
        const flag = createHeroElement('div', `hero-flag-bg ${side}`);
        flag.style.backgroundImage = `url(${JSON.stringify(url)})`;
        return flag;
    }

    function createHeroCrest(team, size) {
        const crest = createHeroElement('img', 'hero-crest-img');
        crest.src = getFlagUrl(team, size);
        crest.alt = '';
        return crest;
    }

    function setHeroMatchData(element, match) {
        element.setAttribute('data-match-data', JSON.stringify(match));
    }

    function renderHeroEmptyCard(variant, title, subtitle) {
        const card = createHeroElement('div', `hero-empty-card hero-empty-${variant}`);
        card.setAttribute('role', 'status');
        card.setAttribute('data-hero-empty', 'true');

        const icon = createHeroElement('div', 'hero-empty-icon');
        icon.appendChild(createHeroElement('i', 'fa-regular fa-calendar'));
        card.append(
            icon,
            createHeroElement('h4', '', title),
            createHeroElement('p', '', subtitle)
        );
        return card;
    }

    function renderHeroSpotlight(todayFixtures, weekFixtures, tomorrowFixtures) {
        const mount = document.getElementById('hero-match-spotlight');
        if (!mount) return;

        const todayList = sortByWatchability(todayFixtures).slice(0, 3);
        const weekPool = [];
        const seenWeekIds = new Set();
        [...(tomorrowFixtures || []), ...(weekFixtures || [])].forEach((match) => {
            const key = match && match.id != null ? match.id : match;
            if (seenWeekIds.has(key)) return;
            seenWeekIds.add(key);
            weekPool.push(match);
        });
        let weekList = sortByWatchability(weekPool).slice(0, 2);

        const isOffseason = !!(activeFixtures && activeFixtures.is_offseason);
        const nextUpcoming = earliestUpcoming(tomorrowFixtures, weekFixtures);
        const nextLine = formatNextMatchLine(nextUpcoming);
        const emptyTitle = isOffseason ? 'Off-Season' : 'No Matches Today';
        const emptySubtitle = isOffseason && activeFixtures.offseason_notice
            ? activeFixtures.offseason_notice
            : nextLine;

        const renderVertCard = (m, rank) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const kickoff = m.formatted_time || '';
            const card = createHeroElement('div', `hero-card-base hero-vert-card ${rClass}`);
            setHeroMatchData(card, m);

            const header = createHeroElement('div', 'hero-card-header');
            header.append(
                createHeroElement('span', 'hero-kicker-tag', `#${rank} · ${m.competition_name || 'Match'}`),
                createHeroElement('span', `hero-score-badge ${rClass}`, `${score}%`)
            );

            const matchup = createHeroElement('div', 'hero-vert-matchup');
            [m.home_team, m.away_team].forEach((team) => {
                const row = createHeroElement('div', 'hero-vert-team-row');
                row.append(createHeroCrest(team), createHeroElement('span', '', team.name));
                matchup.appendChild(row);
            });

            const kickoffLabel = createHeroElement('span');
            if (kickoff) {
                kickoffLabel.append(
                    createHeroElement('i', 'fa-regular fa-clock'),
                    document.createTextNode(` ${kickoff}`)
                );
            }
            const inspectLabel = createHeroElement('span', '', 'Inspect ›');
            inspectLabel.style.color = 'var(--text-secondary)';
            inspectLabel.style.fontWeight = '700';
            const footer = createHeroElement('div', 'hero-vert-footer');
            footer.append(kickoffLabel, inspectLabel);

            card.append(
                createHeroFlagBackground('home', getFlagUrl(m.home_team, 'w320')),
                createHeroFlagBackground('away', getFlagUrl(m.away_team, 'w320')),
                header,
                matchup,
                footer
            );
            return card;
        };

        const renderFeaturedCard = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const homeElo = m.home_team.elo != null ? `ELO ${m.home_team.elo}` : '';
            const awayElo = m.away_team.elo != null ? `ELO ${m.away_team.elo}` : '';
            const meta = [m.competition_name, m.stage].filter(Boolean).join(' · ');
            const card = createHeroElement('div', `hero-card-base hero-card-featured ${rClass}`);
            setHeroMatchData(card, m);

            const kicker = createHeroElement('span', 'hero-kicker-tag');
            kicker.append(createHeroElement('i', 'fa-solid fa-crown'), document.createTextNode(' Best Match Today'));
            const header = createHeroElement('div', 'hero-card-header');
            header.append(kicker, createHeroElement('span', `hero-score-badge ${rClass}`, `${score}%`));

            const createTeam = (team, side, elo) => {
                const teamElement = createHeroElement('div', `hero-featured-team ${side} clickable-team`);
                teamElement.setAttribute('data-name', team.name);
                const identity = createHeroElement('div', 'hero-featured-identity');
                identity.append(
                    createHeroCrest(team),
                    createHeroElement('span', 'hero-featured-name', team.name)
                );
                teamElement.append(identity, createHeroElement('span', 'hero-featured-elo', elo));
                return teamElement;
            };

            const center = createHeroElement('div', 'hero-featured-center');
            center.append(
                createHeroElement('span', 'hero-featured-score-big', score),
                createHeroElement('span', 'hero-featured-time-label', m.formatted_time || '')
            );
            const matchup = createHeroElement('div', 'hero-featured-matchup');
            matchup.append(
                createTeam(m.home_team, 'home', homeElo),
                center,
                createTeam(m.away_team, 'away', awayElo)
            );

            const breakdown = createHeroElement('span', '', 'Tactical Breakdown ›');
            breakdown.style.color = 'var(--text-secondary)';
            breakdown.style.fontWeight = '700';
            const footer = createHeroElement('div', 'hero-featured-footer');
            footer.append(createHeroElement('span', '', meta), breakdown);

            card.append(
                createHeroFlagBackground('home', getFlagUrl(m.home_team, 'w320')),
                createHeroFlagBackground('away', getFlagUrl(m.away_team, 'w320')),
                header,
                matchup,
                footer
            );
            return card;
        };

        const renderWeekBigCard = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const when = m.formatted_time || m.formatted_date_short || '';
            const card = createHeroElement('div', `hero-week-big-card ${rClass}`);
            setHeroMatchData(card, m);

            const kicker = createHeroElement('span', 'hero-kicker-tag week');
            kicker.append(
                createHeroElement('i', 'fa-solid fa-calendar-star'),
                document.createTextNode(` Next 7 Days${when ? ` · ${when}` : ''}`)
            );
            const header = createHeroElement('div', 'hero-card-header');
            header.append(kicker, createHeroElement('span', `hero-score-badge ${rClass}`, `${score}%`));

            const home = createHeroElement('div', 'hero-week-team-item');
            home.append(createHeroCrest(m.home_team), createHeroElement('span', '', m.home_team.name));
            const away = createHeroElement('div', 'hero-week-team-item');
            away.append(createHeroElement('span', '', m.away_team.name), createHeroCrest(m.away_team));
            const matchup = createHeroElement('div', 'hero-week-matchup');
            matchup.append(home, createHeroElement('span', 'hero-week-vs-tag', 'vs'), away);

            card.append(
                createHeroFlagBackground('home', getFlagUrl(m.home_team, 'w320')),
                createHeroFlagBackground('away', getFlagUrl(m.away_team, 'w320')),
                header,
                matchup
            );
            return card;
        };

        const renderWeekSmallStrip = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const card = createHeroElement('div', `hero-week-small-strip ${rClass}`);
            setHeroMatchData(card, m);

            const homeCrest = createHeroCrest(m.home_team);
            const awayCrest = createHeroCrest(m.away_team);
            [homeCrest, awayCrest].forEach((crest) => {
                crest.style.width = '18px';
                crest.style.height = '18px';
            });

            const versus = createHeroElement('span', '', 'v');
            versus.style.color = 'var(--text-muted)';
            versus.style.fontSize = '0.65rem';
            const names = createHeroElement('div', 'hero-week-small-names');
            names.append(
                createHeroElement('span', '', m.home_team.name),
                versus,
                createHeroElement('span', '', m.away_team.name)
            );
            const left = createHeroElement('div', 'hero-week-small-left');
            left.append(
                createHeroElement('span', 'hero-week-small-time', m.formatted_time || m.formatted_date_short || ''),
                homeCrest,
                names,
                awayCrest
            );
            card.append(left, createHeroElement('span', `hero-score-badge ${rClass}`, `${score}%`));
            return card;
        };

        const featuredCard = todayList[0]
            ? renderFeaturedCard(todayList[0])
            : renderHeroEmptyCard('featured', emptyTitle, emptySubtitle);
        const today2Card = todayList[1]
            ? renderVertCard(todayList[1], 2)
            : renderHeroEmptyCard('vert', todayList.length ? 'No More Matches Today' : emptyTitle, emptySubtitle);
        const today3Card = todayList[2]
            ? renderVertCard(todayList[2], 3)
            : renderHeroEmptyCard('vert', todayList.length < 3 ? (isOffseason ? 'Off-Season' : 'Quiet Schedule') : '', emptySubtitle);
        const weekBigCard = weekList[0]
            ? renderWeekBigCard(weekList[0])
            : renderHeroEmptyCard('week-big', 'Nothing in the Next 7 Days', emptySubtitle);
        const weekSmallCard = weekList[1]
            ? renderWeekSmallStrip(weekList[1])
            : renderHeroEmptyCard('week-small', 'Next Match', emptySubtitle);

        const rightColumn = createHeroElement('div', 'hero-right-column');
        rightColumn.append(weekBigCard, weekSmallCard);
        const spotlight = createHeroElement('div', 'hero-spotlight-container');
        spotlight.append(featuredCard, today2Card, today3Card, rightColumn);
        mount.replaceChildren(spotlight);

        mount.querySelectorAll('[data-match-data]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                try {
                    const matchData = JSON.parse(el.getAttribute('data-match-data'));
                    const inspector = document.getElementById('proto-inspector');
                    const width = window.innerWidth;
                    if (inspector && (width >= 1100 || width < 768)) {
                        openMatchInSideInspector(matchData, el);
                    } else {
                        openMatchDetails(matchData);
                    }
                } catch (err) {
                    console.error("Failed to parse hero match data", err);
                }
            });
        });

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
            card.setAttribute('data-fixture-id', String(match.id));
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

        if (window.innerWidth < 768 && typeof window.showMobilePane === 'function') {
            window.showMobilePane('inspector');
        }

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
                const scoreEl = card.querySelector('.score-badge, .score-val, .card-score-pill');
                let score = 0;
                if (scoreEl) {
                    const matchText = scoreEl.textContent.match(/(\d+)%/);
                    if (matchText) score = parseInt(matchText[1], 10);
                }
                const isHotTier = card.classList.contains('recommended') || card.classList.contains('must-watch');
                card.style.display = (score >= 65 || isHotTier) ? '' : 'none';
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
