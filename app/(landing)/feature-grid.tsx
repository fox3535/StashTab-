'use client'
import React from 'react'
import { motion } from 'framer-motion'
import {
    Anchor,
    DatabaseZap,
    PenLine,
    QrCode,
} from 'lucide-react'

const features = [
    {
        icon: QrCode,
        tag: 'IDENTITY',
        title: 'Never re-key a card',
        body: 'Every card gets a persistent SKU with a locked barcode and QR code. One identity across all acquisitions, so you never re-sticker or re-enter a card.',
    },
    {
        icon: DatabaseZap,
        tag: 'SYNC',
        title: 'Inventory that syncs itself',
        body: 'Import your Collectr portfolio in seconds. Physical holdings sync locally, so the floor never waits on the cloud and your counts stay current.',
    },
    {
        icon: PenLine,
        tag: 'CONTROL',
        title: 'Take in any binder or bulk haul',
        body: 'Bring non-Collectr inventory into the system with zero friction. Binders, bulk, and boot-hauls get the same locked identity as everything else.',
    },
    {
        icon: Anchor,
        tag: 'CAPITAL',
        title: 'Catch stagnant stock early',
        body: 'The Paperweight Rule auto-flags inventory sitting 60+ days and alerts you to discount it, so dead capital starts moving again.',
    },
]

export default function FeatureGrid() {
    return (
        <section id="features" className="relative py-20 md:py-24">
            <div className="mx-auto max-w-6xl px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55 }}
                    className="max-w-2xl"
                >
                    <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
                        02 · Your inventory, handled
                    </p>
                    <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                        Your Inventory on Autopilot.
                    </h2>
                    <p className="mt-4 text-lg leading-relaxed text-steel">
                        Automate your SKUs, sync your stock, and track your capital effortlessly.
                        Never lose track of a single card.
                    </p>
                </motion.div>

                <div className="mt-14 grid gap-4 sm:grid-cols-2">
                    {features.map((f, i) => (
                        <motion.div
                            key={f.title}
                            initial={{ opacity: 0, y: 24 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: '-60px' }}
                            transition={{ duration: 0.5, delay: (i % 3) * 0.08 }}
                            className="card-lift group relative rounded-lg border border-border bg-gunmetal p-6"
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex size-11 items-center justify-center rounded-md border border-neon/25 bg-neon/5 transition-all duration-200 group-hover:border-neon/60 group-hover:shadow-[0_0_16px_rgba(139,92,246,0.3)]">
                                    <f.icon className="size-5 text-neon" />
                                </div>
                                <span className="font-mono text-xs tracking-[0.24em] text-steel/80">
                                    {f.tag}
                                </span>
                            </div>
                            <h3 className="mt-5 font-display text-xl font-semibold text-foreground">
                                {f.title}
                            </h3>
                            <p className="mt-2.5 text-[15px] leading-relaxed text-steel">{f.body}</p>
                            {/* bottom hairline accent */}
                            <div className="absolute inset-x-6 bottom-0 h-px scale-x-0 bg-gradient-to-r from-transparent via-neon to-transparent transition-transform duration-300 group-hover:scale-x-100" />
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
