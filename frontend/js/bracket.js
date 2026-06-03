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
        return 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"><circle cx="12" cy="12" r="10" fill="%23666"/></svg>';
    }

    // DOM Elements
    const toggleWeightsBtn = document.getElementById('toggle-weights-btn');
    const closePanelBtn = document.getElementById('close-panel-btn');
    const weightsPanel = document.getElementById('weights-panel');
    const applyWeightsBtn = document.getElementById('apply-weights-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const toast = document.getElementById('toast');
    const themeSelect = document.getElementById('theme-select');
    
    const championBannerContainer = document.getElementById('champion-banner-container');
    const round32List = document.getElementById('round-32-list');
    const round16List = document.getElementById('round-16-list');
    const quarterFinalsList = document.getElementById('quarter-finals-list');
    const semiFinalsList = document.getElementById('semi-finals-list');
    const finalsList = document.getElementById('finals-list');

    // Sliders
    const sliders = {
        elo: document.getElementById('weight-elo'),
        odds: document.getElementById('weight-odds'),
        form: document.getElementById('weight-form'),
        narrative: document.getElementById('weight-narrative')
    };
    
    const sliderVals = {
        elo: document.getElementById('val-elo'),
        odds: document.getElementById('val-odds'),
        form: document.getElementById('val-form'),
        narrative: document.getElementById('val-narrative')
    };

    // Initialize Page Themes
    const savedTheme = localStorage.getItem('matchwatch-theme') || 'neon';
    document.body.className = `theme-${savedTheme}`;
    themeSelect.value = savedTheme;

    // Theme Switcher Event Listener
    themeSelect.addEventListener('change', () => {
        document.body.className = `theme-${themeSelect.value}`;
        localStorage.setItem('matchwatch-theme', themeSelect.value);
        showToast(`Theme switched to ${themeSelect.options[themeSelect.selectedIndex].text}!`);
    });

    // Resolve details and trigger fetch
    fetchBracketDetails();
    fetchWeights();

    // Weight Panel Event Listeners
    toggleWeightsBtn.addEventListener('click', () => {
        weightsPanel.classList.toggle('open');
    });

    closePanelBtn.addEventListener('click', () => {
        weightsPanel.classList.remove('open');
    });

    document.addEventListener('click', (e) => {
        if (!weightsPanel.contains(e.target) && e.target !== toggleWeightsBtn && !toggleWeightsBtn.contains(e.target)) {
            weightsPanel.classList.remove('open');
        }
    });

    Object.keys(sliders).forEach(key => {
        sliders[key].addEventListener('input', () => {
            sliderVals[key].innerText = `${sliders[key].value}%`;
        });
    });

    applyWeightsBtn.addEventListener('click', async () => {
        const body = {
            elo: parseFloat(sliders.elo.value) / 100.0,
            odds: parseFloat(sliders.odds.value) / 100.0,
            form: parseFloat(sliders.form.value) / 100.0,
            narrative: parseFloat(sliders.narrative.value) / 100.0
        };

        try {
            applyWeightsBtn.disabled = true;
            applyWeightsBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...';
            
            const res = await fetch('/api/weights', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            
            updateSlidersUI(data.weights);
            showToast("Weights recalculated & Bracket updated!");
            weightsPanel.classList.remove('open');
            await fetchBracketDetails();
        } catch (err) {
            console.error(err);
            alert("Error recalculating weights.");
        } finally {
            applyWeightsBtn.disabled = false;
            applyWeightsBtn.innerText = 'Recalculate Scores';
        }
    });

    refreshBtn.addEventListener('click', async () => {
        if (!confirm("Are you sure you want to refresh the schedule database? This will reset all mock games and scores.")) return;
        try {
            refreshBtn.classList.add('fa-spin');
            const res = await fetch('/api/refresh', { method: 'POST' });
            if (res.ok) {
                showToast("Database refreshed successfully!");
                await fetchBracketDetails();
            }
        } catch (err) {
            console.error(err);
        } finally {
            refreshBtn.classList.remove('fa-spin');
        }
    });

    async function fetchWeights() {
        try {
            const res = await fetch('/api/weights');
            const weights = await res.json();
            updateSlidersUI(weights);
        } catch (err) {
            console.error("Failed to fetch weights", err);
        }
    }

    function updateSlidersUI(weights) {
        Object.keys(weights).forEach(key => {
            const valPercent = Math.round(weights[key] * 100);
            if (sliders[key]) sliders[key].value = valPercent;
            if (sliderVals[key]) sliderVals[key].innerText = `${valPercent}%`;
        });
    }

    // Fetch Bracket Data
    async function fetchBracketDetails() {
        showLoadingSpinners();
        try {
            const res = await fetch('/api/bracket');
            const data = await res.json();
            
            renderChampion(data.final);
            renderRound(round32List, data.r32);
            renderRound(round16List, data.r16);
            renderRound(quarterFinalsList, data.qf);
            renderRound(semiFinalsList, data.sf);
            renderFinals(data.third, data.final);
        } catch (err) {
            console.error("Failed to load bracket data", err);
            round32List.innerHTML = '<p class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading bracket.</p>';
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
            window.location.href = `/country/${encodeURIComponent(champName)}`;
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

    function createMatchupCard(match, isFinal = false) {
        const card = document.createElement('div');
        card.className = 'bracket-matchup-card glass';
        if (isFinal) {
            card.classList.add('final-match-highlight');
        }
        
        const isWinner1 = match.winner === match.team1.name;
        const isWinner2 = match.winner === match.team2.name;
        
        card.innerHTML = `
            <!-- Team 1 -->
            <div class="bracket-team-row clickable-team-bracket ${isWinner1 ? 'winner' : 'loser'}" data-name="${match.team1.name}">
                <div class="team-identity-bracket">
                    <img src="${getFlagUrl(match.team1.name)}" class="bracket-team-flag" alt="">
                    <span class="bracket-team-name">${match.team1.name}</span>
                    ${match.team1.group_name ? `<span class="bracket-team-group">(Gr. ${match.team1.group_name})</span>` : ''}
                </div>
                <div class="team-stat-bracket">
                    <span class="bracket-elo">ELO ${match.team1.elo}</span>
                    ${isWinner1 ? '<i class="fa-solid fa-circle-check check-winner"></i>' : ''}
                </div>
            </div>
            
            <div class="bracket-vs-line">vs</div>
            
            <!-- Team 2 -->
            <div class="bracket-team-row clickable-team-bracket ${isWinner2 ? 'winner' : 'loser'}" data-name="${match.team2.name}">
                <div class="team-identity-bracket">
                    <img src="${getFlagUrl(match.team2.name)}" class="bracket-team-flag" alt="">
                    <span class="bracket-team-name">${match.team2.name}</span>
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
                window.location.href = `/country/${encodeURIComponent(teamName)}`;
            });
        });
        
        return card;
    }

    function showToast(message) {
        toast.innerText = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
