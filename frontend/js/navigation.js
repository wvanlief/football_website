document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    const isMainPage = (path === '/' || path === '/recommended');

    // 1. Create the horizontal pill bar under the header if it's missing (only on deep pages)
    const mainEl = document.querySelector('main.app-main');
    if (mainEl && !isMainPage && !document.getElementById('competition-pills-nav')) {
        const pillNav = document.createElement('div');
        pillNav.id = 'competition-pills-nav';
        pillNav.className = 'competition-pills-nav-bar glass';
        mainEl.insertBefore(pillNav, mainEl.firstChild);
    }

    // 2. Fetch competitions and tournaments
    fetch('/api/competitions')
        .then(res => res.json())
        .then(competitions => {
            let selectedId = localStorage.getItem('findfootball-tournament-id');
            let activeTourney = null;
            
            // Build a flat list of active tournaments
            const activeTourneysList = [];
            competitions.forEach(comp => {
                comp.tournaments.forEach(tourney => {
                    if (tourney.status === 'Active') {
                        tourney.competition = comp;
                        activeTourneysList.push(tourney);
                    }
                });
            });

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
            
            // Populate selector pills if container exists
            const pillsContainer = document.getElementById('competition-pills-nav');
            if (pillsContainer) {
                pillsContainer.innerHTML = '';
                
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
                
                categories.forEach(cat => {
                    if (cat.items.length === 0) return;
                    
                    const groupWrapper = document.createElement('div');
                    groupWrapper.className = 'comp-category-group';
                    groupWrapper.style.cssText = 'display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; background: rgba(0,0,0,0.2); border-radius: 20px; margin-right: 12px; border: 1px solid rgba(255,255,255,0.05);';
                    
                    const catLabel = document.createElement('span');
                    catLabel.className = 'comp-category-label';
                    catLabel.style.cssText = 'font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); padding: 0 6px; display: flex; align-items: center; gap: 4px;';
                    catLabel.innerHTML = `<i class="fa-solid ${cat.icon}"></i> ${cat.name}`;
                    groupWrapper.appendChild(catLabel);
                    
                    cat.items.forEach(tourney => {
                        const comp = tourney.competition;
                        const btn = document.createElement('button');
                        btn.className = `comp-nav-pill${String(tourney.id) === String(selectedId) ? ' active' : ''}`;
                        btn.innerHTML = `<span class="comp-nav-badge">${comp.badge || '⚽'}</span> <span class="comp-nav-text">${comp.name}</span>`;
                        btn.addEventListener('click', () => {
                            if (String(tourney.id) !== String(selectedId)) {
                                localStorage.setItem('findfootball-tournament-id', tourney.id);
                                
                                const newEngine = comp.format_engine;
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
                        });
                        groupWrapper.appendChild(btn);
                    });
                    
                    pillsContainer.appendChild(groupWrapper);
                });
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
});
