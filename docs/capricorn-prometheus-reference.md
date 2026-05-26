# CapricornPROMETHEUS Reference Inventory

Source folder:

`C:\Users\Drago\OneDrive\Documents\CapricornPROMETHEUS1.5`

This folder appears to be a Capricorn Astrology Software / Prometheus settings library. The files are mostly proprietary binary configuration files, but many contain zlib-compressed UTF-16 metadata that can be decoded for names, categories, descriptions, and likely setting keys.

## Inventory

| Area | Count | Notes |
| --- | ---: | --- |
| Wheel Designs | 259 | Major UI/design reference source for natal, transit, biwheel, triwheel, multiwheel, in-mundo, Gauquelin, Vedic, heliocentric, and black/classic styles. |
| Page Designs | 209 | Layout templates for single wheel, aspectarians, Arabic Parts, medieval pages, talisman pages, synastry, primary/secondary directions, and planetarium views. |
| Aspect Configurations | 50 | Orb/aspect presets including default, medieval, transits 1 degree, conjunction-only, hard/soft, Ptolemy, mundane, in-mundo, harmonic, synastry, Vedic, and stellar. |
| Point Configurations | 34 | Point sets such as 7 planets, 10 planets, Asc/MC, Chiron, Part of Fortune, nodes, asteroids, bright stars, and house cusps. |
| Arabic Parts Configurations | 17 | Al-Biruni, Ptolemy, Brunacci-Onorati, horary, lunar phase, and house-topic lots. |
| Rulership Configurations | 9 | Traditional, Modern, Bonatti, Lilly, Omar, Ptolemy, day/night, Vedic, and Astrodynes rulership presets. |
| Astrology Systems | 2+ | Zodiac system references, including Zodiac13 configurations and a Lahiri 13 file. Useful direction for sidereal/Lahiri support. |
| Astrology Settings | 2 | Large binary settings profiles. These confirm the app should treat systems/settings as first-class selectable profiles. |
| Display Schemes | 14 | Visual themes, including nebula/sombrero-style display references. |
| Planetarium Configurations | 11 | Planetarium-style views and overlays. |
| Primary Directions | 18 | Direction-related configurations and a separate `Primary Directions.zip`. |
| Backgrounds | 4 | Bitmap backgrounds: `background.bmp`, `background2.bmp`, `background3.bmp`, `golden_sky.bmp`. |
| Chart Databases | 5 | Personal chart databases. Avoid reading/importing unless explicitly requested. |

## Useful Files To Study First

Aspect/orb presets:

- `Aspect Configurations\transits_1_deg.asp_conf`
- `Aspect Configurations\Medieval.asp_conf`
- `Aspect Configurations\ptolemy no pll.asp_conf`
- `Aspect Configurations\Standard Western variable orbs.asp_conf`
- `Aspect Configurations\conjunctions 1 deg.asp_conf`
- `Aspect Configurations\trine_square_sextile.asp_conf`

Traditional astrology rules:

- `Rulership Configurations\Traditional.rl_conf`
- `Rulership Configurations\Traditional - Lilly.rl_conf`
- `Rulership Configurations\Traditional - Bonatti.rl_conf`
- `Rulership Configurations\Traditional - Ptolemy.rl_conf`

System settings:

- `Astrology Systems\Zodiac13 Configurations\Default.zodiac13_conf`
- `Astrology Systems\Zodiac13 Configurations\Lahiri 13.zodiac13_conf`
- `Astrology Settings\default.astrology_settings`
- `Astrology Settings\New.astrology_settings`

Wheel/page style references:

- `Wheel Designs\traditional1.wheel_design`
- `Wheel Designs\traditional2.wheel_design`
- `Wheel Designs\EuroWheel1a.wheel_design`
- `Wheel Designs\BasicEuro1.wheel_design`
- `Wheel Designs\northnode 12 classic.wheel_design`
- `Wheel Designs\northnode 12 black.wheel_design`
- `Page Designs\single wheel.page_design`
- `Page Designs\wheel_aspectarian.page_design`
- `Page Designs\natal_progressed_transits.page_design`
- `Page Designs\medieval wheel 1.page_design`
- `Page Designs\lilly_dignities.page_design`

## Import Strategy

1. Build a local decoder that extracts zlib chunks and UTF-16 strings from the config files.
2. Generate a JSON index of metadata only: filename, type, display name, description, and feature tags.
3. Use the metadata to create app presets, not to blindly copy proprietary binary settings.
4. Start with hand-modeled presets for electional astrology: tight transit orbs, conjunction/trine/sextile/square filters, angularity emphasis, and traditional dignity/rulership scoring.
5. Keep chart databases out of source control unless the user explicitly asks to import specific records.

## Application Opportunities

- Add a `Traditional` mode using Lilly/Bonatti/Ptolemy rulership and dignity presets.
- Add a `Transit 1 degree` electional scoring preset.
- Add UI theme choices inspired by `classic`, `black`, `Euro`, and `traditional` wheel designs.
- Add Arabic Parts as optional electional targets, especially Fortune, Spirit, 10th-house lots, and horary lots. Fortune and Spirit are now implemented as first Lots.
- Add page modes: `Wheel`, `Wheel + Aspectarian`, `Medieval Data`, and `Transit Search`.
- Add point-set presets for `7 Classical`, `10 Planets`, `Planets + Nodes`, and `Planets + Fortune`.
- Keep sidereal systems prominent, with Lahiri as the first implemented sidereal mode and tropical preserved as an optional comparison system.
- Add major house systems incrementally. Whole Sign and Equal House are simple foundations; Topocentric/Polich-Page and Koch are now modeled as the first quadrant-style house systems.
