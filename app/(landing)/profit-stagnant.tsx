'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, TrendingUp } from 'lucide-react'

/* ─── Stylized profit dashboard fragment ────────────────────────────── */

function ProfitPanel() {
  const metrics = [
    { label: 'Net profit (30d)', value: '$4,218', delta: '+12%' },
    { label: 'Avg. margin', value: '38.4%', delta: '+2.1%' },
    { label: 'Items sold', value: '186', delta: '+23' },
  ]

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-gunmetal shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-emerald-400" />
          <span className="font-display text-sm font-semibold text-foreground">Profit Overview</span>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-steel">Last 30 days</span>
      </div>
      <div className="grid grid-cols-3 gap-px bg-border/40">
        {metrics.map((m) => (
          <div key={m.label} className="bg-gunmetal p-4 text-center">
            <p className="font-mono text-[10px] uppercase tracking-wider text-steel">{m.label}</p>
            <p className="mt-1.5 font-display text-xl font-bold text-foreground">{m.value}</p>
            <p className="mt-0.5 font-mono text-[10px] text-emerald-400">{m.delta}</p>
          </div>
        ))}
      </div>
      {/* Mini bar chart */}
      <div className="border-t border-border px-4 py-4">
        <div className="flex items-end gap-1.5" aria-hidden>
          {[35, 42, 38, 55, 48, 62, 58, 72, 68, 80, 75, 88].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-sm bg-gradient-to-t from-neon/40 to-neon/80"
              style={{ height: `${h * 0.8}px` }}
            />
          ))}
        </div>
        <p className="mt-2 text-center font-mono text-[9px] uppercase tracking-widest text-steel/60">
          Weekly revenue trend
        </p>
      </div>
    </div>
  )
}

function StagnantPanel() {
  const items = [
    { name: 'Fable Knight', sku: 'MTG-WOE-241', days: 94, cost: '$64.00' },
    { name: 'Ancient Glyph SR', sku: 'OPC-EB02-088', days: 71, cost: '$22.50' },
    { name: 'Crystal Wing V', sku: 'PKM-PAR-156', days: 63, cost: '$31.00' },
  ]

  return (
    <div className="overflow-hidden rounded-lg border border-ember/30 bg-gunmetal shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-ember/20 px-4 py-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="size-4 text-ember" />
          <span className="font-display text-sm font-semibold text-foreground">Paperweight Flags</span>
        </div>
        <span className="rounded bg-ember/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-ember">
          3 items
        </span>
      </div>
      <div className="divide-y divide-border/40">
        {items.map((item) => (
          <div key={item.sku} className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="text-sm font-medium text-foreground">{item.name}</p>
              <p className="font-mono text-[10px] text-steel">{item.sku}</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-xs font-semibold text-ember">{item.days}d stagnant</p>
              <p className="font-mono text-[10px] text-steel">cost {item.cost}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-4 py-3">
        <p className="text-center font-mono text-[10px] text-steel">
          Auto-flagged at 60 days · discount or move to free capital
        </p>
      </div>
    </div>
  )
}

/* ─── Section ───────────────────────────────────────────────────────── */

export default function ProfitStagnant() {
  return (
    <section id="profit" className="relative overflow-hidden py-20 md:py-24">
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 50% 50% at 80% 50%, rgba(16,185,129,0.05), transparent 60%)',
        }}
      />

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="grid items-start gap-12 lg:grid-cols-2 lg:gap-16">
          {/* Copy */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.55 }}
          >
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
              Know your numbers
            </p>
            <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              See profit. Kill dead stock.
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-steel">
              Every sale updates your margins in real time. Every card that sits too
              long gets flagged. You always know what&apos;s making money and what&apos;s
              eating shelf space.
            </p>
            <ul className="mt-8 space-y-4">
              <li className="flex items-start gap-3">
                <span className="mt-1.5 size-2 shrink-0 rounded-full bg-emerald-400" />
                <p className="text-base leading-relaxed text-steel">
                  <span className="font-semibold text-foreground">Real-time profit tracking</span>{' '}
                  — acquisition cost, sale price, and margin on every item.
                </p>
              </li>
              <li className="flex items-start gap-3">
                <span className="mt-1.5 size-2 shrink-0 rounded-full bg-ember" />
                <p className="text-base leading-relaxed text-steel">
                  <span className="font-semibold text-foreground">Paperweight Rule</span>{' '}
                  — auto-flags inventory stagnant 60+ days so dead capital starts moving.
                </p>
              </li>
              <li className="flex items-start gap-3">
                <span className="mt-1.5 size-2 shrink-0 rounded-full bg-neon" />
                <p className="text-base leading-relaxed text-steel">
                  <span className="font-semibold text-foreground">Weighted cost basis</span>{' '}
                  — trade costs distributed by market-value weight, tracked to the cent.
                </p>
              </li>
            </ul>
          </motion.div>

          {/* Panels */}
          <div className="space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.55, delay: 0.1 }}
            >
              <ProfitPanel />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.55, delay: 0.2 }}
            >
              <StagnantPanel />
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  )
}
