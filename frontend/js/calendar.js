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
    const calendarContainer = document.getElementById('calendar-container');
    const refreshBtn = document.getElementById('refresh-btn');
    const toast = document.getElementById('toast');
    const timezoneSelect = document.getElementById('timezone-select');
    
    // Navigation Buttons and Label
    const prevMonthBtn = document.getElementById('prev-month-btn');
    const nextMonthBtn = document.getElementById('next-month-btn');
    const todayBtn = document.getElementById('today-btn');
    const currentMonthYearLabel = document.getElementById('current-month-year');

    // Modal Elements
    const matchModal = document.getElementById('match-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalContainer = document.getElementById('modal-details-container');

    // Local State
    let selectedTimezone = 'local';
    let resolvedTimezone = 'UTC';
    let cachedMatches = [];
    let currentYear = 2026;
    let currentMonth = 5; // June (0-indexed)

    // Initialize Page
    selectedTimezone = localStorage.getItem('matchwatch-timezone') || 'local';
    timezoneSelect.value = selectedTimezone;

    // Event Listeners
    timezoneSelect.addEventListener('change', () => {
        selectedTimezone = timezoneSelect.value;
        localStorage.setItem('matchwatch-timezone', selectedTimezone);
        resolveAndTimezoneFetch();
        showToast(`Timezone set to ${timezoneSelect.options[timezoneSelect.selectedIndex].text}!`);
    });

    refreshBtn.addEventListener('click', async () => {
        if (!confirm("Are you sure you want to refresh the schedule database? This will reset all mock games and scores.")) return;
        
        try {
            refreshBtn.classList.add('fa-spin');
            const res = await fetch('/api/refresh', { method: 'POST' });
            if (res.ok) {
                showToast("Database refreshed successfully!");
                await fetchCalendarFixtures();
            }
        } catch (err) {
            console.error(err);
        } finally {
            refreshBtn.classList.remove('fa-spin');
        }
    });

    modalClose.addEventListener('click', () => {
        matchModal.classList.remove('open');
    });

    matchModal.addEventListener('click', (e) => {
        if (e.target === matchModal) {
            matchModal.classList.remove('open');
        }
    });

    // Calendar Navigation Listeners
    prevMonthBtn.addEventListener('click', () => {
        currentMonth--;
        if (currentMonth < 0) {
            currentMonth = 11;
            currentYear--;
        }
        renderCalendar();
    });

    nextMonthBtn.addEventListener('click', () => {
        currentMonth++;
        if (currentMonth > 11) {
            currentMonth = 0;
            currentYear++;
        }
        renderCalendar();
    });

    todayBtn.addEventListener('click', () => {
        initCurrentMonthYear();
        renderCalendar();
    });

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    async function resolveAndTimezoneFetch() {
        if (selectedTimezone === 'local') {
            try {
                const geoRes = await fetch('https://ipapi.co/json/');
                if (geoRes.ok) {
                    const geoData = await geoRes.json();
                    if (geoData.timezone) {
                        resolvedTimezone = geoData.timezone;
                        console.log(`Detected timezone: ${resolvedTimezone}`);
                    } else {
                        throw new Error("Timezone field missing");
                    }
                } else {
                    throw new Error("Geo IP response not ok");
                }
            } catch (err) {
                resolvedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
                console.log(`Fallback timezone: ${resolvedTimezone}`);
            }
        } else {
            resolvedTimezone = selectedTimezone;
        }
        await fetchCalendarFixtures();
    }

    async function fetchCalendarFixtures() {
        calendarContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading scheduled matches...</div>';
        
        try {
            const res = await fetch(`/api/fixtures/calendar?tz=${encodeURIComponent(resolvedTimezone)}`);
            if (!res.ok) throw new Error("Failed to fetch calendar fixtures");
            cachedMatches = await res.json();
            
            // Set initial month/year based on current system date or tournament start
            initCurrentMonthYear();
            
            renderCalendar();
        } catch (err) {
            console.error("Failed to load calendar fixtures", err);
            calendarContainer.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error loading calendar.</div>';
        }
    }

    function initCurrentMonthYear() {
        const now = new Date();
        try {
            const formatter = new Intl.DateTimeFormat('en-US', {
                timeZone: resolvedTimezone,
                year: 'numeric',
                month: 'numeric'
            });
            const parts = formatter.formatToParts(now);
            const partMap = {};
            parts.forEach(p => partMap[p.type] = p.value);
            currentYear = parseInt(partMap.year);
            currentMonth = parseInt(partMap.month) - 1; // 0-indexed
        } catch (e) {
            currentYear = now.getFullYear();
            currentMonth = now.getMonth();
        }
        
        // World Cup 2026 starts in June 2026. If the local system time is outside June/July 2026,
        // force default to June 2026 so the user sees matches immediately.
        if (currentYear !== 2026) {
            currentYear = 2026;
            currentMonth = 5; // June
        }
    }

    function getDaysInMonthGrid(year, month) {
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        
        const startDayOfWeek = firstDay.getDay(); 
        const totalDays = lastDay.getDate();
        
        const prevMonthLastDay = new Date(year, month, 0).getDate();
        const gridDays = [];
        
        // Previous month days to pad
        for (let i = startDayOfWeek - 1; i >= 0; i--) {
            gridDays.push({
                dayNumber: prevMonthLastDay - i,
                month: month === 0 ? 11 : month - 1,
                year: month === 0 ? year - 1 : year,
                isCurrentMonth: false
            });
        }
        
        // Current month days
        for (let i = 1; i <= totalDays; i++) {
            gridDays.push({
                dayNumber: i,
                month: month,
                year: year,
                isCurrentMonth: true
            });
        }
        
        // Next month days to pad
        const remaining = 7 - (gridDays.length % 7);
        if (remaining < 7) {
            for (let i = 1; i <= remaining; i++) {
                gridDays.push({
                    dayNumber: i,
                    month: month === 11 ? 0 : month + 1,
                    year: month === 11 ? year + 1 : year,
                    isCurrentMonth: false
                });
            }
        }
        
        // Ensure 6 complete weeks (42 cells) to keep height stable
        if (gridDays.length < 42) {
            const currentLength = gridDays.length;
            const nextMonthStart = gridDays[currentLength - 1].dayNumber + 1;
            const nextM = gridDays[currentLength - 1].month;
            const nextY = gridDays[currentLength - 1].year;
            for (let i = 0; i < 42 - currentLength; i++) {
                gridDays.push({
                    dayNumber: nextMonthStart + i,
                    month: nextM,
                    year: nextY,
                    isCurrentMonth: false
                });
            }
        }
        
        return gridDays;
    }

    function renderCalendar() {
        calendarContainer.innerHTML = '';
        
        const monthNames = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ];
        currentMonthYearLabel.textContent = `${monthNames[currentMonth]} ${currentYear}`;
        
        // Group cachedMatches by YYYY-MM-DD key in target timezone
        const matchesByDateKey = {};
        cachedMatches.forEach(match => {
            try {
                const dateObj = new Date(match.date);
                const formatter = new Intl.DateTimeFormat('en-US', {
                    timeZone: resolvedTimezone,
                    year: 'numeric',
                    month: 'numeric',
                    day: 'numeric'
                });
                const parts = formatter.formatToParts(dateObj);
                const partMap = {};
                parts.forEach(p => partMap[p.type] = p.value);
                
                const yStr = partMap.year;
                const mStr = String(partMap.month).padStart(2, '0');
                const dStr = String(partMap.day).padStart(2, '0');
                const dateKey = `${yStr}-${mStr}-${dStr}`;
                
                if (!matchesByDateKey[dateKey]) {
                    matchesByDateKey[dateKey] = [];
                }
                matchesByDateKey[dateKey].push(match);
            } catch (err) {
                console.error("Error formatting match date", err);
            }
        });

        // Generate and append cells
        const gridDays = getDaysInMonthGrid(currentYear, currentMonth);
        
        gridDays.forEach(day => {
            const dayBox = document.createElement('div');
            dayBox.className = 'calendar-day-box';
            if (day.isCurrentMonth) {
                dayBox.classList.add('in-month');
            } else {
                dayBox.classList.add('outside-month');
            }
            
            // Highlight today
            const now = new Date();
            let isToday = false;
            try {
                const formatter = new Intl.DateTimeFormat('en-US', {
                    timeZone: resolvedTimezone,
                    year: 'numeric',
                    month: 'numeric',
                    day: 'numeric'
                });
                const parts = formatter.formatToParts(now);
                const partMap = {};
                parts.forEach(p => partMap[p.type] = p.value);
                
                isToday = (parseInt(partMap.year) === day.year &&
                           (parseInt(partMap.month) - 1) === day.month &&
                           parseInt(partMap.day) === day.dayNumber);
            } catch (e) {
                isToday = (now.getFullYear() === day.year &&
                           now.getMonth() === day.month &&
                           now.getDate() === day.dayNumber);
            }
            
            if (isToday) {
                dayBox.classList.add('is-today');
            }
            
            // Day Number
            const dayNumSpan = document.createElement('span');
            dayNumSpan.className = 'calendar-day-number';
            dayNumSpan.textContent = day.dayNumber;
            dayBox.appendChild(dayNumSpan);
            
            // Matches List
            const matchesContainer = document.createElement('div');
            matchesContainer.className = 'calendar-day-matches';
            
            const dateKey = `${day.year}-${String(day.month + 1).padStart(2, '0')}-${String(day.dayNumber).padStart(2, '0')}`;
            const dayMatches = matchesByDateKey[dateKey] || [];
            
            dayMatches.forEach(match => {
                const compactMatch = document.createElement('div');
                const ratingClass = getRatingClass(match.watchability_score);
                const ratingText = getRatingText(match.watchability_score);
                
                compactMatch.className = `calendar-compact-match ${ratingClass}`;
                compactMatch.setAttribute('title', `${match.home_team.name} vs ${match.away_team.name} (${match.formatted_time} • Watchability: ${ratingText})`);
                
                let statusHtml = '';
                if (match.status === 'Finished') {
                    statusHtml = `<span class="compact-time-score">${match.score}</span>`;
                } else if (match.status === 'Live') {
                    statusHtml = `<span class="compact-time-score live"><span class="live-dot"></span>${match.score}</span>`;
                } else {
                    statusHtml = `<span class="compact-time-score">${match.formatted_time}</span>`;
                }
                
                compactMatch.innerHTML = `
                    <div class="compact-matchup">
                        <img src="${getFlagUrl(match.home_team.name)}" class="compact-flag" alt="${match.home_team.name}">
                        ${statusHtml}
                        <img src="${getFlagUrl(match.away_team.name)}" class="compact-flag" alt="${match.away_team.name}">
                    </div>
                `;
                
                compactMatch.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openMatchDetails(match.id);
                });
                
                matchesContainer.appendChild(compactMatch);
            });
            
            dayBox.appendChild(matchesContainer);
            calendarContainer.appendChild(dayBox);
        });
    }

    async function openMatchDetails(fixtureId) {
        modalContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading details...</div>';
        matchModal.classList.add('open');

        try {
            const res = await fetch(`/api/fixtures/${fixtureId}?tz=${encodeURIComponent(resolvedTimezone)}`);
            if (!res.ok) throw new Error("Failed to fetch fixture details");
            const match = await res.json();
            
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

            // Bind click events inside modal
            if (match.group_name) {
                modalContainer.querySelector('.stage-tag').addEventListener('click', () => {
                    window.location.href = `/group/${match.group_name}`;
                });
            }

            modalContainer.querySelectorAll('.team-nav-link').forEach(el => {
                el.addEventListener('click', () => {
                    window.location.href = `/country/${encodeURIComponent(el.getAttribute('data-name'))}`;
                });
            });

            // Animate progress bars
            setTimeout(() => {
                const fills = modalContainer.querySelectorAll('.bar-fill');
                fills.forEach(fill => {
                    fill.style.width = fill.getAttribute('data-width');
                });
            }, 100);

        } catch (err) {
            console.error("Error opening match details modal:", err);
            modalContainer.innerHTML = '<div class="loading-spinner text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Failed to load match details.</div>';
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
