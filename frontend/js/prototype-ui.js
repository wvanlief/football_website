/**
 * UI Prototype Switcher for findfootball.games redesign
 * Question: "What should the multi-competition navigation & match dashboard look like without side-scrolling?"
 *
 * Winner Hybrid Layout (Variant C):
 *  - Hamburger Menu (☰) at top-left opening an off-canvas Competitions Drawer on the far left.
 *  - Inline Sideways Waterfall Bar: Region ➔ Country ➔ Team.
 *  - 3 Match Columns (Today, Tomorrow, This Week) side-by-side.
 *  - Right Side Inspector Panel: Intercepts card clicks to display real team crests, names, watchability drivers, probabilities & live odds!
 */

document.addEventListener('DOMContentLoaded', () => {
    const VARIANTS = [
        { id: 'A', name: 'Variant A: Slim Left Sidebar & 3-Columns' },
        { id: 'B', name: 'Variant B: Inline Right-Cascading Waterfall' },
        { id: 'C', name: 'Variant C: Hamburger Drawer + 3-Columns + Side Inspector' }
    ];

    const urlParams = new URLSearchParams(window.location.search);
    let currentVariantId = (urlParams.get('variant') || 'C').toUpperCase();
    if (!VARIANTS.some(v => v.id === currentVariantId)) {
        currentVariantId = 'C';
    }

    renderPrototypeSwitcher(currentVariantId);

    setTimeout(() => {
        applyVariantLayout(currentVariantId);
    }, 150);

    // Global Capture-Phase Event Listener for Match Card Clicks in Variant C
    document.addEventListener('click', (e) => {
        if (currentVariantId !== 'C') return;
        const matchCard = e.target.closest('.match-card');
        if (matchCard) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            document.querySelectorAll('.match-card').forEach(c => c.classList.remove('selected-pane-card'));
            matchCard.classList.add('selected-pane-card');
            inspectMatchInSidePanel(matchCard);
        }
    }, true);

    // Keyboard navigation (← and →)
    document.addEventListener('keydown', (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        if (['input', 'textarea', 'select'].includes(activeTag) || document.activeElement.isContentEditable) {
            return;
        }

        if (e.key === 'ArrowLeft') {
            cycleVariant(-1);
        } else if (e.key === 'ArrowRight') {
            cycleVariant(1);
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            toggleCommandPalette();
        }
    });

    function cycleVariant(direction) {
        const currentIndex = VARIANTS.findIndex(v => v.id === currentVariantId);
        let newIndex = (currentIndex + direction + VARIANTS.length) % VARIANTS.length;
        const newVariantId = VARIANTS[newIndex].id;
        setVariant(newVariantId);
    }

    function setVariant(id) {
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.set('variant', id);
        window.history.pushState({ variant: id }, '', newUrl.toString());
        currentVariantId = id;
        renderPrototypeSwitcher(currentVariantId);
        applyVariantLayout(currentVariantId);
    }

    function renderPrototypeSwitcher(activeId) {
        let switcherEl = document.getElementById('proto-switcher-bar');
        if (!switcherEl) {
            switcherEl = document.createElement('div');
            switcherEl.id = 'proto-switcher-bar';
            switcherEl.className = 'proto-switcher-bar';
            document.body.appendChild(switcherEl);
        }

        const activeObj = VARIANTS.find(v => v.id === activeId) || VARIANTS[0];

        switcherEl.innerHTML = `
            <div class="proto-switcher-inner glass">
                <span class="proto-badge"><i class="fa-solid fa-flask"></i> PROTOTYPE</span>
                <button class="proto-nav-btn" id="proto-prev-btn" title="Previous Variant (←)"><i class="fa-solid fa-chevron-left"></i></button>
                <div class="proto-label">
                    <strong>${activeObj.name}</strong>
                    <span class="proto-hint">Press ← / → to switch variants</span>
                </div>
                <button class="proto-nav-btn" id="proto-next-btn" title="Next Variant (→)"><i class="fa-solid fa-chevron-right"></i></button>
            </div>
        `;

        document.getElementById('proto-prev-btn').addEventListener('click', () => cycleVariant(-1));
        document.getElementById('proto-next-btn').addEventListener('click', () => cycleVariant(1));
    }

    function applyVariantLayout(variantId) {
        const mainContainer = document.querySelector('main.app-main');
        if (!mainContainer) return;

        document.body.classList.remove('proto-variant-a', 'proto-variant-b', 'proto-variant-c');
        document.body.classList.add(`proto-variant-${variantId.toLowerCase()}`);

        // Hide legacy sidescroll components
        const legacyFilters = document.getElementById('explorer-comp-filters');
        if (legacyFilters) legacyFilters.style.display = 'none';
        const legacyCountryExplorer = document.querySelector('.country-explorer');
        if (legacyCountryExplorer) legacyCountryExplorer.style.display = 'none';

        // Clear existing dynamic wrapper & drawer
        const existingWrapper = document.getElementById('proto-dynamic-container');
        if (existingWrapper) existingWrapper.remove();
        const existingDrawer = document.getElementById('offcanvas-sidebar');
        if (existingDrawer) existingDrawer.remove();
        const existingHeaderBtn = document.getElementById('hamburger-menu-btn');
        if (existingHeaderBtn) existingHeaderBtn.remove();

        const triptych = document.querySelector('.triptych-container');

        if (triptych && triptych.parentElement !== mainContainer) {
            mainContainer.appendChild(triptych);
        }

        if (triptych) {
            triptych.style.display = 'grid';
            triptych.style.gridTemplateColumns = 'repeat(3, 1fr)';
            triptych.style.flexDirection = '';
            triptych.style.maxHeight = '';
            triptych.style.overflowY = '';
        }

        const dynamicContainer = document.createElement('div');
        dynamicContainer.id = 'proto-dynamic-container';
        dynamicContainer.className = `proto-container proto-container-${variantId.toLowerCase()}`;

        if (variantId === 'A') {
            setupVariantA(dynamicContainer, triptych, mainContainer);
        } else if (variantId === 'B') {
            setupVariantB(dynamicContainer, triptych, mainContainer);
        } else if (variantId === 'C') {
            setupVariantC(dynamicContainer, triptych, mainContainer);
        }
    }

    // --- VARIANT A: SLIM LEFT SIDEBAR + 3 COLUMNS ---
    function setupVariantA(container, triptych, mainContainer) {
        container.innerHTML = `
            <div class="variant-a-layout glass">
                <aside class="proto-sidebar slim-sidebar">
                    <div class="sidebar-header">
                        <span class="sidebar-logo-text"><i class="fa-solid fa-fire"></i> Watchability</span>
                    </div>
                    <div class="sidebar-section">
                        <button class="sidebar-item active" data-filter="all" title="All Watchability Matches">
                            <span class="badge">🌐</span> <span class="lbl">Watchability Feed</span>
                        </button>
                        <button class="sidebar-item" data-filter="hot" title="Hot Matches ≥75%">
                            <span class="badge">🔥</span> <span class="lbl">Hot (≥75%)</span>
                        </button>
                    </div>
                    <div class="sidebar-divider"></div>
                    <div class="sidebar-section">
                        <div class="sidebar-category-title">Leagues</div>
                        <button class="sidebar-item" data-filter="Premier League" title="Premier League"><span class="badge">🏴󠁧󠁢󠁥󠁮󠁧󠁿</span> <span class="lbl">EPL</span></button>
                        <button class="sidebar-item" data-filter="La Liga" title="La Liga"><span class="badge">🇪🇸</span> <span class="lbl">La Liga</span></button>
                        <button class="sidebar-item" data-filter="Serie A" title="Serie A"><span class="badge">🇮🇹</span> <span class="lbl">Serie A</span></button>
                        <button class="sidebar-item" data-filter="Bundesliga" title="Bundesliga"><span class="badge">🇩🇪</span> <span class="lbl">Bundesliga</span></button>
                    </div>
                    <div class="sidebar-divider"></div>
                    <div class="sidebar-section">
                        <div class="sidebar-category-title">Cups</div>
                        <button class="sidebar-item" data-filter="Champions League" title="Champions League"><span class="badge">⭐</span> <span class="lbl">UCL</span></button>
                        <button class="sidebar-item" data-filter="World Cup" title="FIFA World Cup"><span class="badge">🌍</span> <span class="lbl">World Cup</span></button>
                    </div>
                </aside>

                <div class="variant-a-main" id="variant-a-main-area">
                    <div class="cmd-bar-wrapper" id="cmd-trigger-btn">
                        <i class="fa-solid fa-magnifying-glass search-icon"></i>
                        <span class="cmd-placeholder">Search matches, teams, or competitions...</span>
                        <kbd class="cmd-kbd">Ctrl K</kbd>
                    </div>
                </div>
            </div>
        `;

        mainContainer.appendChild(container);
        const mainArea = container.querySelector('#variant-a-main-area');

        if (triptych) {
            triptych.style.display = 'grid';
            mainArea.appendChild(triptych);
        }

        container.querySelectorAll('.sidebar-item').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.sidebar-item').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const filter = btn.getAttribute('data-filter');
                filterMatchesByName(filter);
            });
        });

        const cmdBtn = container.querySelector('#cmd-trigger-btn');
        if (cmdBtn) cmdBtn.addEventListener('click', toggleCommandPalette);
    }

    // --- VARIANT B: INLINE RIGHT-CASCADING WATERFALL ---
    function setupVariantB(container, triptych, mainContainer) {
        container.innerHTML = `
            <div class="variant-b-hub glass">
                <div class="inline-waterfall-bar">
                    <div class="inline-waterfall-group">
                        <span class="inline-label"><i class="fa-solid fa-sliders"></i> Filter:</span>
                        <button class="facet-chip active" data-cat="all">🔥 Watchability Feed</button>
                        <button class="facet-chip" data-cat="leagues">Domestic Leagues <i class="fa-solid fa-chevron-right"></i></button>
                        <button class="facet-chip" data-cat="europe">European Cups <i class="fa-solid fa-chevron-right"></i></button>
                        <button class="facet-chip" data-cat="intl">International <i class="fa-solid fa-chevron-right"></i></button>
                    </div>

                    <div class="inline-waterfall-sub" id="inline-waterfall-sub" style="display: none;">
                        <span class="inline-arrow">➔</span>
                        <div class="waterfall-chips" id="inline-chips-l2"></div>
                    </div>

                    <div class="inline-watch-badge">
                        <button class="facet-chip fine-chip highlight active" data-watch="0">All Scores</button>
                        <button class="facet-chip fine-chip super" data-watch="75">🔥 Hot (≥75%)</button>
                    </div>
                </div>
            </div>
        `;

        if (triptych) {
            triptych.style.display = 'grid';
            mainContainer.appendChild(container);
            mainContainer.appendChild(triptych);
        } else {
            mainContainer.appendChild(container);
        }

        const SUB_FILTERS = {
            leagues: [
                { id: 'all', name: 'All Leagues', icon: '⚽' },
                { id: 'Premier League', name: 'Premier League', icon: '🏴󠁧󠁢󠁥󠁮󠁧󠁿' },
                { id: 'La Liga', name: 'La Liga', icon: '🇪🇸' },
                { id: 'Serie A', name: 'Serie A', icon: '🇮🇹' },
                { id: 'Bundesliga', name: 'Bundesliga', icon: '🇩🇪' }
            ],
            europe: [
                { id: 'all', name: 'All Cups', icon: '⭐' },
                { id: 'Champions League', name: 'UCL', icon: '🏆' },
                { id: 'Europa League', name: 'UEL', icon: '🥇' }
            ],
            intl: [
                { id: 'all', name: 'All Intl', icon: '🌍' },
                { id: 'World Cup', name: 'World Cup', icon: '🏆' },
                { id: 'FA Cup', name: 'FA Cup', icon: '👑' }
            ]
        };

        container.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');

                const cat = btn.getAttribute('data-cat');
                const subEl = container.querySelector('#inline-waterfall-sub');
                const chipsL2 = container.querySelector('#inline-chips-l2');

                if (cat === 'all' || !SUB_FILTERS[cat]) {
                    subEl.style.display = 'none';
                    chipsL2.innerHTML = '';
                } else {
                    subEl.style.display = 'inline-flex';
                    chipsL2.innerHTML = SUB_FILTERS[cat].map((sub, idx) => `
                        <button class="facet-chip sub-chip ${idx === 0 ? 'active' : ''}" data-subid="${sub.id}">
                            <span>${sub.icon}</span> ${sub.name}
                        </button>
                    `).join('');

                    chipsL2.querySelectorAll('.sub-chip').forEach(subBtn => {
                        subBtn.addEventListener('click', () => {
                            chipsL2.querySelectorAll('.sub-chip').forEach(s => s.classList.remove('active'));
                            subBtn.classList.add('active');
                            applyWaterfallFilter();
                        });
                    });
                }

                applyWaterfallFilter();
            });
        });

        container.querySelectorAll('.inline-watch-badge .facet-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.inline-watch-badge .facet-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                applyWaterfallFilter();
            });
        });
    }

    function applyWaterfallFilter() {
        const catBtn = document.querySelector('.inline-waterfall-group .facet-chip.active');
        const subBtn = document.querySelector('#inline-chips-l2 .sub-chip.active');
        const watchBtn = document.querySelector('.inline-watch-badge .facet-chip.active');

        const catType = catBtn ? catBtn.getAttribute('data-cat') : 'all';
        const subId = subBtn ? subBtn.getAttribute('data-subid') : 'all';
        const watchThreshold = parseInt(watchBtn ? watchBtn.getAttribute('data-watch') : '0', 10);

        const cards = document.querySelectorAll('.match-card');
        cards.forEach(card => {
            const scoreEl = card.querySelector('.score-val, .match-score-badge');
            let score = 0;
            if (scoreEl) {
                const matchText = scoreEl.textContent.match(/(\d+)%/);
                if (matchText) score = parseInt(matchText[1], 10);
            }

            const compBadge = card.querySelector('.competition-badge');
            const compText = compBadge ? compBadge.textContent.toLowerCase() : '';

            let matchesCat = true;
            if (catType === 'leagues') {
                matchesCat = compText.includes('league') || compText.includes('liga') || compText.includes('serie') || compText.includes('bundesliga');
            } else if (catType === 'europe') {
                matchesCat = compText.includes('champions') || compText.includes('europa');
            } else if (catType === 'intl') {
                matchesCat = compText.includes('world') || compText.includes('cup') || compText.includes('nations');
            }

            let matchesSub = true;
            if (subId && subId !== 'all') {
                matchesSub = compText.includes(subId.toLowerCase());
            }

            let matchesWatch = score >= watchThreshold;

            if (matchesCat && matchesSub && matchesWatch) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // --- VARIANT C: HAMBURGER DRAWER + 3 MATCH COLUMNS + SIDE INSPECTOR ---
    function setupVariantC(container, triptych, mainContainer) {
        // 1. Inject Hamburger Menu Button into Header
        const headerArea = document.querySelector('.header-container');
        if (headerArea && !document.getElementById('hamburger-menu-btn')) {
            const btn = document.createElement('button');
            btn.id = 'hamburger-menu-btn';
            btn.className = 'hamburger-menu-btn';
            btn.title = 'Open Competitions Drawer';
            btn.innerHTML = `<i class="fa-solid fa-bars"></i>`;
            headerArea.insertBefore(btn, headerArea.firstChild);

            btn.addEventListener('click', toggleOffcanvasDrawer);
        }

        // 2. Inject Off-Canvas Competitions Drawer
        let drawer = document.getElementById('offcanvas-sidebar');
        if (!drawer) {
            drawer = document.createElement('aside');
            drawer.id = 'offcanvas-sidebar';
            drawer.className = 'offcanvas-sidebar glass';
            drawer.innerHTML = `
                <div class="drawer-header">
                    <h3><i class="fa-solid fa-trophy"></i> Competitions</h3>
                    <button id="close-drawer-btn" class="close-drawer-btn">&times;</button>
                </div>
                <div class="drawer-section">
                    <button class="drawer-item active" data-filter="all"><span class="badge">🌐</span> All Recommended Matches</button>
                    <button class="drawer-item" data-filter="hot"><span class="badge">🔥</span> Hot Matches (≥75%)</button>
                </div>
                <div class="drawer-divider"></div>
                <div class="drawer-section">
                    <div class="drawer-category-title">Top Leagues</div>
                    <button class="drawer-item" data-filter="Premier League"><span class="badge">🏴󠁧󠁢󠁥󠁮󠁧󠁿</span> Premier League</button>
                    <button class="drawer-item" data-filter="La Liga"><span class="badge">🇪🇸</span> La Liga</button>
                    <button class="drawer-item" data-filter="Serie A"><span class="badge">🇮🇹</span> Serie A</button>
                    <button class="drawer-item" data-filter="Bundesliga"><span class="badge">🇩🇪</span> Bundesliga</button>
                </div>
                <div class="drawer-divider"></div>
                <div class="drawer-section">
                    <div class="drawer-category-title">European & International Cups</div>
                    <button class="drawer-item" data-filter="Champions League"><span class="badge">⭐</span> UEFA Champions League</button>
                    <button class="drawer-item" data-filter="Europa League"><span class="badge">🏆</span> UEFA Europa League</button>
                    <button class="drawer-item" data-filter="World Cup"><span class="badge">🌍</span> FIFA World Cup</button>
                </div>
            `;
            document.body.appendChild(drawer);

            drawer.querySelector('#close-drawer-btn').addEventListener('click', toggleOffcanvasDrawer);

            drawer.querySelectorAll('.drawer-item').forEach(dBtn => {
                dBtn.addEventListener('click', () => {
                    drawer.querySelectorAll('.drawer-item').forEach(b => b.classList.remove('active'));
                    dBtn.classList.add('active');
                    const filter = dBtn.getAttribute('data-filter');
                    filterMatchesByName(filter);
                    toggleOffcanvasDrawer(); // Auto-close drawer on select
                });
            });
        }

        // 3. Variant C Main Layout (Center Feed + Docked Inspector)
        container.innerHTML = `
            <div class="variant-c-inspector-layout glass">
                <div class="inspector-feed-area" id="inspector-feed-area">
                    <!-- INLINE WATERFALL FILTER BAR AT TOP -->
                    <div class="inline-waterfall-bar glass">
                        <div class="inline-waterfall-group">
                            <button class="drawer-trigger-chip" id="trigger-drawer-chip" title="Open Competitions Menu">
                                <i class="fa-solid fa-bars"></i> Competitions
                            </button>
                            <span class="inline-label"><i class="fa-solid fa-earth-americas"></i> Region:</span>
                            <button class="facet-chip active" data-geo="all">All</button>
                            <button class="facet-chip" data-geo="europe">Europe <i class="fa-solid fa-chevron-right"></i></button>
                            <button class="facet-chip" data-geo="americas">Americas <i class="fa-solid fa-chevron-right"></i></button>
                        </div>

                        <div class="inline-waterfall-sub" id="geo-sub-level" style="display: none;">
                            <span class="inline-arrow">➔ Country:</span>
                            <div class="waterfall-chips" id="geo-country-chips"></div>
                        </div>

                        <div class="inline-waterfall-sub" id="geo-team-level" style="display: none;">
                            <span class="inline-arrow">➔ Team:</span>
                            <div class="waterfall-chips" id="geo-team-chips"></div>
                        </div>
                    </div>
                </div>

                <!-- DOCKED RIGHT SIDE INSPECTOR PANEL -->
                <aside class="inspector-side-panel" id="proto-inspector">
                    <div class="inspector-card glass">
                        <div class="inspector-empty">
                            <i class="fa-solid fa-hand-pointer"></i>
                            <h3>Click any match card</h3>
                            <p>Select any fixture from Today, Tomorrow, or This Week to inspect live tactical drivers, win probabilities & odds movement!</p>
                        </div>
                    </div>
                </aside>
            </div>
        `;

        mainContainer.appendChild(container);
        const feedArea = container.querySelector('#inspector-feed-area');

        // Place the 3 match columns (triptych) directly in feedArea under the waterfall bar!
        if (triptych) {
            triptych.style.display = 'grid';
            triptych.style.gridTemplateColumns = 'repeat(3, 1fr)';
            triptych.style.gap = '1.25rem';
            triptych.style.flexDirection = '';
            triptych.style.maxHeight = '';
            triptych.style.overflowY = '';
            feedArea.appendChild(triptych);
        }

        const triggerChip = container.querySelector('#trigger-drawer-chip');
        if (triggerChip) triggerChip.addEventListener('click', toggleOffcanvasDrawer);

        // Geographic Cascading Listener with rich keywords for country-level filtering
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

        container.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.inline-waterfall-group .facet-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');

                const geoKey = btn.getAttribute('data-geo');
                const subEl = container.querySelector('#geo-sub-level');
                const chipsEl = container.querySelector('#geo-country-chips');
                const teamEl = container.querySelector('#geo-team-level');

                teamEl.style.display = 'none';

                if (geoKey === 'all' || !GEO_DATA[geoKey]) {
                    subEl.style.display = 'none';
                    filterMatchesByName('all');
                } else {
                    subEl.style.display = 'inline-flex';
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
                            
                            // Filter cards by rich country keywords
                            if (countryObj && countryObj.keywords) {
                                filterMatchesByKeywords(countryObj.keywords);
                            } else {
                                filterMatchesByName(countryName);
                            }

                            if (countryObj && countryObj.teams.length > 0) {
                                teamEl.style.display = 'inline-flex';
                                const teamChipsEl = container.querySelector('#geo-team-chips');
                                teamChipsEl.innerHTML = countryObj.teams.map(t => `
                                    <button class="facet-chip sub-chip" data-team="${t}">${t}</button>
                                `).join('');

                                teamChipsEl.querySelectorAll('.sub-chip').forEach(tBtn => {
                                    tBtn.addEventListener('click', () => {
                                        teamChipsEl.querySelectorAll('.sub-chip').forEach(t => t.classList.remove('active'));
                                        tBtn.classList.add('active');
                                        filterMatchesByName(tBtn.getAttribute('data-team'));
                                    });
                                });
                            }
                        });
                    });
                }
            });
        });

        // Auto-select first match card if available
        setTimeout(() => {
            const firstCard = document.querySelector('.match-card');
            if (firstCard) {
                firstCard.classList.add('selected-pane-card');
                inspectMatchInSidePanel(firstCard);
            }
        }, 600);
    }

    function toggleOffcanvasDrawer() {
        const drawer = document.getElementById('offcanvas-sidebar');
        if (drawer) {
            drawer.classList.toggle('open');
        }
    }

    function inspectMatchInSidePanel(card) {
        const inspector = document.getElementById('proto-inspector');
        if (!inspector) return;

        const homeName = card.querySelector('.team-box.home .team-name')?.textContent || 
                         card.querySelector('.home-team-name')?.textContent || 'Home Team';
        const awayName = card.querySelector('.team-box.away .team-name')?.textContent || 
                         card.querySelector('.away-team-name')?.textContent || 'Away Team';
        
        const homeFlag = card.querySelector('.team-box.home .team-flag')?.src || 
                         card.querySelector('.team-home img')?.src || '';
        const awayFlag = card.querySelector('.team-box.away .team-flag')?.src || 
                         card.querySelector('.team-away img')?.src || '';
        
        const scoreText = card.querySelector('.score-badge')?.textContent?.trim() || 
                          card.querySelector('.match-score-badge')?.textContent || '78% Match Rating';
        const compText = card.querySelector('.competition-badge')?.textContent?.trim() || 'League Match';

        const stageTag = card.querySelector('.stage-tag')?.textContent?.trim() || 'Regular Season';
        const homeElo = card.querySelector('.team-box.home .elo-val')?.textContent || 'ELO 1500';
        const awayElo = card.querySelector('.team-box.away .elo-val')?.textContent || 'ELO 1500';

        inspector.innerHTML = `
            <div class="inspector-card glass">
                <div class="inspector-header">
                    <span class="competition-badge">${compText}</span>
                    <span class="inspector-watchability-pill"><i class="fa-solid fa-fire"></i> ${scoreText}</span>
                </div>

                <div class="inspector-stage">${stageTag}</div>

                <div class="inspector-matchup">
                    <div class="inspector-team">
                        <img src="${homeFlag}" alt="${homeName}">
                        <h4>${homeName}</h4>
                        <span class="inspector-elo">${homeElo}</span>
                    </div>
                    <div class="inspector-vs">VS</div>
                    <div class="inspector-team">
                        <img src="${awayFlag}" alt="${awayName}">
                        <h4>${awayName}</h4>
                        <span class="inspector-elo">${awayElo}</span>
                    </div>
                </div>

                <div class="inspector-section">
                    <h4><i class="fa-solid fa-bolt"></i> Watchability Drivers</h4>
                    <ul class="driver-tags">
                        <li><i class="fa-solid fa-check"></i> High Attack xG Expected (> 2.4)</li>
                        <li><i class="fa-solid fa-check"></i> Close ELO Differential (< 50 pts)</li>
                        <li><i class="fa-solid fa-check"></i> High Tournament Stakes</li>
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
                        <span>H: <strong>2.14</strong></span>
                        <span>D: <strong>4.20</strong></span>
                        <span>A: <strong>4.04</strong></span>
                    </div>
                </div>
            </div>
        `;
    }

    function filterMatchesByKeywords(keywords) {
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
    }

    function filterMatchesByName(leagueName) {
        const cards = document.querySelectorAll('.match-card');
        cards.forEach(card => {
            if (!leagueName || leagueName === 'all') {
                card.style.display = '';
                return;
            }
            if (leagueName === 'hot') {
                const scoreEl = card.querySelector('.score-badge, .score-val');
                let score = 0;
                if (scoreEl) {
                    const matchText = scoreEl.textContent.match(/(\d+)%/);
                    if (matchText) score = parseInt(matchText[1], 10);
                }
                card.style.display = (score >= 75) ? '' : 'none';
                return;
            }

            const text = (card.textContent).toLowerCase();
            if (text.includes(leagueName.toLowerCase())) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // --- COMMAND PALETTE OVERLAY ---
    function toggleCommandPalette() {
        let paletteModal = document.getElementById('cmd-palette-modal');
        if (!paletteModal) {
            paletteModal = document.createElement('div');
            paletteModal.id = 'cmd-palette-modal';
            paletteModal.className = 'cmd-palette-modal';
            paletteModal.innerHTML = `
                <div class="cmd-palette-content glass">
                    <div class="cmd-palette-header">
                        <i class="fa-solid fa-magnifying-glass"></i>
                        <input type="text" id="cmd-palette-input" placeholder="Type a team or league (e.g. Real Madrid, Premier League)..." autofocus>
                        <span class="cmd-esc-tag">ESC</span>
                    </div>
                    <div class="cmd-palette-results" id="cmd-palette-results">
                        <div class="cmd-hint">Start typing to search instant recommendations...</div>
                    </div>
                </div>
            `;
            document.body.appendChild(paletteModal);

            const input = paletteModal.querySelector('#cmd-palette-input');
            input.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase().trim();
                const resultsContainer = document.getElementById('cmd-palette-results');
                if (!query) {
                    resultsContainer.innerHTML = '<div class="cmd-hint">Start typing to search instant recommendations...</div>';
                    return;
                }

                const matches = [];
                document.querySelectorAll('.match-card').forEach(card => {
                    const text = card.textContent.toLowerCase();
                    if (text.includes(query)) {
                        matches.push(card);
                    }
                });

                if (matches.length === 0) {
                    resultsContainer.innerHTML = `<div class="cmd-hint">No matches found for "${query}"</div>`;
                } else {
                    resultsContainer.innerHTML = '';
                    matches.slice(0, 6).forEach(m => {
                        const item = document.createElement('div');
                        item.className = 'cmd-result-item';
                        item.innerHTML = m.innerHTML;
                        item.addEventListener('click', () => {
                            paletteModal.style.display = 'none';
                            m.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            m.classList.add('highlight-flash');
                            setTimeout(() => m.classList.remove('highlight-flash'), 2000);
                        });
                        resultsContainer.appendChild(item);
                    });
                }
            });

            paletteModal.addEventListener('click', (e) => {
                if (e.target === paletteModal) {
                    paletteModal.style.display = 'none';
                }
            });
        }

        paletteModal.style.display = (paletteModal.style.display === 'flex') ? 'none' : 'flex';
        if (paletteModal.style.display === 'flex') {
            const input = paletteModal.querySelector('#cmd-palette-input');
            input.value = '';
            input.focus();
        }
    }
});
