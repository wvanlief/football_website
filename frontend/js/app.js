document.addEventListener('DOMContentLoaded', () => {
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

    function renderHeroEmptyCard(variant, title, subtitle) {
        return `
            <div class="hero-empty-card hero-empty-${variant}" role="status" data-hero-empty="true">
                <div class="hero-empty-icon"><i class="fa-regular fa-calendar"></i></div>
                <h4>${title}</h4>
                <p>${subtitle}</p>
            </div>
        `;
    }

    function renderHeroSpotlight(todayFixtures, weekFixtures, tomorrowFixtures) {
        const mount = document.getElementById('hero-match-spotlight');
        if (!mount) return;

        const todayList = sortByWatchability(todayFixtures).slice(0, 3);
        let weekList = sortByWatchability(weekFixtures).slice(0, 2);
        if (weekList.length < 2 && tomorrowFixtures && tomorrowFixtures.length > 0) {
            const used = new Set(weekList);
            const extras = sortByWatchability(tomorrowFixtures).filter((match) => !used.has(match));
            weekList = [...weekList, ...extras].slice(0, 2);
        }

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
            const hFlag = getFlagUrl(m.home_team, 'w320');
            const aFlag = getFlagUrl(m.away_team, 'w320');
            const kickoff = m.formatted_time || '';

            return `
                <div class="hero-card-base hero-vert-card ${rClass}" data-match-data='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
                    <div class="hero-flag-bg home" style="background-image: url('${hFlag}');"></div>
                    <div class="hero-flag-bg away" style="background-image: url('${aFlag}');"></div>

                    <div class="hero-card-header">
                        <span class="hero-kicker-tag">#${rank} · ${m.competition_name || 'Match'}</span>
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
                        <span>${kickoff ? `<i class="fa-regular fa-clock"></i> ${kickoff}` : ''}</span>
                        <span style="color: var(--text-secondary); font-weight: 700;">Inspect ›</span>
                    </div>
                </div>
            `;
        };

        const renderFeaturedCard = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const homeFlag = getFlagUrl(m.home_team, 'w320');
            const awayFlag = getFlagUrl(m.away_team, 'w320');
            const homeElo = m.home_team.elo != null ? `ELO ${m.home_team.elo}` : '';
            const awayElo = m.away_team.elo != null ? `ELO ${m.away_team.elo}` : '';
            const meta = [m.competition_name, m.stage].filter(Boolean).join(' · ');

            return `
                <div class="hero-card-base hero-card-featured ${rClass}" data-match-data='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
                    <div class="hero-flag-bg home" style="background-image: url('${homeFlag}');"></div>
                    <div class="hero-flag-bg away" style="background-image: url('${awayFlag}');"></div>

                    <div class="hero-card-header">
                        <span class="hero-kicker-tag"><i class="fa-solid fa-crown"></i> Best Match Today</span>
                        <span class="hero-score-badge ${rClass}">${score}%</span>
                    </div>

                    <div class="hero-featured-matchup">
                        <div class="hero-featured-team home clickable-team" data-name="${m.home_team.name}">
                            <div class="hero-featured-identity">
                                <img src="${getFlagUrl(m.home_team)}" class="hero-crest-img" alt="">
                                <span class="hero-featured-name">${m.home_team.name}</span>
                            </div>
                            <span class="hero-featured-elo">${homeElo}</span>
                        </div>

                        <div class="hero-featured-center">
                            <span class="hero-featured-score-big">${score}</span>
                            <span class="hero-featured-time-label">${m.formatted_time || ''}</span>
                        </div>

                        <div class="hero-featured-team away clickable-team" data-name="${m.away_team.name}">
                            <div class="hero-featured-identity">
                                <img src="${getFlagUrl(m.away_team)}" class="hero-crest-img" alt="">
                                <span class="hero-featured-name">${m.away_team.name}</span>
                            </div>
                            <span class="hero-featured-elo">${awayElo}</span>
                        </div>
                    </div>

                    <div class="hero-featured-footer">
                        <span>${meta}</span>
                        <span style="color: var(--text-secondary); font-weight: 700;">Tactical Breakdown ›</span>
                    </div>
                </div>
            `;
        };

        const renderWeekBigCard = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            const when = m.formatted_time || m.formatted_date_short || '';
            return `
                <div class="hero-week-big-card ${rClass}" data-match-data='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
                    <div class="hero-flag-bg home" style="background-image: url('${getFlagUrl(m.home_team, 'w320')}');"></div>
                    <div class="hero-flag-bg away" style="background-image: url('${getFlagUrl(m.away_team, 'w320')}');"></div>

                    <div class="hero-card-header">
                        <span class="hero-kicker-tag week"><i class="fa-solid fa-calendar-star"></i> Next 7 Days${when ? ` · ${when}` : ''}</span>
                        <span class="hero-score-badge ${rClass}">${score}%</span>
                    </div>

                    <div class="hero-week-matchup">
                        <div class="hero-week-team-item">
                            <img src="${getFlagUrl(m.home_team)}" class="hero-crest-img" alt="">
                            <span>${m.home_team.name}</span>
                        </div>
                        <span class="hero-week-vs-tag">vs</span>
                        <div class="hero-week-team-item">
                            <span>${m.away_team.name}</span>
                            <img src="${getFlagUrl(m.away_team)}" class="hero-crest-img" alt="">
                        </div>
                    </div>
                </div>
            `;
        };

        const renderWeekSmallStrip = (m) => {
            const score = Math.round(matchWatchability(m));
            const rClass = getRatingClass(score);
            return `
                <div class="hero-week-small-strip ${rClass}" data-match-data='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
                    <div class="hero-week-small-left">
                        <span class="hero-week-small-time">${m.formatted_time || m.formatted_date_short || ''}</span>
                        <img src="${getFlagUrl(m.home_team)}" class="hero-crest-img" style="width: 18px; height: 18px;" alt="">
                        <div class="hero-week-small-names">
                            <span>${m.home_team.name}</span>
                            <span style="color: var(--text-muted); font-size: 0.65rem;">v</span>
                            <span>${m.away_team.name}</span>
                        </div>
                        <img src="${getFlagUrl(m.away_team)}" class="hero-crest-img" style="width: 18px; height: 18px;" alt="">
                    </div>
                    <span class="hero-score-badge ${rClass}">${score}%</span>
                </div>
            `;
        };

        const featuredHtml = todayList[0]
            ? renderFeaturedCard(todayList[0])
            : renderHeroEmptyCard('featured', emptyTitle, emptySubtitle);
        const today2Html = todayList[1]
            ? renderVertCard(todayList[1], 2)
            : renderHeroEmptyCard('vert', todayList.length ? 'No More Matches Today' : emptyTitle, emptySubtitle);
        const today3Html = todayList[2]
            ? renderVertCard(todayList[2], 3)
            : renderHeroEmptyCard('vert', todayList.length < 3 ? (isOffseason ? 'Off-Season' : 'Quiet Schedule') : '', emptySubtitle);
        const weekBigHtml = weekList[0]
            ? renderWeekBigCard(weekList[0])
            : renderHeroEmptyCard('week-big', 'Nothing in the Next 7 Days', emptySubtitle);
        const weekSmallHtml = weekList[1]
            ? renderWeekSmallStrip(weekList[1])
            : renderHeroEmptyCard('week-small', 'Next Match', emptySubtitle);

        mount.innerHTML = `
            <div class="hero-spotlight-container">
                ${featuredHtml}
                ${today2Html}
                ${today3Html}
                <div class="hero-right-column">
                    ${weekBigHtml}
                    ${weekSmallHtml}
                </div>
            </div>
        `;

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
