document.addEventListener('DOMContentLoaded', () => {
    // 1. Find the controls-area and insert the competition select dropdown if it's missing
    const controlsArea = document.querySelector('.controls-area');
    if (controlsArea && !document.getElementById('competition-select-wrapper')) {
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
            if (!selectEl) return;
            selectEl.innerHTML = '';
            
            let selectedId = localStorage.getItem('findfootball-tournament-id');
            let activeTourney = null;
            
            competitions.forEach(comp => {
                comp.tournaments.forEach(tourney => {
                    const option = document.createElement('option');
                    option.value = tourney.id;
                    option.textContent = `${comp.name} (${tourney.season_name})`;
                    option.setAttribute('data-engine', comp.format_engine);
                    option.setAttribute('data-name', comp.name);
                    selectEl.appendChild(option);
                    
                    if (String(tourney.id) === String(selectedId)) {
                        activeTourney = tourney;
                        activeTourney.competition = comp;
                    }
                    if (!activeTourney && tourney.status === 'Active') {
                        activeTourney = tourney;
                        activeTourney.competition = comp;
                    }
                });
            });
            
            // Default to the first option if none is selected/active
            if (!activeTourney && selectEl.options.length > 0) {
                const firstOption = selectEl.options[0];
                selectedId = firstOption.value;
                localStorage.setItem('findfootball-tournament-id', selectedId);
                selectEl.value = selectedId;
            } else if (activeTourney) {
                selectedId = activeTourney.id;
                localStorage.setItem('findfootball-tournament-id', selectedId);
                selectEl.value = selectedId;
            }
            
            // Get format engine of selected tournament
            const selectedOption = selectEl.options[selectEl.selectedIndex];
            const engine = selectedOption ? selectedOption.getAttribute('data-engine') : 'group_knockout';
            const compName = selectedOption ? selectedOption.getAttribute('data-name') : 'World Cup';
            
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
                subtitleEl.textContent = `${compName} Watchability Index`;
            }
            
            // 5. Handle change event
            selectEl.addEventListener('change', () => {
                const newId = selectEl.value;
                localStorage.setItem('findfootball-tournament-id', newId);
                
                const path = window.location.pathname;
                const selectedOpt = selectEl.options[selectEl.selectedIndex];
                const newEngine = selectedOpt ? selectedOpt.getAttribute('data-engine') : '';
                
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
        })
        .catch(err => console.error("Error loading competitions selector:", err));
});
