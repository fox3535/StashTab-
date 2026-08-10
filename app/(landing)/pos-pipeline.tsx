'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import {
    Scale,
    ScanLine,
    Smartphone,
    PackagePlus,
    type LucideIcon,
} from 'lucide-react'
import { PhoneScreenshot } from './phone-screenshot'

/* ---------- stylized phone mockup frame ---------- */
function PhoneMock({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <div
            className={cn(
                'relative mx-auto w-[264px] rounded-[2rem] border border-border bg-obsidian p-2 shadow-2xl shadow-black/70',
                className
            )}
        >
            <div className="absolute left-1/2 top-2 z-10 h-1.5 w-16 -translate-x-1/2 rounded-full bg-surface" />
            <div className="overflow-hidden rounded-[1.55rem] border border-border bg-gunmetal">
                <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                    <span className="font-display text-xs font-bold text-foreground">
                        Stash<span className="text-neon">Tab</span>
                    </span>
                    <span className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-steel">
                        <span className="size-1.5 animate-blink rounded-full bg-neon" />
                        Live
                    </span>
                </div>
                {children}
            </div>
        </div>
    )
}

function MockScanPos() {
    return (
        <div className="space-y-2.5 p-3.5">
            <div className="relative overflow-hidden rounded-md border border-neon/50 bg-surface px-3 py-2.5 shadow-[0_0_14px_rgba(139,92,246,0.25)]">
                <div className="scan-beam !left-2 !right-2" />
                <p className="font-mono text-[10px] text-neon">▮ PKM-SIT-193-0042</p>
            </div>
            <div className="rounded-md border border-border bg-obsidian p-3">
                <div className="flex items-center gap-2.5">
                    <div className="h-12 w-9 rounded-sm border border-neon/30 bg-gradient-to-br from-neon/25 via-holo-pink/15 to-holo-gold/15" />
                    <div className="min-w-0">
                        <p className="truncate text-[11px] font-semibold text-foreground">Azure-Drake VSTAR</p>
                        <p className="font-mono text-[9px] text-steel">SIT-193 · 3 in stock</p>
                    </div>
                    <p className="ml-auto font-mono text-sm font-bold text-neon">$84.99</p>
                </div>
            </div>
            <div className="flex items-center justify-between rounded-md border border-border bg-obsidian px-3 py-2 font-mono text-[10px] text-steel">
                <span>STOCK −1</span>
                <span className="text-emerald-400">DEDUCTED ✓</span>
            </div>
            <div className="rounded-md bg-neon py-2.5 text-center font-display text-xs font-bold text-white">
                Finalize Sale · $84.99
            </div>
        </div>
    )
}

function MockPlaceholderTrades() {
    return (
        <div className="space-y-2.5 p-3.5">
            <div className="rounded-md border border-dashed border-holo-gold/60 bg-holo-gold/5 p-3">
                <div className="flex items-center justify-between">
                    <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-holo-gold">
                        Trade bucket · running
                    </p>
                    <PackagePlus className="size-3.5 text-holo-gold" />
                </div>
                <p className="mt-1.5 font-mono text-lg font-bold text-foreground">$240.00</p>
                <p className="font-mono text-[9px] text-steel">14 cards · bulk acquisition</p>
            </div>
            <div className="rounded-md border border-dashed border-holo-gold/35 bg-holo-gold/[0.02] p-3">
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-holo-gold/80">
                    Trade bucket · table 2
                </p>
                <p className="mt-1.5 font-mono text-lg font-bold text-foreground">$86.50</p>
                <p className="font-mono text-[9px] text-steel">5 cards · in progress</p>
            </div>
            <p className="px-1 text-center font-mono text-[9px] text-steel">
                settle at close-out → cost basis preserved
            </p>
        </div>
    )
}

function MockWeightedCost() {
    const rows = [
        ['Azure-Drake VSTAR', '$84.99', '54%', '$54.00'],
        ['Ember-Fist ACE', '$42.00', '27%', '$27.00'],
        ['Tide-Caller SR', '$29.99', '19%', '$19.00'],
    ]
    return (
        <div className="p-3.5">
            <div className="mb-2 flex items-center justify-between">
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-steel">
                    Trade cost $100.00
                </p>
                <Scale className="size-3.5 text-neon" />
            </div>
            <div className="overflow-hidden rounded-md border border-border">
                <div className="grid grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr] gap-1 border-b border-border bg-obsidian px-2.5 py-1.5 font-mono text-[8px] uppercase tracking-wider text-steel">
                    <span>Card</span>
                    <span className="text-right">Mkt</span>
                    <span className="text-right">Wt</span>
                    <span className="text-right">Cost</span>
                </div>
                {rows.map(([name, mkt, wt, cost]) => (
                    <div key={name} className="grid grid-cols-[1.4fr_0.8fr_0.6fr_0.8fr] gap-1 border-b border-border/60 px-2.5 py-2 font-mono text-[9px] last:border-0">
                        <span className="truncate text-foreground">{name}</span>
                        <span className="text-right text-steel">{mkt}</span>
                        <span className="text-right text-holo-pink">{wt}</span>
                        <span className="text-right font-semibold text-neon">{cost}</span>
                    </div>
                ))}
            </div>
            <p className="mt-2 text-center font-mono text-[9px] text-emerald-400">
                ✓ cost-basis tracked to the cent
            </p>
        </div>
    )
}

/* ---------- section ---------- */
type PipelineItem = {
    icon: LucideIcon
    kicker: string
    title: string
    body: string
    mock?: React.ReactNode
    screenshot?: string
}

const pipeline: PipelineItem[] = [
    {
        icon: ScanLine,
        kicker: 'SCAN · DEDUCT · FINALIZE',
        title: 'Sell at scanner speed',
        body: 'Scan a card to pull details, deduct stock, and finalize through the barcode POS. No lag, no crashes — the queue moves at the speed of your scanner.',
        mock: <MockScanPos />,
    },
    {
        icon: Smartphone,
        kicker: 'ANY PHONE · ANY BROWSER',
        title: 'Sell from any phone',
        body: 'Run checkout from anywhere in your booth on a dedicated mobile web interface. No app-store installs, no paired hardware.',
        screenshot: '/screenshots/pos-checkout.png',
    },
    {
        icon: PackagePlus,
        kicker: 'BULK SHOW ACQUISITIONS',
        title: 'Bulk buys, zero bottleneck',
        body: "Create 'running total' placeholder-trade buckets for bulk show acquisitions. Keep the line moving — reconcile when the floor clears.",
        mock: <MockPlaceholderTrades />,
    },
    {
        icon: Scale,
        kicker: 'AUTOMATIC COST MATH',
        title: 'Cost basis, tracked to the cent',
        body: 'Weighted cost distribution splits trade costs by market-value weight automatically, so your cost basis and profit are flawless across every buy-in.',
        mock: <MockWeightedCost />,
    },
]

export default function PosPipeline() {
    return (
        <section id="pipeline" className="relative overflow-hidden bg-gunmetal/30 py-20 md:py-24">
            <div className="dot-grid absolute inset-0 opacity-40" aria-hidden />
            <div className="relative mx-auto max-w-6xl px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55 }}
                    className="max-w-2xl"
                >
                    <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
                        03 · Sell anywhere
                    </p>
                    <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                        Your Store on the Go.
                    </h2>
                    <p className="mt-4 text-lg leading-relaxed text-steel">
                        A checkout line that runs on the phone in your pocket — with back-office
                        math your accountant will love.
                    </p>
                </motion.div>

                <div className="mt-16 space-y-16 md:mt-20 md:space-y-20">
                    {pipeline.map((item, i) => {
                        const flip = i % 2 === 1
                        return (
                            <motion.div
                                key={item.title}
                                initial={{ opacity: 0, y: 32 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: '-100px' }}
                                transition={{ duration: 0.6 }}
                                className={cn(
                                    'grid items-center gap-12 lg:grid-cols-2 lg:gap-20',
                                    flip && 'lg:[&>*:first-child]:order-2'
                                )}
                            >
                                <div className={cn(flip && 'lg:pl-8', !flip && 'lg:pr-8')}>
                                    <div className="flex items-center gap-3">
                                        <div className="flex size-10 items-center justify-center rounded-md border border-neon/30 bg-neon/5">
                                            <item.icon className="size-5 text-neon" />
                                        </div>
                                        <span className="font-mono text-xs tracking-[0.24em] text-neon">
                                            {item.kicker}
                                        </span>
                                    </div>
                                    <h3 className="mt-5 font-display text-3xl font-bold tracking-tight text-foreground">
                                        {item.title}
                                    </h3>
                                    <p className="mt-3 max-w-md text-base leading-relaxed text-steel">
                                        {item.body}
                                    </p>
                                    <div className="mt-6 h-px w-24 bg-gradient-to-r from-neon to-transparent" />
                                </div>
                                <div className="relative">
                                    <div
                                        aria-hidden
                                        className={cn(
                                            'absolute -inset-8 rounded-full blur-3xl',
                                            flip ? 'bg-holo-pink/8' : 'bg-neon/8'
                                        )}
                                    />
                                    <motion.div
                                        initial={{ rotate: flip ? 3 : -3 }}
                                        whileInView={{ rotate: flip ? 1.5 : -1.5 }}
                                        viewport={{ once: true }}
                                        transition={{ duration: 0.8 }}
                                        className="relative"
                                    >
                                        {item.screenshot ? (
                                            <PhoneScreenshot src={item.screenshot} alt={item.title} />
                                        ) : (
                                            <PhoneMock>{item.mock}</PhoneMock>
                                        )}
                                    </motion.div>
                                </div>
                            </motion.div>
                        )
                    })}
                </div>
            </div>
        </section>
    )
}
