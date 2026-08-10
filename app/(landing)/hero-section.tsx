'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { ArrowRight, ScanBarcode, Zap } from 'lucide-react'
import { SignUpButton } from '@clerk/nextjs'
import { PhoneScreenshot } from './phone-screenshot'

function scrollToDemo() {
    document.getElementById('pipeline')?.scrollIntoView({ behavior: 'smooth' })
}

const fadeUp = {
    hidden: { opacity: 0, y: 24 },
    show: (i: number) => ({
        opacity: 1,
        y: 0,
        transition: { delay: 0.08 * i, duration: 0.55, ease: 'easeOut' as const },
    }),
}

function ScanVisual() {
    return (
        <div className="relative mx-auto w-full max-w-md" aria-hidden>
            {/* ambient glow */}
            <div className="absolute -inset-10 rounded-full bg-neon/10 blur-3xl" />

            {/* real POS screenshot in phone frame */}
            <motion.div
                initial={{ opacity: 0, rotate: -3, y: 30 }}
                animate={{ opacity: 1, rotate: -1.5, y: 0 }}
                transition={{ duration: 0.7, ease: 'easeOut' }}
            >
                <PhoneScreenshot
                    src="/screenshots/pos-scan.png"
                    alt="StashTab show-floor checkout — scan and sell screen"
                    className="w-[264px] sm:w-[288px]"
                />
            </motion.div>

            {/* floating readout chip — SKU locked */}
            <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.5, duration: 0.5 }}
                className="absolute -left-4 top-10 animate-float-slow sm:-left-10"
            >
                <div className="glass-panel flex items-center gap-2 rounded-md border border-neon/30 px-3 py-2 shadow-lg shadow-black/50">
                    <ScanBarcode className="size-4 text-neon" />
                    <div>
                        <p className="font-mono text-xs uppercase tracking-widest text-steel">SKU locked</p>
                        <p className="font-mono text-xs font-semibold text-foreground">CS-0001 · Charizard ex</p>
                    </div>
                </div>
            </motion.div>

            {/* floating readout chip — cart total */}
            <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.75, duration: 0.5 }}
                className="absolute -right-2 bottom-16 animate-float-slower sm:-right-8"
            >
                <div className="glass-panel rounded-md border border-border px-3 py-2 shadow-xl shadow-black/60">
                    <p className="font-mono text-xs uppercase tracking-widest text-steel">Cart total</p>
                    <p className="font-mono text-sm font-bold text-emerald-400">$611.99 · 6 cards</p>
                </div>
            </motion.div>
        </div>
    )
}

const marqueeItems = [
    'OPEN A TAB',
    'MANAGE YOUR STASH',
    'INSTANT SCANS',
    'SEAMLESS SALES',
    'LIVE POS',
    'ZERO OVERSELLS',
]

export default function HeroSection() {
    return (
        <main>
                <section className="relative overflow-hidden">
                    {/* obsidian + dot-grid backdrop */}
                    <div className="dot-grid mask-fade-b absolute inset-0" aria-hidden />
                    <div
                        aria-hidden
                        className="absolute inset-x-0 top-0 h-[520px]"
                        style={{
                            background:
                                'radial-gradient(ellipse 60% 50% at 70% 0%, rgba(139,92,246,0.1), transparent 70%), radial-gradient(ellipse 40% 40% at 15% 10%, rgba(168,85,247,0.06), transparent 70%)',
                        }}
                    />

                    <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-16 px-6 pb-24 pt-32 md:pt-40 lg:grid-cols-[1.1fr_0.9fr] lg:pb-32">
                        {/* Copy block */}
                        <div>
                            <motion.div variants={fadeUp} initial="hidden" animate="show" custom={0}>
                                <span className="inline-flex items-center gap-2 rounded-md border border-neon/30 bg-neon/5 px-3 py-1 font-mono text-xs uppercase tracking-[0.2em] text-neon">
                                    <Zap className="size-3.5" />
                                    Lightspeed TCG POS
                                </span>
                            </motion.div>

                            <motion.h1
                                variants={fadeUp}
                                initial="hidden"
                                animate="show"
                                custom={1}
                                className="mt-6 font-display text-5xl font-bold leading-[1.02] tracking-tight text-foreground sm:text-6xl lg:text-7xl"
                            >
                                Keep Tabs on
                                <br />
                                <span className="text-glow-accent text-neon">Your Inventory.</span>
                            </motion.h1>

                            <motion.p
                                variants={fadeUp}
                                initial="hidden"
                                animate="show"
                                custom={2}
                                className="mt-6 max-w-xl text-lg leading-relaxed text-steel"
                            >
                                The all in one TCG inventory management and POS app. Run
                                sales and manage your stash seamlessly.
                            </motion.p>

                            <motion.div
                                variants={fadeUp}
                                initial="hidden"
                                animate="show"
                                custom={3}
                                className="mt-9 flex flex-wrap items-center gap-4"
                            >
                                <SignUpButton mode="modal">
                                    <Button
                                        size="lg"
                                        className="animate-pulse-glow h-13 gap-2 rounded-md bg-neon px-8 font-display text-base font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_36px_rgba(139,92,246,0.6)]"
                                    >
                                        Open Your Tab
                                        <ArrowRight className="size-4" />
                                    </Button>
                                </SignUpButton>
                                <Button
                                    size="lg"
                                    variant="outline"
                                    onClick={scrollToDemo}
                                    className="h-13 border-border bg-gunmetal/60 font-display text-base text-foreground transition-all duration-200 hover:border-neon/50 hover:text-neon hover:shadow-[0_0_18px_rgba(139,92,246,0.2)]"
                                >
                                    Launch Live POS
                                </Button>
                            </motion.div>

                            {/* Trust signals */}
                            <motion.div
                                variants={fadeUp}
                                initial="hidden"
                                animate="show"
                                custom={4}
                                className="mt-10 flex flex-wrap items-center gap-3"
                            >
                                <span className="font-mono text-xs uppercase tracking-[0.18em] text-steel">
                                    Supports
                                </span>
                                <span className="flex items-center gap-2 rounded-md border border-yellow-300/40 bg-yellow-300/5 px-3 py-1.5 text-sm font-semibold text-yellow-300">
                                    <span className="size-2 rounded-full bg-yellow-300/80" />
                                    Pokémon TCG
                                </span>
                                <span className="flex items-center gap-2 rounded-md border border-red-400/40 bg-red-400/5 px-3 py-1.5 text-sm font-semibold text-red-400">
                                    <span className="size-2 rounded-full bg-red-400/80" />
                                    One Piece TCG
                                </span>
                                <span className="flex items-center gap-2 rounded-md border border-emerald-400/40 bg-emerald-400/5 px-3 py-1.5 text-sm font-semibold text-emerald-400">
                                    <span className="size-2 rounded-full bg-emerald-400/80" />
                                    MTG
                                </span>
                                <span className="flex items-center gap-2 rounded-md border border-sky-400/40 bg-sky-400/5 px-3 py-1.5 text-sm font-semibold text-sky-400">
                                    <span className="size-2 rounded-full bg-sky-400/80" />
                                    Lorcana
                                </span>
                            </motion.div>
                        </div>

                        {/* Scan visual */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.94 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.25, duration: 0.7, ease: 'easeOut' }}
                            className="hidden pb-10 sm:block"
                        >
                            <ScanVisual />
                        </motion.div>
                    </div>

                    {/* stats ticker strip */}
                    <div className="relative z-10 bg-gunmetal/40">
                        <div className="mask-fade-edges overflow-hidden py-3.5">
                            <div className="animate-marquee flex w-max whitespace-nowrap">
                                {[...Array(2)].map((_, dup) => (
                                    <div key={dup} className="flex items-center">
                                        {marqueeItems.map((item) => (
                                            <span
                                                key={`${dup}-${item}`}
                                                className="flex items-center font-mono text-xs tracking-[0.22em] text-steel"
                                            >
                                                {item}
                                                <span className="mx-6 text-neon">·</span>
                                            </span>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </section>
            </main>
    )
}
