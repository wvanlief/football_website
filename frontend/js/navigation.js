document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    const isMainPage = (path === '/' || path === '/recommended');
    const usesCompetitionPicker = path === '/recommended' || path === '/bracket' || path === '/calendar' || path.startsWith('/group/');

    function competitionBadgeHtml(comp) {
        const b = (comp && comp.badge) || '⚽';
        if (typeof b === 'string' && (b.startsWith('http') || b.startsWith('/'))) {
            return `<img class="comp-picker-badge" src="${b}" alt="">`;
        }
        return `<span class="comp-picker-badge-emoji">${b}</span>`;
    }

    function navigateToTournament(tourney) {
        localStorage.setItem('findfootball-tournament-id', tourney.id);
        const newEngine = tourney.competition.format_engine;
        if (path === '/recommended') {
            if (newEngine === 'cup') {
                window.location.href = '/bracket';
            } else if (newEngine === 'group_knockout') {
                window.location.href = '/group/A';
            } else {
                window.location.href = '/group/standings';
            }
            return;
        }
        if ((newEngine === 'league' || newEngine === 'league_phase_knockout') && path.startsWith('/group/') && path !== '/group/standings') {
            window.location.href = '/group/standings';
        } else if (newEngine === 'cup') {
            window.location.href = '/bracket';
        } else if (newEngine === 'group_knockout' && path === '/group/standings') {
            window.location.href = '/group/A';
        } else if (newEngine === 'league' && path === '/bracket') {
            window.location.href = '/group/standings';
        } else {
            window.location.reload();
        }
    }

    function renderCompetitionPicker(pane, categories, selectedId) {
        const selectedCat = categories.find((cat) => cat.items.some((t) => String(t.id) === String(selectedId)));
        pane.innerHTML = `<div class="comp-picker-card">
            <input class="comp-picker-search" type="search" placeholder="Filter leagues…" aria-label="Filter leagues">
            ${categories.map((cat, i) => `
                <div class="comp-picker-drop${(selectedCat && selectedCat.name === cat.name) || (!selectedCat && i === 0) ? ' is-open' : ''}">
                    <button type="button" class="comp-picker-toggle">
                        <span><i class="fa-solid ${cat.icon}"></i> ${cat.name}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </button>
                    <div class="comp-picker-menu">
                        ${cat.items.map((t) => `
                            <button type="button" class="comp-picker-item${String(t.id) === String(selectedId) ? ' is-active' : ''}" data-tid="${t.id}" data-name="${(t.competition.name || '').toLowerCase().replace(/"/g, '')}">
                                ${competitionBadgeHtml(t.competition)}
                                <span>${t.competition.name}</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `).join('')}
        </div>`;

        pane.querySelectorAll('.comp-picker-toggle').forEach((btn) => {
            btn.addEventListener('click', () => {
                const drop = btn.parentElement;
                const open = drop.classList.contains('is-open');
                pane.querySelectorAll('.comp-picker-drop').forEach((d) => d.classList.remove('is-open'));
                if (!open) drop.classList.add('is-open');
            });
        });

        const search = pane.querySelector('.comp-picker-search');
        search.addEventListener('input', () => {
            const q = search.value.trim().toLowerCase();
            pane.querySelectorAll('.comp-picker-item').forEach((item) => {
                item.style.display = !q || (item.getAttribute('data-name') || '').includes(q) ? '' : 'none';
            });
            if (q) {
                pane.querySelectorAll('.comp-picker-drop').forEach((d) => d.classList.add('is-open'));
            }
        });

        pane.querySelectorAll('.comp-picker-item').forEach((btn) => {
            btn.addEventListener('click', () => {
                const tid = btn.getAttribute('data-tid');
                if (String(tid) === String(selectedId)) return;
                const tourney = categories.flatMap((c) => c.items).find((t) => String(t.id) === String(tid));
                if (tourney) navigateToTournament(tourney);
            });
        });
    }

    // 1. Left competition picker on Hot List / Standings / Bracket / Calendar
    const mainEl = document.querySelector('main.app-main');
    if (mainEl && usesCompetitionPicker && !document.getElementById('competition-picker')) {
        document.body.classList.add('has-comp-picker');
        const content = document.createElement('div');
        content.className = 'comp-picker-content';
        while (mainEl.firstChild) content.appendChild(mainEl.firstChild);
        const pane = document.createElement('aside');
        pane.id = 'competition-picker';
        pane.className = 'comp-picker-pane';
        pane.setAttribute('aria-label', 'Competitions');
        mainEl.appendChild(pane);
        mainEl.appendChild(content);
    }

    // 2. Fetch competitions and tournaments
    fetch('/api/competitions')
        .then(res => res.json())
        .then(competitions => {
            let selectedId = localStorage.getItem('findfootball-tournament-id');
            let activeTourney = null;
            
            // Build a flat list of the latest active tournament edition per competition
            const activeTourneysMap = new Map();
            competitions.forEach(comp => {
                comp.tournaments.forEach(tourney => {
                    if (tourney.status === 'Active') {
                        tourney.competition = comp;
                        const existing = activeTourneysMap.get(comp.id);
                        if (!existing || tourney.id > existing.id) {
                            activeTourneysMap.set(comp.id, tourney);
                        }
                    }
                });
            });
            const activeTourneysList = Array.from(activeTourneysMap.values());

            // Find matching active tournament
            if (selectedId) {
                activeTourney = activeTourneysList.find(t => String(t.id) === String(selectedId));
            }
            if (!activeTourney && activeTourneysList.length > 0) {
                activeTourney = activeTourneysList[0];
            }
            
            if (activeTourney) {
                selectedId = activeTourney.id;
                localStorage.setItem('findfootball-tournament-id', selectedId);
            }
            
            const pickerPane = document.getElementById('competition-picker');
            if (pickerPane) {
                const categories = [
                    { name: 'Top Leagues', icon: 'fa-trophy', items: [] },
                    { name: 'European Cups', icon: 'fa-star', items: [] },
                    { name: 'Tournaments & Cups', icon: 'fa-globe', items: [] }
                ];

                activeTourneysList.forEach(tourney => {
                    const comp = tourney.competition;
                    if (comp.format_engine === 'league_phase_knockout' || comp.name.includes('Champions') || comp.name.includes('Europa')) {
                        categories[1].items.push(tourney);
                    } else if (comp.type === 'League' || comp.format_engine === 'league') {
                        categories[0].items.push(tourney);
                    } else {
                        categories[2].items.push(tourney);
                    }
                });

                renderCompetitionPicker(pickerPane, categories.filter((c) => c.items.length), selectedId);
            }
            
            // Get format engine of selected tournament
            const engine = activeTourney ? activeTourney.competition.format_engine : 'group_knockout';
            const compName = activeTourney ? activeTourney.competition.name : 'World Cup';
            
            // 3. Update the Nav Bar based on competition format engine
            const bracketLink = document.querySelector('a[href="/bracket"]');
            const groupsLink = document.querySelector('a[href="/group/A"], a[href^="/group/"]');
            
            if (engine === 'league') {
                if (bracketLink) bracketLink.style.display = 'none';
                if (groupsLink) {
                    groupsLink.style.display = 'inline-block';
                    groupsLink.innerHTML = '<i class="fa-solid fa-table-list"></i> Standings';
                    groupsLink.setAttribute('href', '/group/standings');
                }
            } else if (engine === 'league_phase_knockout') {
                if (bracketLink) bracketLink.style.display = 'inline-block';
                if (groupsLink) {
                    groupsLink.style.display = 'inline-block';
                    groupsLink.innerHTML = '<i class="fa-solid fa-table-list"></i> Standings';
                    groupsLink.setAttribute('href', '/group/standings');
                }
            } else if (engine === 'cup') {
                if (groupsLink) groupsLink.style.display = 'none';
                if (bracketLink) bracketLink.style.display = 'inline-block';
            } else {
                if (bracketLink) bracketLink.style.display = 'inline-block';
                if (groupsLink) {
                    groupsLink.style.display = 'inline-block';
                    groupsLink.innerHTML = '<i class="fa-solid fa-table-list"></i> Groups';
                    groupsLink.setAttribute('href', '/group/A');
                }
            }
            
            // 4. Update Header Subtitle text dynamically
            const subtitleEl = document.querySelector('.logo-text p');
            if (subtitleEl) {
                if (isMainPage) {
                    subtitleEl.textContent = 'Watchability Index';
                } else {
                    subtitleEl.textContent = `${compName} Watchability Index`;
                }
            }

            // 5. Update Document Title dynamically
            if (!isMainPage) {
                if (path.startsWith('/group/')) {
                    const groupLetter = path.split('/').pop();
                    if (groupLetter === 'standings') {
                        document.title = `${compName} Standings | findfootball.games`;
                    } else {
                        document.title = `${compName} Group ${groupLetter.toUpperCase()} | findfootball.games`;
                    }
                } else if (path === '/bracket') {
                    document.title = `${compName} Bracket | findfootball.games`;
                } else if (path === '/calendar') {
                    document.title = `${compName} Calendar | findfootball.games`;
                }
            }
        })
        .catch(err => console.error("Error loading competitions selector:", err));

    // 6. Off-Canvas Competitions Drawer Controller
    const hamburgerBtn = document.getElementById('hamburger-menu-btn');
    const closeDrawerBtn = document.getElementById('close-drawer-btn');
    const offcanvasSidebar = document.getElementById('offcanvas-sidebar');

    function toggleOffcanvasDrawer() {
        if (offcanvasSidebar) offcanvasSidebar.classList.toggle('open');
    }

    if (hamburgerBtn) hamburgerBtn.addEventListener('click', toggleOffcanvasDrawer);
    if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', toggleOffcanvasDrawer);

    document.querySelectorAll('.drawer-item').forEach(dBtn => {
        dBtn.addEventListener('click', () => {
            document.querySelectorAll('.drawer-item').forEach(b => b.classList.remove('active'));
            dBtn.classList.add('active');
            const filter = dBtn.getAttribute('data-filter');
            if (typeof window.filterMatchesByName === 'function') {
                window.filterMatchesByName(filter);
            }
            if (offcanvasSidebar) offcanvasSidebar.classList.remove('open');
        });
    });

    // 7. Top Inline Geographic Waterfall Filter Controller
    const triggerChip = document.getElementById('trigger-drawer-chip');
    if (triggerChip) {
        triggerChip.addEventListener('click', toggleOffcanvasDrawer);
    }

    const GEO_DATA = {
        europe: {
            countries: [
                { 
                    id: 'england', 
                    name: 'England', 
                    icon: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 
                    keywords: ['england', 'premier league', 'epl', 'fa cup', 'man city', 'arsenal', 'liverpool', 'chelsea', 'man united', 'tottenham'], 
                    teams: ['Man City', 'Arsenal', 'Liverpool', 'Chelsea'] 
                },
                { 
                    id: 'spain', 
                    name: 'Spain', 
                    icon: '🇪🇸', 
                    keywords: ['spain', 'la liga', 'copa del rey', 'real madrid', 'barcelona', 'atletico'], 
                    teams: ['Real Madrid', 'Barcelona', 'Atletico'] 
                },
                { 
                    id: 'italy', 
                    name: 'Italy', 
                    icon: '🇮🇹', 
                    keywords: ['italy', 'serie a', 'coppa italia', 'inter', 'ac milan', 'juventus'], 
                    teams: ['Inter', 'AC Milan', 'Juventus'] 
                },
                { 
                    id: 'germany', 
                    name: 'Germany', 
                    icon: '🇩🇪', 
                    keywords: ['germany', 'bundesliga', 'bayern', 'dortmund', 'bayer leverkusen'], 
                    teams: ['Bayern', 'Dortmund', 'Bayer Leverkusen'] 
                }
            ]
        },
        americas: {
            countries: [
                { 
                    id: 'argentina', 
                    name: 'Argentina', 
                    icon: '🇦🇷', 
                    keywords: ['argentina', 'river plate', 'boca juniors', 'aldosivi', 'gimnasia', 'deportivo riestra', 'barracas', 'rosario central', 'regular season', 'liga profesional', 'primera division'], 
                    teams: ['River Plate', 'Boca Juniors', 'Aldosivi', 'Gimnasia L.P.', 'Deportivo Riestra', 'Barracas Central', 'Rosario Central'] 
                },
                { 
                    id: 'brazil', 
                    name: 'Brazil', 
                    icon: '🇧🇷', 
                    keywords: ['brazil', 'flamengo', 'palmeiras', 'juventude', 'atletico-mg', 'gremio', 'mirassol', 'internacional', 'corinthians', 'brasileirao', 'serie a', 'round of 16'], 
                    teams: ['Flamengo', 'Palmeiras', 'Juventude', 'Atletico-MG', 'Gremio', 'Mirassol', 'Internacional', 'Corinthians'] 
                }
            ]
        }
    };

    const waterfallBar = document.getElementById('inline-waterfall-bar');
    if (waterfallBar) {
        waterfallBar.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                waterfallBar.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');

                const geoKey = btn.getAttribute('data-geo');
                const subEl = document.getElementById('geo-sub-level');
                const chipsEl = document.getElementById('geo-country-chips');
                const teamEl = document.getElementById('geo-team-level');

                if (teamEl) teamEl.style.display = 'none';

                if (geoKey === 'all' || !GEO_DATA[geoKey]) {
                    if (subEl) subEl.style.display = 'none';
                    if (typeof window.filterMatchesByName === 'function') window.filterMatchesByName('all');
                } else {
                    if (subEl) subEl.style.display = 'inline-flex';
                    if (typeof window.filterMatchesByName === 'function') window.filterMatchesByName(geoKey);
                    if (chipsEl) {
                        chipsEl.innerHTML = GEO_DATA[geoKey].countries.map(c => `
                            <button class="facet-chip sub-chip" data-country="${c.name}">
                                <span>${c.icon}</span> ${c.name}
                            </button>
                        `).join('');

                        chipsEl.querySelectorAll('.sub-chip').forEach(cBtn => {
                            cBtn.addEventListener('click', () => {
                                chipsEl.querySelectorAll('.sub-chip').forEach(s => s.classList.remove('active'));
                                cBtn.classList.add('active');

                                const countryName = cBtn.getAttribute('data-country');
                                const countryObj = GEO_DATA[geoKey].countries.find(x => x.name === countryName);
                                
                                if (countryObj && countryObj.keywords && typeof window.filterMatchesByKeywords === 'function') {
                                    window.filterMatchesByKeywords(countryObj.keywords);
                                } else if (typeof window.filterMatchesByName === 'function') {
                                    window.filterMatchesByName(countryName);
                                }

                                if (countryObj && countryObj.teams.length > 0 && teamEl) {
                                    teamEl.style.display = 'inline-flex';
                                    const teamChipsEl = document.getElementById('geo-team-chips');
                                    if (teamChipsEl) {
                                        teamChipsEl.innerHTML = countryObj.teams.map(t => `
                                            <button class="facet-chip sub-chip" data-team="${t}">${t}</button>
                                        `).join('');

                                        teamChipsEl.querySelectorAll('.sub-chip').forEach(tBtn => {
                                            tBtn.addEventListener('click', () => {
                                                teamChipsEl.querySelectorAll('.sub-chip').forEach(t => t.classList.remove('active'));
                                                tBtn.classList.add('active');
                                                if (typeof window.filterMatchesByName === 'function') {
                                                    window.filterMatchesByName(tBtn.getAttribute('data-team'));
                                                }
                                            });
                                        });
                                    }
                                }
                            });
                        });
                    }
                }
            });
        });
    }
});
