document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    const isMainPage = (path === '/' || path === '/recommended');

    // 1. Find the controls-area and insert the competition select dropdown if it's missing (only on deep pages)
    const controlsArea = document.querySelector('.controls-area');
    if (controlsArea && !isMainPage && !document.getElementById('competition-select-wrapper')) {
        const wrapper = document.createElement('div');
        wrapper.id = 'competition-select-wrapper';
        wrapper.className = 'competition-select-wrapper';
        wrapper.style.marginRight = '1rem';
        wrapper.innerHTML = `
            <i class="fa-solid fa-trophy competition-icon" style="margin-right: 0.5rem; color: var(--text-secondary);"></i>
            <select id="competition-select" class="timezone-select" style="background: transparent; border: none; color: var(--text-primary); font-family: var(--font-family); font-size: 0.85rem; font-weight: 600; outline: none; cursor: pointer;">
                <option value="">Loading...</option>
            </select>
        `;
        controlsArea.insertBefore(wrapper, controlsArea.firstChild);
    }

    const selectEl = document.getElementById('competition-select');
    
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

            // Populate selector if it exists
            if (selectEl) {
                selectEl.innerHTML = '';
                activeTourneysList.forEach(tourney => {
                    const comp = tourney.competition;
                    const option = document.createElement('option');
                    option.value = tourney.id;
                    option.textContent = `${comp.name} (${tourney.season_name})`;
                    option.setAttribute('data-engine', comp.format_engine);
                    option.setAttribute('data-name', comp.name);
                    selectEl.appendChild(option);
                });
            }
            
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
                if (selectEl) selectEl.value = selectedId;
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
                    groupsLink.innerHTML = '<i class="fa-solid fa-table-list"></i> Standings';
                    groupsLink.setAttribute('href', '/group/standings');
                }
            } else {
                if (bracketLink) bracketLink.style.display = 'inline-block';
                if (groupsLink) {
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
            
            // 6. Handle change event
            if (selectEl) {
                selectEl.addEventListener('change', () => {
                    const newId = selectEl.value;
                    localStorage.setItem('findfootball-tournament-id', newId);
                    
                    const matchingTourney = activeTourneysList.find(t => String(t.id) === String(newId));
                    const newEngine = matchingTourney ? matchingTourney.competition.format_engine : '';
                    
                    if (newEngine === 'league' && path.startsWith('/group/')) {
                        window.location.href = '/group/standings';
                    } else if (newEngine !== 'league' && path === '/group/standings') {
                        window.location.href = '/group/A';
                    } else if (newEngine === 'league' && path === '/bracket') {
                        window.location.href = '/';
                    } else {
                        window.location.reload();
                    }
                });
            }
        })
        .catch(err => console.error("Error loading competitions selector:", err));
});
