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

    function getFlagUrl(countryName, size = 'w40') {
        const code = COUNTRY_FLAGS[countryName];
        if (code) {
            return `https://flagcdn.com/${size}/${code}.png`;
        }
        return 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAyNCAyNCcgd2lkdGg9JzI0JyBoZWlnaHQ9JzI0Jz48Y2lyY2xlIGN4PScxMicgY3k9JzEyJyByPScxMCcgZmlsbD0nIzY2NicvPjwvc3ZnPg==';
    }

    // DOM Elements
    const toast = document.getElementById('toast');
    
    const championBannerContainer = document.getElementById('champion-banner-container');
    const round32List = document.getElementById('round-32-list');
    const round16List = document.getElementById('round-16-list');
    const quarterFinalsList = document.getElementById('quarter-finals-list');
    const semiFinalsList = document.getElementById('semi-finals-list');
    const finalsList = document.getElementById('finals-list');

    // Tab Elements
    const tabTreeBtn = document.getElementById('tab-tree-btn');
    const tabProbBtn = document.getElementById('tab-prob-btn');
    const treeTabPanel = document.getElementById('tree-tab-panel');
    const probTabPanel = document.getElementById('prob-tab-panel');

    // Leaderboard Control Elements
    const teamSearch = document.getElementById('team-search');
    const leaderboardSort = document.getElementById('leaderboard-sort');
    const simulationMeta = document.getElementById('simulation-meta');
    const simulationTimestamp = document.getElementById('simulation-timestamp');
    const leaderboardBody = document.getElementById('leaderboard-body');
    const simulationLoadingOverlay = document.getElementById('simulation-loading-overlay');

    // Store fetched probabilities globally for search/filtering
    let allProbabilities = [];
    let projectedChampion = "";



    // Tab Toggling Action
    function switchTab(tabId) {
        if (tabId === 'tree') {
            tabTreeBtn.classList.add('active');
            tabProbBtn.classList.remove('active');
            treeTabPanel.classList.add('active');
            probTabPanel.classList.remove('active');
            localStorage.setItem('active-bracket-tab', 'tree');
        } else {
            tabTreeBtn.classList.remove('active');
            tabProbBtn.classList.add('active');
            treeTabPanel.classList.remove('active');
            probTabPanel.classList.add('active');
            localStorage.setItem('active-bracket-tab', 'prob');
            // Force redraw/re-animate of probability fills when switching
            renderLeaderboard();
        }
    }

    tabTreeBtn.addEventListener('click', () => switchTab('tree'));
    tabProbBtn.addEventListener('click', () => switchTab('prob'));

    // Apply saved tab
    const savedTab = localStorage.getItem('active-bracket-tab') || 'tree';
    switchTab(savedTab);

    // Resolve details and trigger fetch
    fetchBracketDetails();



    // Fetch Bracket Data
    async function fetchBracketDetails() {
        showLoadingSpinners();
        try {
            const tournamentId = localStorage.getItem('findfootball-tournament-id') || '';
            const res = await fetch(`/api/bracket${tournamentId ? `?tournament_id=${tournamentId}` : ''}`);
            const data = await res.json();
            
            const bracket = data.bracket;
            allProbabilities = data.probabilities || [];
            projectedChampion = bracket.champion;

            // Render Bracket Tree
            renderChampion(bracket.final);
            renderRound(round32List, bracket.r32);
            renderRound(round16List, bracket.r16);
            renderRound(quarterFinalsList, bracket.qf);
            renderRound(semiFinalsList, bracket.sf);
            renderFinals(bracket.third, bracket.final);

            // Populate Leaderboard Metadata
            if (simulationMeta) {
                simulationMeta.innerText = `${(data.num_simulations || 5000).toLocaleString()} runs`;
            }
            if (simulationTimestamp && data.last_updated) {
                const dateObj = new Date(data.last_updated);
                simulationTimestamp.innerText = dateObj.toLocaleString();
            }

            // Render Leaderboard Table
            renderLeaderboard();
        } catch (err) {
            console.error("Failed to load bracket data", err);
            round32List.innerHTML = '<p class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading bracket.</p>';
            if (leaderboardBody) {
                leaderboardBody.innerHTML = '<tr><td colspan="11" class="text-danger text-center"><i class="fa-solid fa-triangle-exclamation"></i> Error loading win probabilities.</td></tr>';
            }
        }
    }

    function showLoadingSpinners() {
        const spinner = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i></div>';
        round32List.innerHTML = spinner;
        round16List.innerHTML = spinner;
        quarterFinalsList.innerHTML = spinner;
        semiFinalsList.innerHTML = spinner;
        finalsList.innerHTML = spinner;
        championBannerContainer.innerHTML = '';
        if (leaderboardBody) {
            leaderboardBody.innerHTML = '<tr><td colspan="11" class="text-center"><i class="fa-solid fa-circle-notch fa-spin text-warning"></i> Loading simulation statistics...</td></tr>';
        }
    }

    function renderChampion(finalMatch) {
        const champName = finalMatch.winner;
        championBannerContainer.innerHTML = `
            <div class="champion-projected-banner glass animate-champion">
                <i class="fa-solid fa-crown crown-champ"></i>
                <div class="champ-info">
                    <span class="champ-label">PROJECTED CHAMPION</span>
                    <h3 class="champ-title">${champName.toUpperCase()}</h3>
                </div>
                <img src="${getFlagUrl(champName, 'w80')}" class="champ-avatar-flag" alt="">
            </div>
        `;
        
        // Link click on champion banner
        championBannerContainer.querySelector('.champion-projected-banner').addEventListener('click', () => {
            window.location.href = `/team/${encodeURIComponent(champName)}`;
        });
    }

    function renderRound(container, matches) {
        container.innerHTML = '';
        matches.forEach(match => {
            const card = createMatchupCard(match);
            container.appendChild(card);
        });
    }

    function renderFinals(thirdMatch, finalMatch) {
        finalsList.innerHTML = '';
        
        // 1. Final Card
        const finalTitle = document.createElement('div');
        finalTitle.className = 'finals-group-title';
        finalTitle.innerHTML = '<i class="fa-solid fa-trophy text-warning"></i> WORLD CUP FINAL';
        finalsList.appendChild(finalTitle);
        
        const finalCard = createMatchupCard(finalMatch, true); // true highlights the champion
        finalsList.appendChild(finalCard);
        
        // 2. Third Place Card
        const thirdTitle = document.createElement('div');
        thirdTitle.className = 'finals-group-title margin-top-finals';
        thirdTitle.innerHTML = '<i class="fa-solid fa-medal text-muted"></i> THIRD PLACE PLAY-OFF';
        finalsList.appendChild(thirdTitle);
        
        const thirdCard = createMatchupCard(thirdMatch);
        finalsList.appendChild(thirdCard);
    }
    function formatMatchDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }

    function createMatchupCard(match, isFinal = false) {
        const card = document.createElement('div');
        card.className = 'bracket-matchup-card glass';
        if (isFinal) {
            card.classList.add('final-match-highlight');
        }
        
        const status = match.matchup_status || 'predicted';
        card.classList.add(status);
        
        const isWinner1 = match.winner === match.team1.name;
        const isWinner2 = match.winner === match.team2.name;
        
        let badgeHtml = '';
        if (status === 'official') {
            badgeHtml = '<i class="fa-solid fa-circle-check"></i> Played';
        } else if (status === 'scheduled') {
            badgeHtml = '<i class="fa-solid fa-calendar-check"></i> Matchup Set';
        } else {
            badgeHtml = '<i class="fa-solid fa-wand-magic-sparkles"></i> Predicted';
        }
        
        const dateHtml = match.date ? `
            <div class="bracket-match-header-row">
                <span class="bracket-match-date">
                    <i class="fa-regular fa-calendar-days"></i> ${formatMatchDate(match.date)}
                </span>
                <span class="bracket-match-status-badge ${status}">
                    ${badgeHtml}
                </span>
            </div>
        ` : '';

        card.innerHTML = `
            ${dateHtml}
            <!-- Team 1 -->
            <div class="bracket-team-row clickable-team-bracket ${isWinner1 ? 'winner' : 'loser'} ${match.team1.is_predicted ? 'predicted-team' : ''}" data-name="${match.team1.name}">
                <div class="team-identity-bracket">
                    <img src="${getFlagUrl(match.team1.name)}" class="bracket-team-flag" alt="">
                    <span class="bracket-team-name">
                        ${match.team1.name}
                        ${match.team1.is_predicted ? ' <i class="fa-solid fa-wand-magic-sparkles" style="color: #ff006e; font-size: 0.65rem; opacity: 0.8;" title="Predicted team"></i>' : ''}
                    </span>
                    ${match.team1.group_name ? `<span class="bracket-team-group">(Gr. ${match.team1.group_name})</span>` : ''}
                </div>
                <div class="team-stat-bracket">
                    <span class="bracket-elo">ELO ${match.team1.elo}</span>
                    ${isWinner1 ? '<i class="fa-solid fa-circle-check check-winner"></i>' : ''}
                </div>
            </div>
            
            <div class="bracket-vs-line">vs</div>
            
            <!-- Team 2 -->
            <div class="bracket-team-row clickable-team-bracket ${isWinner2 ? 'winner' : 'loser'} ${match.team2.is_predicted ? 'predicted-team' : ''}" data-name="${match.team2.name}">
                <div class="team-identity-bracket">
                    <img src="${getFlagUrl(match.team2.name)}" class="bracket-team-flag" alt="">
                    <span class="bracket-team-name">
                        ${match.team2.name}
                        ${match.team2.is_predicted ? ' <i class="fa-solid fa-wand-magic-sparkles" style="color: #ff006e; font-size: 0.65rem; opacity: 0.8;" title="Predicted team"></i>' : ''}
                    </span>
                    ${match.team2.group_name ? `<span class="bracket-team-group">(Gr. ${match.team2.group_name})</span>` : ''}
                </div>
                <div class="team-stat-bracket">
                    <span class="bracket-elo">ELO ${match.team2.elo}</span>
                    ${isWinner2 ? '<i class="fa-solid fa-circle-check check-winner"></i>' : ''}
                </div>
            </div>
        `;
        
        // Add clicks to navigate to country details
        card.querySelectorAll('.clickable-team-bracket').forEach(row => {
            row.addEventListener('click', () => {
                const teamName = row.getAttribute('data-name');
                window.location.href = `/team/${encodeURIComponent(teamName)}`;
            });
        });
        
        return card;
    }

    // Leaderboard Sorting & Filtering
    function renderLeaderboard() {
        if (!leaderboardBody) return;

        const searchQuery = teamSearch.value.trim().toLowerCase();
        const sortBy = leaderboardSort.value;

        // 1. Filter
        let filtered = allProbabilities.filter(p => p.team.toLowerCase().includes(searchQuery));

        // 2. Sort
        filtered.sort((a, b) => {
            if (sortBy === 'champion_pct') {
                return (b.champion_pct - a.champion_pct) || (b.runner_up_pct - a.runner_up_pct) || (b.sf_exit_pct - a.sf_exit_pct) || (b.elo - a.elo);
            } else if (sortBy === 'elo') {
                return (b.elo - a.elo) || (b.champion_pct - a.champion_pct);
            } else if (sortBy === 'group_exit_pct') {
                return (b.group_exit_pct - a.group_exit_pct) || (b.elo - a.elo);
            }
            return 0;
        });

        // 3. Render
        if (filtered.length === 0) {
            leaderboardBody.innerHTML = '<tr><td colspan="11" class="text-center text-secondary">No teams matching search query found.</td></tr>';
            return;
        }

        leaderboardBody.innerHTML = '';
        filtered.forEach((team, index) => {
            const tr = document.createElement('tr');
            tr.className = 'leaderboard-row';
            if (team.team === projectedChampion) {
                tr.classList.add('champion-highlight');
            }
            tr.setAttribute('data-name', team.team);

            // Helper to get color class for progress fill
            const getFillClass = (pct, column) => {
                if (column === 'champion') {
                    return pct > 15 ? 'high-prob' : pct > 5 ? 'medium-prob' : 'low-prob';
                }
                return pct > 40 ? 'high-prob' : pct > 15 ? 'medium-prob' : 'low-prob';
            };

            // HTML cell helper for probabilities
            const makeProbCell = (pct, isChamp = false) => {
                const rounded = Math.round(pct);
                const fillClass = getFillClass(pct, isChamp ? 'champion' : 'other');
                return `
                    <td class="col-prob ${isChamp ? 'champion-col' : ''}">
                        <div class="leaderboard-prob-cell">
                            <span class="prob-val-text">${pct.toFixed(1)}%</span>
                            <div class="prob-bar-track">
                                <div class="prob-bar-fill ${fillClass}" style="width: ${rounded}%"></div>
                            </div>
                        </div>
                    </td>
                `;
            };

            tr.innerHTML = `
                <td class="col-rank">${index + 1}</td>
                <td class="col-team-leader">
                    <div class="team-identity-leader">
                        <img src="${getFlagUrl(team.team)}" class="leader-team-flag" alt="">
                        <span class="leader-team-name">${team.team}</span>
                    </div>
                </td>
                <td class="col-elo-leader">ELO ${team.elo}</td>
                <td class="col-group-leader">Group ${team.group_name || '-'}</td>
                ${makeProbCell(team.group_exit_pct)}
                ${makeProbCell(team.r32_exit_pct)}
                ${makeProbCell(team.r16_exit_pct)}
                ${makeProbCell(team.qf_exit_pct)}
                ${makeProbCell(team.sf_exit_pct)}
                ${makeProbCell(team.runner_up_pct)}
                ${makeProbCell(team.champion_pct, true)}
            `;

            // Row click event navigation
            tr.addEventListener('click', () => {
                window.location.href = `/team/${encodeURIComponent(team.team)}`;
            });

            leaderboardBody.appendChild(tr);
        });
    }

    // Bind controls to leaderboard rendering
    if (teamSearch) {
        teamSearch.addEventListener('input', renderLeaderboard);
    }
    if (leaderboardSort) {
        leaderboardSort.addEventListener('change', renderLeaderboard);
    }

    function showToast(message) {
        toast.innerText = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
