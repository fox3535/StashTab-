'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { Check, Minus, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type CellValue = 'yes' | 'no' | 'partial'

const vendors = ['StashTab', 'Collection Apps', 'Listing Tools', 'Spreadsheets'] as const

const rows: { feature: string; note: string; values: Record<(typeof vendors)[number], CellValue> }[] = [
    {
        feature: 'Persistent SKUs',
        note: 'Locked barcode/QR identity across re-acquisitions',
        values: { StashTab: 'yes', 'Collection Apps': 'no', 'Listing Tools': 'partial', Spreadsheets: 'partial' },
    },
    {
        feature: 'Mobile Web POS',
        note: 'Checkout from any phone browser, no install',
        values: { StashTab: 'yes', 'Collection Apps': 'no', 'Listing Tools': 'no', Spreadsheets: 'no' },
    },
    {
        feature: 'Weighted Cost Distribution',
        note: 'Trade cost basis split by market-value weight',
        values: { StashTab: 'yes', 'Collection Apps': 'no', 'Listing Tools': 'no', Spreadsheets: 'partial' },
    },
    {
        feature: 'Paperweight Rule',
        note: 'Automated 60+ day stagnant inventory flags',
        values: { StashTab: 'yes', 'Collection Apps': 'partial', 'Listing Tools': 'no', Spreadsheets: 'no' },
    },
    {
        feature: 'Local Image Caching',
        note: 'Sub-millisecond offline-first artwork retrieval',
        values: { StashTab: 'yes', 'Collection Apps': 'no', 'Listing Tools': 'no', Spreadsheets: 'no' },
    },
]

function CellMark({ value, highlight }: { value: CellValue; highlight?: boolean }) {
    if (value === 'yes')
        return (
            <span
                className={cn(
                    'mx-auto flex size-6 items-center justify-center rounded-full',
                    highlight ? 'bg-neon/15 text-neon shadow-[0_0_12px_rgba(139,92,246,0.35)]' : 'bg-neon/10 text-neon'
                )}
            >
                <Check className="size-3.5" strokeWidth={3} />
            </span>
        )
    if (value === 'partial')
        return (
            <span className="mx-auto flex size-6 items-center justify-center rounded-full bg-sky-400/10 text-sky-400">
                <Minus className="size-3.5" strokeWidth={3} />
            </span>
        )
    return (
        <span className="mx-auto flex size-6 items-center justify-center rounded-full bg-white/[0.03] text-steel/40">
            <X className="size-3.5" strokeWidth={3} />
        </span>
    )
}

export default function ComparisonMatrix() {
    return (
        <section id="compare" className="relative py-20 md:py-24">
            <div className="mx-auto max-w-6xl px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55 }}
                    className="max-w-2xl"
                >
                    <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
                        05 · Why StashTab
                    </p>
                    <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                        Built for the whole business.
                    </h2>
                    <p className="mt-4 text-lg leading-relaxed text-steel">
                        Collection apps track your cards. Listing tools post them. StashTab runs the
                        business behind them — inventory, point of sale, and cost basis in one place.
                    </p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 28 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.6, delay: 0.1 }}
                    className="scrollbar-slim mt-14 overflow-x-auto pb-2"
                >
                    <div className="relative min-w-[760px]">
                        {/* holo highlight overlay for the StashTab column */}
                        <div
                            aria-hidden
                            className="holo-border pointer-events-none absolute -bottom-2 -top-2 z-0 rounded-lg opacity-90"
                            style={{ left: 'calc(32% - 6px)', width: 'calc(17% + 12px)' }}
                        />

                        <div className="relative z-10">
                            {/* header row */}
                            <div className="grid grid-cols-[1.9fr_1fr_1fr_1fr_1fr] items-center gap-x-2 border-b border-border px-4 pb-4">
                                <span className="font-mono text-xs uppercase tracking-[0.22em] text-steel">
                                    Capability
                                </span>
                                {vendors.map((v) => (
                                    <div key={v} className="text-center">
                                        {v === 'StashTab' ? (
                                            <span className="font-display text-base font-bold text-neon text-glow-accent">
                                                StashTab
                                            </span>
                                        ) : (
                                            <span className="font-display text-base font-semibold text-steel">
                                                {v}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>

                            {/* data rows */}
                            {rows.map((row, i) => (
                                <div
                                    key={row.feature}
                                    className={cn(
                                        'grid grid-cols-[1.9fr_1fr_1fr_1fr_1fr] items-center gap-x-2 border-b border-border/60 px-4 py-5 transition-colors duration-200 hover:bg-gunmetal/60',
                                        i % 2 === 1 && 'bg-row-alt/60'
                                    )}
                                >
                                    <div>
                                        <p className="font-display text-base font-semibold text-foreground">
                                            {row.feature}
                                        </p>
                                        <p className="mt-0.5 text-sm leading-relaxed text-steel">{row.note}</p>
                                    </div>
                                    {vendors.map((v) => (
                                        <div key={v} className="text-center">
                                            <CellMark value={row.values[v]} highlight={v === 'StashTab'} />
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                </motion.div>

                <p className="mt-6 font-mono text-xs tracking-wide text-steel/70">
                    <span className="text-neon">●</span> full support&ensp;
                    <span className="text-sky-400">●</span> partial&ensp;
                    <span className="text-steel/50">●</span> not available
                </p>
            </div>
        </section>
    )
}
