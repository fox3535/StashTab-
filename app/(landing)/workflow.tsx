'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { Activity, HardDriveDownload, QrCode, ScanLine } from 'lucide-react'

const steps = [
    {
        num: '01',
        icon: HardDriveDownload,
        title: 'Import',
        body: 'Bring inventory in from Collectr or add cards manually.',
    },
    {
        num: '02',
        icon: QrCode,
        title: 'Identify',
        body: 'Assign each item a persistent SKU and barcode.',
    },
    {
        num: '03',
        icon: ScanLine,
        title: 'Sell',
        body: 'Scan cards through the POS from a booth, store or mobile device.',
    },
    {
        num: '04',
        icon: Activity,
        title: 'Track',
        body: 'Maintain inventory counts, acquisition costs, profit and stagnant-stock visibility.',
    },
]

export default function Workflow() {
    return (
        <section id="workflow" className="relative bg-gunmetal/20 py-20 md:py-24">
            <div className="mx-auto max-w-6xl px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55 }}
                    className="max-w-2xl"
                >
                    <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
                        01 · The workflow
                    </p>
                    <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                        From intake to checkout.
                    </h2>
                    <p className="mt-4 text-lg leading-relaxed text-steel">
                        One continuous pipeline for your inventory. No re-keying, no lost cost
                        basis, no guesswork at the table.
                    </p>
                </motion.div>

                <ol className="relative mt-14 grid gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
                    {/* mobile vertical rail */}
                    <div aria-hidden className="absolute left-6 top-2 h-[calc(100%-1rem)] w-px bg-border sm:hidden" />
                    {/* desktop connecting line */}
                    <div
                        aria-hidden
                        className="absolute inset-x-12 top-6 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent lg:block"
                    />

                    {steps.map((s, i) => (
                        <motion.li
                            key={s.num}
                            initial={{ opacity: 0, y: 24 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: '-60px' }}
                            transition={{ duration: 0.5, delay: i * 0.08 }}
                            className="relative flex gap-5 sm:block"
                        >
                            <div className="relative z-10 flex size-12 shrink-0 items-center justify-center rounded-full border border-neon/40 bg-gunmetal font-mono text-sm font-bold text-neon shadow-[0_0_16px_rgba(139,92,246,0.2)]">
                                {s.num}
                            </div>
                            <div className="sm:mt-5">
                                <div className="flex items-center gap-2">
                                    <s.icon className="size-4 text-neon" />
                                    <h3 className="font-display text-xl font-semibold text-foreground">
                                        {s.title}
                                    </h3>
                                </div>
                                <p className="mt-2 text-[15px] leading-relaxed text-steel">{s.body}</p>
                            </div>
                        </motion.li>
                    ))}
                </ol>
            </div>
        </section>
    )
}
