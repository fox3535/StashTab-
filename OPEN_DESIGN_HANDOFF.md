\# StashTab — Design Handoff for Open Design



> \*\*What this is:\*\* a complete handoff of the StashTab design system as it is \*actually built\* in the codebase. Read this to understand the established visual language, then design new screens/components that match it exactly.

>

> \*\*Source of truth:\*\* every color, font, shadow, and effect below is defined in `app/globals.css`. If this doc and the code ever disagree, trust `app/globals.css`.

>

> \*\*Companion doc:\*\* `UI\_DESIGN\_SYSTEM.md` is a shorter, prompt-style brief. This file is the detailed reference.



\---



\## 1. Product \& Brand Identity



\- \*\*Product:\*\* StashTab — a Point-of-Sale + inventory-management system for \*\*TCG (trading card game) vendors\*\*. Tagline: \*"Own the Booth. Master the Inventory."\*

\- \*\*Audience:\*\* card sellers working convention booths and trade shows. \*\*Mobile-first\*\* — they sell on their phones, on the road, in bright halls.

\- \*\*Positioning:\*\* a \*\*premium B2B fintech operating system\*\*. Think Linear / Vercel / Stripe in dark mode. It must feel sleek, fast, and authoritative.

\- \*\*It must NOT feel like\*\* a game, a toy, or a casual collector's app. No cartoonish elements, no rainbow "gamer" aesthetics.

\- \*\*Dark-mode only.\*\* The app is locked to dark theme (`<html class="dark">`). The pure-black background is a deliberate choice for \*\*OLED screens and glare reduction at convention booths\*\*.



\### Design principles

1\. \*\*High contrast, low noise.\*\* Pure white text on pure black; muted zinc for everything secondary. Color is reserved for meaning (accent = action, emerald = profit, ember = warning).

2\. \*\*Data is the hero.\*\* Prices, SKUs, and counts are monospace, right-aligned, and bright for fast scanning across a busy show floor.

3\. \*\*Glow, don't decorate.\*\* Depth comes from soft ultraviolet glows and subtle borders — not heavy gradients or drop shadows.

4\. \*\*Big touch targets.\*\* POS buttons are chunky and thumb-friendly.

5\. \*\*Consistent rhythm.\*\* Every marketing section uses the same kicker → heading → sub pattern (see §11).



\---



\## 2. Color System



\### 2.1 Core palette

These are the raw tokens (defined in `:root, .dark`). The "Tailwind name" is what you use in classes.



| Token | Hex | Tailwind class | Role |

|---|---|---|---|

| `--bg-obsidian` | `#000000` | `bg-obsidian` | App background (pure black, OLED) |

| `--bg-gunmetal` | `#09090B` | `bg-gunmetal` | Cards / surfaces (zinc-950) |

| `--bg-surface` | `#18181B` | `bg-surface` | Inputs, hover, inner panels (zinc-900) |

| `--accent-cyan` | `#8B5CF6` | `bg-neon` / `text-neon` | \*\*Primary ultraviolet accent\*\* (violet-500) |

| `--accent-violet` | `#A855F7` | `text-data` | \*\*Bright violet data accent\*\* (graphs, active metrics) |

| `--holo-pink` | `#A855F7` | `text-holo-pink` | Remapped to bright violet (tonal) |

| `--holo-gold` | `#7C3AED` | `text-holo-gold` | Remapped to deep violet (violet-600) |

| `--text-primary` | `#FFFFFF` | `text-foreground` | Primary text |

| `--text-secondary` | `#A1A1AA` | `text-steel` | Secondary text / labels (zinc-400) |

| `--border-subtle` | `#27272A` | `border-border` | Subtle borders (zinc-800) |

| `--row-alt` | `#0C0C0E` | `bg-row-alt` | Alternating table rows |

| `--ember` | `#FF7A2F` | `text-ember` | Semantic warning (e.g. Paperweight flag) |



> \*\*Naming quirk (important):\*\* the tokens are historically named `accent-cyan`, `neon`, `holo-pink`, `holo-gold` from an older cyan/holographic theme. Their \*\*values are now all violet\*\*. Do not be misled by the names — `neon` = ultraviolet `#8B5CF6`, not cyan.



\### 2.2 Semantic (shadcn) mapping

Used by shadcn/ui components via `bg-primary`, `text-muted-foreground`, etc.



| Token | Value | Notes |

|---|---|---|

| `--primary` | `#7C3AED` | Solid ultraviolet CTA (violet-600) |

| `--primary-foreground` | `#FFFFFF` | White text on primary buttons |

| `--background` / `--foreground` | `#000000` / `#FFFFFF` | |

| `--card` | `#09090B` | |

| `--secondary` / `--muted` / `--accent` | `#18181B` | |

| `--muted-foreground` | `#A1A1AA` | |

| `--destructive` | `#EF4444` | Red |

| `--border` / `--input` | `#27272A` | |

| `--ring` | `#8B5CF6` | Ultraviolet focus ring |



\### 2.3 Charts

`--chart-1 #8B5CF6` · `--chart-2 #A855F7` · `--chart-3 #C4B5FD` · `--chart-4 #7C3AED` · `--chart-5 #10B981` (emerald = profit).



\### 2.4 The brand gradient

A single violet sweep used for premium/rare indicators, the logo, and shimmer text:



&#x20;   linear-gradient(135deg, #7C3AED 0%, #A855F7 50%, #C4B5FD 100%)



\### 2.5 Glow color

All ultraviolet glows use the RGB base `rgb(139 92 246 / <alpha>)`.



\---



\## 3. Typography



Three Google fonts loaded in `app/layout.tsx`:



| Font | CSS var | Tailwind | Role | Weights |

|---|---|---|---|---|

| \*\*Inter\*\* | `--font-inter` | `font-sans` | Body \& UI text (default) | 400–700 |

| \*\*Space Grotesk\*\* | `--font-space-grotesk` | `font-display` | Headings, display, logo | 400/500/600/700 |

| \*\*JetBrains Mono\*\* | `--font-jetbrains-mono` | `font-mono` | Data: SKUs, prices, counts, kickers | 400/500/600/700 |



\### Type patterns

\- \*\*Section kicker:\*\* `font-mono text-xs uppercase tracking-\[0.28em] text-neon` → format `0X · LABEL` (e.g. `01 · FEATURES`).

\- \*\*Display heading:\*\* `font-display text-4xl sm:text-5xl font-bold tracking-tight text-foreground`.

\- \*\*Section sub:\*\* `text-lg text-steel`.

\- \*\*Dashboard stat:\*\* `font-display text-4xl/5xl font-bold text-foreground` (pure white, very large).

\- \*\*Data / price:\*\* `font-mono`, right-aligned, white; labels in `text-steel`.

\- All of `h1–h4` default to `font-display` via base layer.



\---



\## 4. Radius, Spacing \& Layout



\- \*\*Base radius:\*\* `--radius: 0.5rem`. Scale: `sm = radius−4px`, `md = radius−2px`, `lg = radius`, `xl = radius+4px`.

\- \*\*Marketing container:\*\* `mx-auto max-w-6xl px-6`.

\- \*\*Section vertical rhythm:\*\* `py-24 md:py-32`.

\- \*\*Cards:\*\* `rounded-xl`, `bg-gunmetal`, `border border-border`.

\- \*\*Buttons:\*\* `rounded-md` (shadcn default) — POS CTAs sometimes use larger radii + chunky padding.

\- Grid layouts use Tailwind grid; the pipeline alternates `lg:grid-cols-2` rows.



\---



\## 5. Elevation, Shadows \& Glows



\### Shadow scale (all pure-black based)

| Token | Value |

|---|---|

| `--shadow-2xs` / `xs` | `0 1px 3px rgb(0 0 0 / 0.35)` |

| `--shadow-sm` / default | `0 2px 6px rgb(0 0 0 / 0.45)` |

| `--shadow-md` | `0 4px 12px rgb(0 0 0 / 0.5)` |

| `--shadow-lg` | `0 8px 24px rgb(0 0 0 / 0.55)` |

| `--shadow-xl` | `0 16px 40px rgb(0 0 0 / 0.6)` |

| `--shadow-2xl` | `0 24px 60px rgb(0 0 0 / 0.65)` |



\### Glow helpers (utility classes)

\- `.glow-accent` → `box-shadow: 0 0 24px rgb(139 92 246 / 0.35)`

\- `.glow-accent-sm` → `box-shadow: 0 0 12px rgb(139 92 246 / 0.25)`

\- `.text-glow-accent` → `text-shadow: 0 0 14px rgb(139 92 246 / 0.55)`

\- Primary CTAs: `shadow-lg shadow-purple-600/30` style colored glow.



\---



\## 6. Signature Visual Effects (the "StashTab look")



These utilities live in `@layer utilities` in `globals.css`. Reuse them rather than reinventing.



\- \*\*`.holo-border`\*\* — a violet \*gradient border\* (premium/rare indicator). Technique: transparent border + `padding-box` gunmetal fill + `border-box` violet gradient.

\- \*\*`.holo-text`\*\* — animated violet shimmer text (gradient clipped to text, `holo-sheen` animation).

\- \*\*`.glass-panel`\*\* — dark glassmorphism for modals/drawers/chips: `background: rgb(9 9 11 / 0.9)` + `backdrop-filter: blur(18px)`.

\- \*\*`.dot-grid`\*\* — subtle dot texture for hero/section backgrounds: `radial-gradient(rgb(255 255 255 / 0.07) 1px, transparent 1px)` at `24px 24px`. Pair with `.dot-grid-drift` to animate.

\- \*\*`.scan-beam`\*\* — an animated 2px ultraviolet "laser" line that sweeps vertically (the card-scan motif).

\- \*\*`.card-lift`\*\* — interactive hover: `translateY(-4px)` + violet border + layered shadow.

\- \*\*`.mask-fade-b` / `.mask-fade-edges`\*\* — gradient masks to fade content out.

\- \*\*`.scrollbar-slim`\*\* — 6px slim scrollbars inside panels.



\---



\## 7. Motion



CSS keyframe animations (referenced via `--animate-\*`):



| Animation | Duration | Use |

|---|---|---|

| `scanline` | 3.4s | scan-beam sweep |

| `holo-sheen` | 6s | shimmer text |

| `pulse-glow` | 2.4s | pulsing ultraviolet glow |

| `float-slow` / `float-slower` | 7s / 10s | floating chips (slower is reversed) |

| `blink` | 1.6s | "live" status dots |

| `ticker` | 30s | horizontal marquee |

| `ember-pulse` | 1.4s | warning pulse |

| `grid-drift` | 24s | drifting dot-grid |



\*\*Framer Motion\*\* is used throughout the landing page: fade-up on scroll (`whileInView`, `viewport={{ once: true }}`), subtle rotations on phone frames (−3° → −1.5°), staggered chip entrances. Keep motion subtle and purposeful.



\---



\## 8. Component Library



\- \*\*Framework:\*\* shadcn/ui, \*\*style = `new-york`\*\*, base color = `neutral`, CSS variables enabled. Icons = \*\*lucide-react\*\*.

\- Components live in `components/ui/\*`.



\### Button variants (`components/ui/button.tsx`)

| Variant | Look |

|---|---|

| `default` | `bg-primary text-primary-foreground` → solid violet `#7C3AED`, white text |

| `destructive` | red `#EF4444`, white text |

| `outline` | border + transparent bg, hover fills |

| `secondary` | `bg-secondary` (`#18181B`) |

| `ghost` | transparent, hover fills |

| `link` | violet underlined text |



Sizes: `default h-9 px-4` · `sm h-8 px-3` · `lg h-10 px-6` · `icon size-9`. Base `rounded-md`.



\### Conventions

\- \*\*Cards:\*\* `bg-gunmetal` + `border-border` + `rounded-xl`; add `.card-lift` for interactive ones.

\- \*\*Inputs/search:\*\* flat `bg-surface`, no harsh outline; focus = ultraviolet ring (`--ring`).

\- \*\*Tabs:\*\* underlined; active = thick ultraviolet bottom border + white text; inactive = muted zinc.

\- \*\*Tables/lists:\*\* no zebra striping or heavy borders; 1px `border-border` dividers; header labels uppercase, small, tracked, `text-steel`; numeric cells monospace, right-aligned, white.

\- \*\*Graphs:\*\* minimalist, no gridlines; smooth bezier stroke in bright violet `#A855F7` with a fading violet gradient fill.



\---



\## 9. Iconography



\- \*\*Library:\*\* `lucide-react` (stroke icons).

\- Standard sizing via `size-\*` utilities (e.g. `size-4`, `size-5`); stroke width defaults to 2, occasionally bumped to 3 for tiny status marks.

\- Icons inherit `currentColor`; accent icons use `text-neon`.



\---



\## 10. Brand \& Logo (`components/logo.tsx`)



\- \*\*`StashTabMark`\*\* — an `ST` monogram in a `size-8 rounded-md` tile: `bg-gunmetal`, `border-neon/40`, a 25%-opacity violet gradient overlay, and `text-glow-accent` on the letters.

\- \*\*Wordmark\*\* — SVG with the brand gradient `#C4B5FD → #7C3AED`.

\- Use the monogram for favicons/app icons and the wordmark in headers.



\---



\## 11. Landing Page Architecture (`app/(landing)/page.tsx`)



Section order, top to bottom:



| # | Section | File | Purpose |

|---|---|---|---|

| 1 | \*\*Hero\*\* | `hero-section.tsx` | Headline + real POS screenshot in a phone frame + floating glass chips |

| 2 | \*\*Feature Grid\*\* | `feature-grid.tsx` | 6 icon feature cards |

| 3 | \*\*POS Pipeline\*\* | `pos-pipeline.tsx` | "Booth Anywhere suite" — 5 alternating rows with phone frames |

| 4 | \*\*Comparison\*\* | `comparison-matrix.tsx` | "Why StashTab" — generic columns (Collection Apps / Listing Tools / Spreadsheets) |

| 5 | \*\*Pricing\*\* | inline + `custom-clerk-pricing.tsx` | "Free on the floor. Pro in the back office." |

| 6 | \*\*CTA / Footer\*\* | `call-to-action.tsx`, `footer.tsx` | Final CTA + sticky mobile CTA bar |



\### Recurring section pattern

Every section follows: mono kicker (`0X · LABEL`) → display heading → steel sub-copy → content, all inside `mx-auto max-w-6xl px-6` with `py-24 md:py-32`.



\### Phone frames

Real screenshots use a shared frame (`app/(landing)/phone-screenshot.tsx`): 264px wide, `rounded-\[2rem]` bezel, a dynamic-island pill, and the screenshot inside a `rounded-\[1.55rem]` screen. Stylized mock screens use `PhoneMock` in `pos-pipeline.tsx` (adds a fake header bar).



\---



\## 12. App Shell Patterns



\- \*\*Back office\*\* (`app/admin/\*`, `app/dashboard/\*`): sidebar navigation (`--sidebar` = pure black), top header, data tables, stat cards. Desktop-first.

\- \*\*POS\*\* (`app/pos/\*`): mobile-first sell/checkout flow; large touch targets; status bars (API connected, Shopify sync). This is the on-the-floor experience the marketing site sells.



\---



\## 13. Source-of-Truth File Map



| File | What it defines |

|---|---|

| `app/globals.css` | \*\*All design tokens\*\*, shadows, animations, signature utilities (THE source of truth) |

| `app/layout.tsx` | Fonts (Inter / Space Grotesk / JetBrains Mono), dark theme lock, metadata |

| `components.json` | shadcn config (new-york, neutral, lucide) |

| `components/ui/\*` | shadcn primitives (button, card, input, table, tabs…) |

| `components/logo.tsx` | Brand marks |

| `app/(landing)/\*` | Marketing sections |

| `app/pos/\*`, `app/admin/\*`, `app/dashboard/\*` | Product shells |

| `UI\_DESIGN\_SYSTEM.md` | Concise prompt-style companion brief |



\---



\## 14. Quick-Reference Cheat Sheet



\- \*\*Backgrounds:\*\* page `#000000` · card `#09090B` · input/hover `#18181B`

\- \*\*Accent (action):\*\* `#8B5CF6` (class `neon`) · CTA solid `#7C3AED` (class `primary`)

\- \*\*Data accent:\*\* `#A855F7` (class `data`)

\- \*\*Text:\*\* primary `#FFFFFF` · secondary `#A1A1AA` (class `steel`)

\- \*\*Border:\*\* `#27272A` · \*\*Warning:\*\* `#FF7A2F` (ember) · \*\*Profit:\*\* `#10B981`

\- \*\*Fonts:\*\* Inter (body) · Space Grotesk (headings) · JetBrains Mono (data)

\- \*\*Radius base:\*\* `0.5rem` · \*\*Container:\*\* `max-w-6xl` · \*\*Section padding:\*\* `py-24 md:py-32`

\- \*\*Brand gradient:\*\* `135deg, #7C3AED → #A855F7 → #C4B5FD`

\- \*\*Glow base:\*\* `rgb(139 92 246 / α)`

\- \*\*Vibe:\*\* premium B2B fintech, dark-mode only, glow-don't-decorate, data-forward.

