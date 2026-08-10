'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { GlobeLock, HardDriveDownload, Layers3 } from 'lucide-react'

const infra = [
    {
        icon: GlobeLock,
        tag: 'CLOUDFLARE TUNNEL · 0 EXPOSED PORTS',
        title: 'Secure access from anywhere',
        body: 'Connect to your vault over a Cloudflare Tunnel with TLS 1.3. No open ports, no port maps — the booth stays open while the vault stays sealed.',
    },
    {
        icon: HardDriveDownload,
        tag: 'LOCAL IMAGE REPOSITORY · OFFLINE-FIRST',
        title: 'Instant card images, even offline',
        body: 'Artwork is cached locally for sub-millisecond retrieval, so scans stay fast for Pokémon and One Piece even when the venue Wi-Fi dies.',
    },
    {
        icon: Layers3,
        tag: 'MULTI-TCG ARCHITECTURE',
        title: 'Works across your games',
        body: 'A universal schema handles game-specific imports cleanly. Pokémon today, One Piece tomorrow, anything next.',
    },
]

export default function InfraStrip() {
    return (
        <section className="relative py-16 md:py-20">
            <div className="mx-auto max-w-6xl px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55 }}
                    className="max-w-2xl"
                >
                    <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
                        04 · Built to stay open
                    </p>
                    <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                        Always on. Never exposed.
                    </h2>
                    <p className="mt-4 text-lg leading-relaxed text-steel">
                        Secure access from anywhere, instant card images offline, and a
                        catalog ready for every game you run.
                    </p>
                </motion.div>

                <div className="mt-14 grid gap-x-10 gap-y-10 md:grid-cols-3">
                    {infra.map((item, i) => (
                        <motion.div
                            key={item.title}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: '-60px' }}
                            transition={{ duration: 0.5, delay: i * 0.08 }}
                        >
                            <div className="flex items-center gap-3">
                                <item.icon className="size-5 text-neon" />
                                <h3 className="font-display text-lg font-semibold text-foreground">
                                    {item.title}
                                </h3>
                            </div>
                            <p className="mt-3 text-[15px] leading-relaxed text-steel">{item.body}</p>
                            <p className="mt-4 font-mono text-[11px] tracking-[0.18em] text-steel/70">
                                {item.tag}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
