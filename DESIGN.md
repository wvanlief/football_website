# Design System

<!-- impeccable:design-schema 1 -->

## Visual World: Stadium Pitch & Trophy Gold

A high-contrast, physical stadium aesthetic designed specifically for live matchday excitement:

- **Atmosphere & Pitch Depth**: Deep obsidian ground with organic pitch-turf undertones (`#060807` base, `#0d1611` solid cards, `rgba(14, 24, 18, 0.45)` translucent glass), eliminating any muddy navy-blue haze.
- **Accents & Watchability**: Vibrant, warm Amber Gold (`#fbbf24` / `#f59e0b` / `#d97706`) for the trophy logo, glowing score badges, and interactive controls.
- **High-Readability Typography**: Primary text in crisp silver-white (`#f8fafc`), muted indicators in neutral sand/gray (`#94a3b8`), and razor-sharp monospace (`Geist Mono`) for odds, ELO scores, and timestamps.

## Color Palette Tokens

```css
--bg-main: #060807;
--bg-card: rgba(14, 24, 18, 0.45);
--bg-card-solid: #0d1611;
--bg-panel: #08100b;
--border-color: rgba(255, 255, 255, 0.08);
--border-hover: rgba(251, 191, 36, 0.4);

--text-primary: #f8fafc;
--text-secondary: #fbbf24;
--text-muted: #94a3b8;

--color-must-watch: #fbbf24;
--color-recommended: #f59e0b;
--color-average: #e2e8f0;
--color-skip: #64748b;

--gradient-logo: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%);
--gradient-glow: radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, rgba(6, 8, 7, 0) 70%);
```

## Component & Card Grammar

- **Match Cards**: Translucent pitch-glass tiles with 0.08 alpha white borders that illuminate to warm gold on hover.
- **Score & Badges**: High-contrast gold badges (`#fbbf24`) with drop shadows for immediate glanceability.
- **Background Ambiance**: Subtle radial pitch glow (`rgba(16, 185, 129, 0.12)`) simulating floodlights on grass.
