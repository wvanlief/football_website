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

    const CLUB_BADGES = {
        // Spain
        "Real Madrid": "https://media.api-sports.io/football/teams/541.png",
        "FC Barcelona": "https://media.api-sports.io/football/teams/529.png",
        "Barcelona": "https://media.api-sports.io/football/teams/529.png",
        "Atletico Madrid": "https://media.api-sports.io/football/teams/530.png",
        "Atlético Madrid": "https://media.api-sports.io/football/teams/530.png",
        "Athletic Club": "https://media.api-sports.io/football/teams/531.png",
        "Athletic Bilbao": "https://media.api-sports.io/football/teams/531.png",
        "Villarreal": "https://media.api-sports.io/football/teams/533.png",
        "Villarreal CF": "https://media.api-sports.io/football/teams/533.png",
        "Real Sociedad": "https://media.api-sports.io/football/teams/548.png",
        "Sevilla": "https://media.api-sports.io/football/teams/536.png",
        "Girona": "https://media.api-sports.io/football/teams/547.png",
        "Real Betis": "https://media.api-sports.io/football/teams/543.png",
        "Valencia": "https://media.api-sports.io/football/teams/532.png",
        "Osasuna": "https://media.api-sports.io/football/teams/727.png",
        "Celta Vigo": "https://media.api-sports.io/football/teams/538.png",
        "Rayo Vallecano": "https://media.api-sports.io/football/teams/728.png",
        "Getafe": "https://media.api-sports.io/football/teams/546.png",
        "Mallorca": "https://media.api-sports.io/football/teams/798.png",
        "Las Palmas": "https://media.api-sports.io/football/teams/534.png",
        "Alaves": "https://media.api-sports.io/football/teams/542.png",

        // England
        "Manchester City": "https://media.api-sports.io/football/teams/50.png",
        "Man City": "https://media.api-sports.io/football/teams/50.png",
        "Arsenal": "https://media.api-sports.io/football/teams/42.png",
        "Liverpool": "https://media.api-sports.io/football/teams/40.png",
        "Aston Villa": "https://media.api-sports.io/football/teams/66.png",
        "Tottenham Hotspur": "https://media.api-sports.io/football/teams/47.png",
        "Tottenham": "https://media.api-sports.io/football/teams/47.png",
        "Chelsea": "https://media.api-sports.io/football/teams/49.png",
        "Manchester United": "https://media.api-sports.io/football/teams/33.png",
        "Man United": "https://media.api-sports.io/football/teams/33.png",
        "Newcastle": "https://media.api-sports.io/football/teams/34.png",
        "Newcastle United": "https://media.api-sports.io/football/teams/34.png",
        "West Ham": "https://media.api-sports.io/football/teams/48.png",
        "West Ham United": "https://media.api-sports.io/football/teams/48.png",
        "Brighton": "https://media.api-sports.io/football/teams/51.png",
        "Wolverhampton": "https://media.api-sports.io/football/teams/39.png",
        "Fulham": "https://media.api-sports.io/football/teams/45.png",
        "Bournemouth": "https://media.api-sports.io/football/teams/35.png",
        "Crystal Palace": "https://media.api-sports.io/football/teams/52.png",
        "Everton": "https://media.api-sports.io/football/teams/46.png",
        "Brentford": "https://media.api-sports.io/football/teams/55.png",
        "Nottingham Forest": "https://media.api-sports.io/football/teams/65.png",

        // France
        "Paris Saint-Germain": "https://media.api-sports.io/football/teams/85.png",
        "PSG": "https://media.api-sports.io/football/teams/85.png",
        "Marseille": "https://media.api-sports.io/football/teams/81.png",
        "Olympique de Marseille": "https://media.api-sports.io/football/teams/81.png",
        "OM": "https://media.api-sports.io/football/teams/81.png",
        "Monaco": "https://media.api-sports.io/football/teams/91.png",
        "AS Monaco": "https://media.api-sports.io/football/teams/91.png",
        "Lille": "https://media.api-sports.io/football/teams/79.png",
        "LOSC Lille": "https://media.api-sports.io/football/teams/79.png",
        "Lyon": "https://media.api-sports.io/football/teams/80.png",
        "Olympique Lyonnais": "https://media.api-sports.io/football/teams/80.png",
        "Nice": "https://media.api-sports.io/football/teams/84.png",
        "Lens": "https://media.api-sports.io/football/teams/116.png",
        "Brest": "https://media.api-sports.io/football/teams/1063.png",
        "Rennes": "https://media.api-sports.io/football/teams/94.png",

        // Germany
        "Bayern Munchen": "https://media.api-sports.io/football/teams/157.png",
        "Bayern Munich": "https://media.api-sports.io/football/teams/157.png",
        "Borussia Dortmund": "https://media.api-sports.io/football/teams/165.png",
        "Dortmund": "https://media.api-sports.io/football/teams/165.png",
        "Bayer Leverkusen": "https://media.api-sports.io/football/teams/168.png",
        "Leverkusen": "https://media.api-sports.io/football/teams/168.png",
        "RB Leipzig": "https://media.api-sports.io/football/teams/173.png",
        "Leipzig": "https://media.api-sports.io/football/teams/173.png",
        "Eintracht Frankfurt": "https://media.api-sports.io/football/teams/169.png",
        "Frankfurt": "https://media.api-sports.io/football/teams/169.png",
        "Stuttgart": "https://media.api-sports.io/football/teams/172.png",
        "VfB Stuttgart": "https://media.api-sports.io/football/teams/172.png",
        "Wolfsburg": "https://media.api-sports.io/football/teams/161.png",
        "Gladbach": "https://media.api-sports.io/football/teams/163.png",
        "Hoffenheim": "https://media.api-sports.io/football/teams/167.png",
        "Freiburg": "https://media.api-sports.io/football/teams/160.png",
        "Werder Bremen": "https://media.api-sports.io/football/teams/162.png",

        // Italy
        "Inter": "https://media.api-sports.io/football/teams/505.png",
        "Inter Milan": "https://media.api-sports.io/football/teams/505.png",
        "AC Milan": "https://media.api-sports.io/football/teams/489.png",
        "Milan": "https://media.api-sports.io/football/teams/489.png",
        "Juventus": "https://media.api-sports.io/football/teams/496.png",
        "Atalanta": "https://media.api-sports.io/football/teams/499.png",
        "Bologna": "https://media.api-sports.io/football/teams/500.png",
        "Roma": "https://media.api-sports.io/football/teams/497.png",
        "AS Roma": "https://media.api-sports.io/football/teams/497.png",
        "Lazio": "https://media.api-sports.io/football/teams/487.png",
        "SS Lazio": "https://media.api-sports.io/football/teams/487.png",
        "Napoli": "https://media.api-sports.io/football/teams/492.png",
        "Fiorentina": "https://media.api-sports.io/football/teams/502.png",
        "Torino": "https://media.api-sports.io/football/teams/503.png",

        // Other European Clubs
        "PSV Eindhoven": "https://media.api-sports.io/football/teams/197.png",
        "PSV": "https://media.api-sports.io/football/teams/197.png",
        "Feyenoord": "https://media.api-sports.io/football/teams/610.png",
        "Ajax": "https://media.api-sports.io/football/teams/194.png",
        "Sporting CP": "https://media.api-sports.io/football/teams/498.png",
        "Benfica": "https://media.api-sports.io/football/teams/495.png",
        "Porto": "https://media.api-sports.io/football/teams/503.png",
        "Celtic": "https://media.api-sports.io/football/teams/247.png",
        "Rangers": "https://media.api-sports.io/football/teams/257.png",
        "Club Brugge": "https://media.api-sports.io/football/teams/569.png",
        "Anderlecht": "https://media.api-sports.io/football/teams/564.png",
        "Bodo/Glimt": "https://media.api-sports.io/football/teams/1038.png",
        "Bodø/Glimt": "https://media.api-sports.io/football/teams/1038.png",
        "Copenhagen": "https://media.api-sports.io/football/teams/400.png",
        "FC Copenhagen": "https://media.api-sports.io/football/teams/400.png",
        "Galatasaray": "https://media.api-sports.io/football/teams/645.png",
        "Fenerbahce": "https://media.api-sports.io/football/teams/611.png",
        "Besiktas": "https://media.api-sports.io/football/teams/562.png",
        "Shakhtar Donetsk": "https://media.api-sports.io/football/teams/550.png",
        "Red Star Belgrade": "https://media.api-sports.io/football/teams/598.png",
        "Sparta Praha": "https://media.api-sports.io/football/teams/549.png",
        "Slavia Praha": "https://media.api-sports.io/football/teams/553.png",
        "Sturm Graz": "https://media.api-sports.io/football/teams/2020.png",
        "RB Salzburg": "https://media.api-sports.io/football/teams/571.png",
        "Red Bull Salzburg": "https://media.api-sports.io/football/teams/571.png",
        "Young Boys": "https://media.api-sports.io/football/teams/565.png",
        "Dinamo Zagreb": "https://media.api-sports.io/football/teams/631.png",
        "Midtjylland": "https://media.api-sports.io/football/teams/398.png",
        "PAOK": "https://media.api-sports.io/football/teams/616.png",
        "Malmo FF": "https://media.api-sports.io/football/teams/377.png",
        "Qarabag": "https://media.api-sports.io/football/teams/636.png"
    };

    // Pre-build normalized lookup map for fuzzy matching
    const NORMALIZED_CLUB_BADGES = {};
    Object.keys(CLUB_BADGES).forEach(key => {
        const normKey = key.toLowerCase().replace(/[\s\-_'’\/\.]/g, '');
        NORMALIZED_CLUB_BADGES[normKey] = CLUB_BADGES[key];
    });

    function getFlagUrl(target, size = 'w40') {
        if (!target) return '/static/badges/default.png';
        if (typeof target === 'object') {
            if (target.logo_url) return target.logo_url;
            target = target.name || target.team;
        }
        if (typeof target === 'string') {
            if (CLUB_BADGES[target]) return CLUB_BADGES[target];
            const normName = target.toLowerCase().replace(/[\s\-_'’\/\.]/g, '');
            if (NORMALIZED_CLUB_BADGES[normName]) return NORMALIZED_CLUB_BADGES[normName];
            const code = COUNTRY_FLAGS[target];
            if (code) return `https://flagcdn.com/${size}/${code}.png`;
        }
        return '/static/badges/default.png';
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
    const toggleMatrixBtn = document.getElementById('toggle-matrix-btn');
    const groupMatchesContainer = document.getElementById('group-matches-container');
    const matrixContainer = document.getElementById('matrix-container');
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
    let formatEngine = 'group_knockout';
    let competitionName = 'World Cup';

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

    if (toggleMatrixBtn) {
        toggleMatrixBtn.addEventListener('click', () => {
            activeView = 'matrix';
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

    function renderNationsLeagueTabs() {
        if (!groupTabsNav) return;
        
        let activeDiv = 'A';
        let activeNum = '1';
        if (activeGroup.length >= 2) {
            activeDiv = activeGroup[0];
            activeNum = activeGroup.slice(1);
        } else if (['A', 'B', 'C', 'D'].includes(activeGroup)) {
            activeDiv = activeGroup;
            activeNum = '1';
            activeGroup = `${activeDiv}${activeNum}`;
        } else {
            activeGroup = 'A1';
        }

        groupTabsNav.innerHTML = `
            <button class="group-tab-btn ${activeDiv === 'A' ? 'active' : ''}" data-div="A">League A</button>
            <button class="group-tab-btn ${activeDiv === 'B' ? 'active' : ''}" data-div="B">League B</button>
            <button class="group-tab-btn ${activeDiv === 'C' ? 'active' : ''}" data-div="C">League C</button>
            <button class="group-tab-btn ${activeDiv === 'D' ? 'active' : ''}" data-div="D">League D</button>
        `;

        let subTabsNav = document.getElementById('sub-group-tabs-nav');
        if (!subTabsNav) {
            subTabsNav = document.createElement('div');
            subTabsNav.id = 'sub-group-tabs-nav';
            subTabsNav.style.display = 'flex';
            subTabsNav.style.gap = '0.5rem';
            subTabsNav.style.marginTop = '0.75rem';
            groupTabsNav.parentNode.appendChild(subTabsNav);
        }
        
        const numGroups = activeDiv === 'D' ? 2 : 4;
        let subTabsHtml = '';
        for (let i = 1; i <= numGroups; i++) {
            subTabsHtml += `
                <button class="group-tab-btn ${activeNum === String(i) ? 'active' : ''}" data-num="${i}" style="padding: 0.35rem 0.75rem; font-size: 0.85rem; border-radius: 6px;">
                    Group ${i}
                </button>
            `;
        }
        subTabsNav.innerHTML = subTabsHtml;

        groupTabsNav.querySelectorAll('[data-div]').forEach(btn => {
            btn.addEventListener('click', () => {
                const div = btn.getAttribute('data-div');
                switchToGroup(`${div}1`);
            });
        });

        subTabsNav.querySelectorAll('[data-num]').forEach(btn => {
            btn.addEventListener('click', () => {
                const num = btn.getAttribute('data-num');
                switchToGroup(`${activeDiv}${num}`);
            });
        });
    }

    function restoreStandardTabs() {
        const subTabsNav = document.getElementById('sub-group-tabs-nav');
        if (subTabsNav) subTabsNav.remove();
        
        if (!groupTabsNav) return;
        if (groupTabsNav.querySelector('[data-group="A"]') && groupTabsNav.querySelector('[data-group="L"]')) {
            return;
        }
        
        let html = '';
        for (let i = 65; i <= 76; i++) {
            const letter = String.fromCharCode(i);
            html += `<button class="group-tab-btn" data-group="${letter}">Group ${letter}</button>\n`;
        }
        html += `<button class="group-tab-btn thirds-tab" data-group="thirds"><i class="fa-solid fa-award"></i> Best 3rd</button>`;
        groupTabsNav.innerHTML = html;

        groupTabsNav.querySelectorAll('.group-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const target = btn.getAttribute('data-group');
                switchToGroup(target);
            });
        });
    }

    function updateTabsUI() {
        if (!groupTabsNav) return;
        if (formatEngine === 'nations_league') {
            renderNationsLeagueTabs();
        } else {
            restoreStandardTabs();
            groupTabsNav.querySelectorAll('.group-tab-btn').forEach(btn => {
                if (btn.getAttribute('data-group') === activeGroup) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
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
            if (formatEngine === 'nations_league' && activeGroup.length >= 2) {
                const div = activeGroup[0];
                const num = activeGroup.slice(1);
                document.title = `League ${div} Group ${num} Standings | findfootball.games`;
                document.getElementById('group-title-header').innerText = `LEAGUE ${div} GROUP ${num}`;
            } else {
                document.title = `Group ${activeGroup} Standings | findfootball.games`;
                document.getElementById('group-title-header').innerText = `GROUP ${activeGroup}`;
            }
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

    formatEngine = 'group_knockout';
    competitionName = 'World Cup';

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    async function resolveAndTimezoneFetch() {
        // Fetch format engine first
        try {
            const compRes = await fetch('/api/competitions');
            if (compRes.ok) {
                const competitions = await compRes.json();
                const activeId = localStorage.getItem('findfootball-tournament-id');
                let found = null;
                competitions.forEach(comp => {
                    comp.tournaments.forEach(tourney => {
                        if (String(tourney.id) === String(activeId) || (!activeId && tourney.status === 'Active')) {
                            found = { comp, tourney };
                        }
                    });
                });
                if (found) {
                    formatEngine = found.comp.format_engine;
                    competitionName = found.comp.name;
                }
            }
        } catch (e) {
            console.error("Error fetching format engine in group.js", e);
        }

        updateTabsUI();

        if (toggleMatrixBtn) {
            if (formatEngine === 'league_phase_knockout') {
                toggleMatrixBtn.style.display = 'inline-flex';
            } else {
                toggleMatrixBtn.style.display = 'none';
                if (activeView === 'matrix') {
                    activeView = 'schedule';
                    localStorage.setItem('findfootball-group-view', activeView);
                }
            }
        }

        // Adjust UI elements for league format
        const tabsRow = document.querySelector('.group-selector-tabs-wrapper');
        const standingsFootnote = document.querySelector('.standings-footnote');
        const tableTitle = document.querySelector('#group-standings-section h3');
        
        if (formatEngine === 'league' || formatEngine === 'league_phase_knockout') {
            if (tabsRow) tabsRow.style.display = 'none';
            if (standingsFootnote) {
                if (formatEngine === 'league_phase_knockout') {
                    standingsFootnote.innerHTML = `<i class="fa-solid fa-info-circle"></i> League Phase for ${competitionName}. Top 8 auto-qualify for Round of 16. Positions 9–24 enter Play-offs.`;
                } else {
                    standingsFootnote.innerHTML = `<i class="fa-solid fa-info-circle"></i> Standings for ${competitionName}. Rankings determined by points, GD, GF, and ELO.`;
                }
            }
            if (tableTitle) {
                tableTitle.innerHTML = `<i class="fa-solid fa-table-list"></i> ${competitionName} Table`;
            }
            activeGroup = 'STANDINGS';
        } else if (formatEngine === 'nations_league') {
            if (tabsRow) tabsRow.style.display = 'block';
            if (standingsFootnote) {
                standingsFootnote.innerHTML = `<i class="fa-solid fa-info-circle"></i> UEFA Nations League. Group winners qualify for Finals (League A) or promotion. Bottom teams are relegated.`;
            }
            if (tableTitle) {
                tableTitle.innerHTML = `<i class="fa-solid fa-table-list"></i> Group Table`;
            }
        } else {
            if (tabsRow) tabsRow.style.display = 'block';
            if (standingsFootnote) {
                standingsFootnote.innerHTML = `<i class="fa-solid fa-info-circle"></i> Top two teams qualify for the Round of 32 knockout stage. Plus 8 best 3rd teams.`;
            }
            if (tableTitle) {
                tableTitle.innerHTML = `<i class="fa-solid fa-table-list"></i> Group Table`;
            }
        }

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
            const tournamentId = localStorage.getItem('findfootball-tournament-id') || '';
            const res = await fetch(`/api/group/${encodeURIComponent(activeGroup)}?tz=${encodeURIComponent(resolvedTimezone)}${tournamentId ? `&tournament_id=${tournamentId}` : ''}`);
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
                <td class="col-team">
                    <div class="clickable-team-row" data-name="${team.name}">
                        <img src="${getFlagUrl(team)}" class="table-team-flag" alt="${team.name}">
                        <span class="table-team-name">${team.name}</span>
                    </div>
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
                window.location.href = `/team/${encodeURIComponent(team.name)}`;
            });
            
            thirdsTbody.appendChild(tr);
        });
    }

    async function fetchAndRenderProjectedMatches() {
        const projectedCard = document.getElementById('projected-knockout-card');
        const projectedContainer = document.getElementById('projected-matches-container');
        
        if (!projectedCard || !projectedContainer) return;
        
        if (activeGroup === 'THIRDS' || formatEngine === 'league') {
            projectedCard.style.display = 'none';
            return;
        }
        
        projectedContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading projected matchups...</div>';
        
        try {
            const tournamentId = localStorage.getItem('findfootball-tournament-id') || '';
            const res = await fetch(`/api/bracket${tournamentId ? `?tournament_id=${tournamentId}` : ''}`);
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
        
        const isPreSeason = standings.every(t => t.played === 0);
        let bannerEl = document.getElementById('preseason-banner');
        if ((formatEngine === 'league' || formatEngine === 'league_phase_knockout') && isPreSeason) {
            if (!bannerEl) {
                bannerEl = document.createElement('div');
                bannerEl.id = 'preseason-banner';
                bannerEl.className = 'alert-info-banner';
                bannerEl.style.padding = '0.75rem 1rem';
                bannerEl.style.marginBottom = '1rem';
                bannerEl.style.borderRadius = '8px';
                bannerEl.style.background = 'rgba(245, 158, 11, 0.1)';
                bannerEl.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                bannerEl.style.color = '#F59E0B';
                bannerEl.style.fontSize = '0.9rem';
                bannerEl.style.fontWeight = '500';
                bannerEl.innerHTML = `<i class="fa-solid fa-info-circle" style="margin-right: 0.5rem;"></i> Season hasn't started yet — teams ranked by ELO rating`;
                
                const card = document.getElementById('group-standings-section');
                const tableWrapper = card.querySelector('.table-wrapper');
                card.insertBefore(bannerEl, tableWrapper);
            }
            // Sort by ELO preseason
            standings.sort((a, b) => b.elo - a.elo);
        } else if (bannerEl) {
            bannerEl.remove();
        }

        standings.forEach((team, index) => {
            const rank = index + 1;
            
            let statusHtml = '';
            let qualifyClass = '';
            
            if (formatEngine === 'league') {
                statusHtml = `<span class="text-muted">—</span>`;
            } else if (formatEngine === 'league_phase_knockout') {
                if (rank <= 8) {
                    statusHtml = `<span class="qual-badge qualified" style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); color: #10b981;"><i class="fa-solid fa-circle-check"></i> R16 Auto</span>`;
                    qualifyClass = 'status-qualified';
                } else if (rank <= 24) {
                    statusHtml = `<span class="qual-badge playoff" style="background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); color: #3b82f6;"><i class="fa-solid fa-circle-right"></i> Playoff</span>`;
                    qualifyClass = 'status-playoff';
                } else {
                    statusHtml = `<span class="qual-badge eliminated" style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444;"><i class="fa-solid fa-circle-xmark"></i> Eliminated</span>`;
                    qualifyClass = 'status-eliminated';
                }
            } else if (team.status === 'Qualified') {
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
                <td class="col-team">
                    <div class="clickable-team-row" data-name="${team.name}">
                        <img src="${getFlagUrl(team)}" class="table-team-flag" alt="${team.name}">
                        <span class="table-team-name">${team.name}</span>
                    </div>
                </td>
                <td class="col-stat">${team.played}</td>
                <td class="col-stat">${team.won}</td>
                <td class="col-stat">${team.drawn}</td>
                <td class="col-stat">${team.lost}</td>
                <td class="col-stat">${team.goal_difference > 0 ? '+' : ''}${team.goal_difference}</td>
                <td class="col-pts font-weight-bold">${team.points}</td>
                <td class="col-status">${statusHtml}</td>
            `;
            
            tr.querySelector('.clickable-team-row').addEventListener('click', () => {
                window.location.href = `/team/${encodeURIComponent(team.name)}`;
            });
            
            standingsTbody.appendChild(tr);
        });
    }

    function renderMatches() {
        groupMatchesContainer.innerHTML = '';
        if (matrixContainer) matrixContainer.innerHTML = '';
        const fixtures = activeGroupData.fixtures;
        if (!fixtures || fixtures.length === 0) {
            groupMatchesContainer.innerHTML = '<div class="loading-spinner"><p>No matches scheduled in this group.</p></div>';
            return;
        }

        if (activeView === 'schedule') {
            renderScheduleView(fixtures);
        } else if (activeView === 'leaderboard') {
            renderLeaderboardView(fixtures);
        } else if (activeView === 'matrix') {
            renderMatrixView(fixtures);
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

    function renderMatrixView(fixtures) {
        if (!matrixContainer) return;
        matrixContainer.innerHTML = '';

        const teams = activeGroupData.standings.map(s => s.name);
        if (teams.length === 0) {
            matrixContainer.innerHTML = '<div style="padding: 2rem; text-align: center;">No standings data available to build the matrix.</div>';
            return;
        }

        function getAbbreviation(name) {
            if (!name) return "TBD";
            const clean = name.replace(/[^a-zA-Z\s]/g, '').trim();
            const parts = clean.split(/\s+/);
            if (parts.length >= 2) {
                return (parts[0][0] + parts[1][0] + (parts[1][1] || '')).toUpperCase();
            }
            return clean.substring(0, 3).toUpperCase();
        }

        const fixtureMap = {};
        teams.forEach(home => {
            fixtureMap[home] = {};
        });

        fixtures.forEach(f => {
            if (f.home_team && f.away_team && fixtureMap[f.home_team.name]) {
                fixtureMap[f.home_team.name][f.away_team.name] = f;
            }
        });

        const table = document.createElement('table');
        table.className = 'matrix-table';
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.textAlign = 'center';
        table.style.fontSize = '0.85rem';

        const thead = document.createElement('thead');
        const headerTr = document.createElement('tr');
        
        const cornerTh = document.createElement('th');
        cornerTh.className = 'matrix-corner';
        cornerTh.style.position = 'sticky';
        cornerTh.style.left = '0';
        cornerTh.style.zIndex = '3';
        cornerTh.style.background = 'var(--bg-glass-card, rgba(30, 41, 59, 0.8))';
        cornerTh.style.backdropFilter = 'blur(12px)';
        cornerTh.style.borderBottom = '1px solid rgba(255, 255, 255, 0.1)';
        cornerTh.style.borderRight = '1px solid rgba(255, 255, 255, 0.1)';
        cornerTh.style.padding = '0.4rem 0.5rem';
        cornerTh.innerHTML = `<span style="font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase;">H \\ A</span>`;
        headerTr.appendChild(cornerTh);

        teams.forEach(team => {
            const th = document.createElement('th');
            th.style.padding = '0.4rem 0.5rem';
            th.style.borderBottom = '1px solid rgba(255, 255, 255, 0.1)';
            th.style.fontWeight = '600';
            th.style.minWidth = '32px';
            th.style.color = 'var(--text-secondary)';
            th.title = team;
            th.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; width: 100%;">
                    <img src="${getFlagUrl(team)}" style="width: 20px; height: 20px; object-fit: contain; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4));" alt="${team}">
                </div>
            `;
            headerTr.appendChild(th);
        });
        thead.appendChild(headerTr);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        teams.forEach((homeTeam) => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
            
            const rowHeader = document.createElement('td');
            rowHeader.className = 'matrix-row-header';
            rowHeader.style.position = 'sticky';
            rowHeader.style.left = '0';
            rowHeader.style.zIndex = '2';
            rowHeader.style.background = 'var(--bg-glass-card, rgba(30, 41, 59, 0.8))';
            rowHeader.style.backdropFilter = 'blur(12px)';
            rowHeader.style.borderRight = '1px solid rgba(255, 255, 255, 0.1)';
            rowHeader.style.padding = '0.4rem 0.5rem';
            rowHeader.style.textAlign = 'center';
            rowHeader.title = homeTeam;
            rowHeader.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; width: 100%;">
                    <img src="${getFlagUrl(homeTeam)}" style="width: 20px; height: 20px; object-fit: contain; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.4));" alt="${homeTeam}">
                </div>
            `;
            tr.appendChild(rowHeader);

            teams.forEach((awayTeam) => {
                const td = document.createElement('td');
                td.style.padding = '0.4rem 0.5rem';
                td.style.position = 'relative';
                
                if (homeTeam === awayTeam) {
                    td.style.background = 'rgba(255, 255, 255, 0.03)';
                    td.innerHTML = `<div style="width: 100%; height: 100%; color: rgba(255,255,255,0.15); font-size: 1.1rem;"><i class="fa-solid fa-ban"></i></div>`;
                } else {
                    const match = fixtureMap[homeTeam] ? fixtureMap[homeTeam][awayTeam] : null;
                    if (match) {
                        td.className = 'matrix-cell clickable-matrix-cell';
                        td.style.cursor = 'pointer';
                        td.style.fontWeight = '600';
                        td.title = `${homeTeam} vs ${awayTeam}`;
                        
                        const watchScore = match.watchability ? match.watchability.overall : match.watchability_score;
                        let watchClass = getRatingClass(watchScore);
                        let indicatorColor = 'transparent';
                        if (watchClass === 'must-watch') indicatorColor = '#F59E0B';
                        else if (watchClass === 'recommended') indicatorColor = '#10B981';
                        else if (watchClass === 'average') indicatorColor = '#3B82F6';
                        
                        if (indicatorColor !== 'transparent') {
                            td.style.borderLeft = `3px solid ${indicatorColor}`;
                        }

                        if (match.status === 'Finished') {
                            td.innerHTML = `<span style="color: var(--text-primary); font-size: 0.85rem;">${match.score}</span>`;
                        } else {
                            let displayDate = 'TBD';
                            if (match.date) {
                                try {
                                    const d = new Date(match.date);
                                    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                                    displayDate = `${d.getDate()} ${months[d.getMonth()]}`;
                                } catch (e) {
                                    displayDate = match.formatted_date_short || 'TBD';
                                }
                            }
                            td.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.75rem;">${displayDate}</span>`;
                        }

                        td.addEventListener('click', () => {
                            openMatchDetails(match);
                        });
                    } else {
                        td.innerHTML = `<span style="color: rgba(255,255,255,0.1); font-weight: 300;">—</span>`;
                    }
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        matrixContainer.appendChild(table);
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
                window.location.href = `/team/${encodeURIComponent(teamBox.getAttribute('data-name'))}`;
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

    function updateToggleButtonsUI() {
        if (toggleScheduleBtn) toggleScheduleBtn.classList.remove('active');
        if (toggleLeaderboardBtn) toggleLeaderboardBtn.classList.remove('active');
        if (toggleMatrixBtn) toggleMatrixBtn.classList.remove('active');

        if (activeView === 'schedule') {
            if (toggleScheduleBtn) toggleScheduleBtn.classList.add('active');
            if (groupMatchesContainer) groupMatchesContainer.style.display = 'block';
            if (matrixContainer) matrixContainer.style.display = 'none';
        } else if (activeView === 'leaderboard') {
            if (toggleLeaderboardBtn) toggleLeaderboardBtn.classList.add('active');
            if (groupMatchesContainer) groupMatchesContainer.style.display = 'block';
            if (matrixContainer) matrixContainer.style.display = 'none';
        } else if (activeView === 'matrix') {
            if (toggleMatrixBtn) toggleMatrixBtn.classList.add('active');
            if (groupMatchesContainer) groupMatchesContainer.style.display = 'none';
            if (matrixContainer) matrixContainer.style.display = 'block';
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
