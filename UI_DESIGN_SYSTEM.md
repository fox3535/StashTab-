# StashTab UI Design System (For AI UI Generation)

## 1. Brand Identity & Vibe
StashTab is a premium, B2B SaaS Point of Sale and Inventory Management system for TCG card vendors. The UI must feel like a high-end fintech operating system—sleek, fast, authoritative, and modern. It should NOT look like a game or a casual collector's app. 

## 2. Color Palette (Obsidian & Ultraviolet Theme)
- **App Background:** Pure Black (`#000000`) — Optimized for OLED screens and reducing glare at convention booths.
- **Surface/Card Background:** Deep Zinc (`#09090B`) with subtle borders (`#27272A`).
- **Primary Accent (Ultraviolet):** `#8B5CF6` (Hover state: `#7C3AED`). Used for primary CTAs, active tab underlines, and focus rings.
- **Data Accent (Bright Violet):** `#A855F7`. Used specifically for line graphs, profit indicators, and active dashboard metrics.
- **Primary Text:** Pure White (`#FFFFFF`).
- **Secondary Text:** Muted Zinc (`#A1A1AA`). Used for labels, subtitles, and inactive tabs.
- **Success/Profit:** Emerald Green (`#10B981`).
- **Shadows/Glows:** Use colored shadows for depth. E.g., primary buttons should have `shadow-lg shadow-purple-600/30`.

## 3. Typography
- **Font Family:** Inter, or system-ui sans-serif.
- **Headings (H1, H2):** Bold, tight tracking. Pure white.
- **Dashboard Stats (e.g., Total Profit):** Very large (text-4xl/5xl), bold, pure white.
- **Body Text:** Normal weight, `#A1A1AA` for readability on black.
- **Buttons/CTAs:** Semibold, slightly tracked.

## 4. Component Styling Guidelines
- **Buttons:** Fully rounded corners (`rounded-xl`), no harsh gradients. Solid ultraviolet background with white text. Large, chunky touch targets for mobile POS usage.
- **Cards:** Dark grey (`bg-zinc-950`), 1px subtle border (`border-zinc-800`), rounded-xl.
- **Inputs/Search Bars:** Flat, dark backgrounds (`bg-zinc-900`), no harsh outlines unless focused. Focus state should be a solid ultraviolet ring.
- **Tabs:** Underlined style. Active tab has a thick ultraviolet bottom border and white text. Inactive tabs are muted zinc.
- **Graphs:** Minimalist. Remove gridlines. Use a smooth bezier curve with a bright violet stroke (`#A855F7`) and a fading violet gradient fill below the line.
- **Lists/Tables:** No heavy borders or zebra striping. Separate rows with subtle 1px dividers (`border-zinc-800`). Header labels are uppercase, small, tracked, and muted zinc (`#A1A1AA`). Numeric and price data is monospace, right-aligned, and pure white for quick scanning.
