document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const calendarContainer = document.getElementById('calendar-container');
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
    let highWatchabilityOnly = false;

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

    const filterBtn = document.getElementById('toggle-watchability-filter');
    if (filterBtn) {
        filterBtn.addEventListener('click', () => {
            highWatchabilityOnly = !highWatchabilityOnly;
            filterBtn.classList.toggle('active', highWatchabilityOnly);
            filterBtn.innerHTML = highWatchabilityOnly
                ? '<i class="fa-solid fa-fire text-warning"></i> Showing Recommended+ (≥65%)'
                : '<i class="fa-solid fa-filter"></i> Show Recommended+ Only (≥65%)';
            renderCalendar();
        });
    }

    // Event Listeners
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

    // Calendar Navigation Listeners
    if (prevMonthBtn) {
        prevMonthBtn.addEventListener('click', () => {
            currentMonth--;
            if (currentMonth < 0) {
                currentMonth = 11;
                currentYear--;
            }
            renderCalendar();
        });
    }

    if (nextMonthBtn) {
        nextMonthBtn.addEventListener('click', () => {
            currentMonth++;
            if (currentMonth > 11) {
                currentMonth = 0;
                currentYear++;
            }
            renderCalendar();
        });
    }

    if (todayBtn) {
        todayBtn.addEventListener('click', () => {
            initCurrentMonthYear();
            renderCalendar();
        });
    }

    // Resolve timezone and trigger fetch
    resolveAndTimezoneFetch();

    async function resolveAndTimezoneFetch() {
        resolvedTimezone = await resolveTimezone(selectedTimezone);
        await fetchCalendarFixtures();
    }

    async function fetchCalendarFixtures() {
        calendarContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading scheduled matches...</div>';
        
        try {
            const tournamentId = localStorage.getItem('findfootball-tournament-id') || '';
            const res = await fetch(`/api/fixtures/calendar?tz=${encodeURIComponent(resolvedTimezone)}${tournamentId ? `&tournament_id=${tournamentId}` : ''}`);
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
        
        // Dynamic alignment: default calendar to the first match's month/year if no matches in current month
        let hasMatchInCurrentView = cachedMatches.some(m => {
            const d = new Date(m.date);
            return d.getFullYear() === currentYear && d.getMonth() === currentMonth;
        });
        
        if (!hasMatchInCurrentView && cachedMatches.length > 0) {
            const firstMatchDate = new Date(cachedMatches[0].date);
            currentYear = firstMatchDate.getFullYear();
            currentMonth = firstMatchDate.getMonth();
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
            const dayMatches = (matchesByDateKey[dateKey] || []).filter(match => !highWatchabilityOnly || match.watchability_score >= 65.0);
            
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
                        <img src="${getFlagUrl(match.home_team)}" class="compact-flag" alt="${match.home_team.name}">
                        ${statusHtml}
                        <img src="${getFlagUrl(match.away_team)}" class="compact-flag" alt="${match.away_team.name}">
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
});
