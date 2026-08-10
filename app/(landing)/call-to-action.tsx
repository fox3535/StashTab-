'use client'
import React from 'react'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SignUpButton } from '@clerk/nextjs'

/** Sticky bottom CTA bar — reveals only after the first product-proof section,
 *  hidden during the cinematic hero and on small mobile so it never covers content. */
export function StickyCtaBar() {
    const [visible, setVisible] = React.useState(false)

    React.useEffect(() => {
        const target = document.getElementById('product')
        const onScroll = () => {
            // Reveal only once the product-reveal (first product proof) has scrolled past
            setVisible(target ? target.getBoundingClientRect().bottom < 0 : window.scrollY > 1200)
        }
        onScroll()
        window.addEventListener('scroll', onScroll, { passive: true })
        return () => window.removeEventListener('scroll', onScroll)
    }, [])

    return (
        <div
            className={
                visible
                    ? 'fixed inset-x-0 bottom-0 z-40 hidden translate-y-0 transition-transform duration-300 ease-out motion-reduce:transition-none sm:block'
                    : 'pointer-events-none fixed inset-x-0 bottom-0 z-40 hidden translate-y-full transition-transform duration-300 ease-out motion-reduce:transition-none sm:block'
            }
        >
            <div className="glass-panel border-t border-border">
                <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
                    <p className="font-display text-sm font-semibold text-foreground">
                        Stop losing time. <span className="text-neon">Start moving product.</span>
                    </p>
                    <SignUpButton mode="modal">
                        <Button
                            size="sm"
                            className="bg-neon font-display font-bold text-white hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.5)]"
                        >
                            Open Your Tab
                            <ArrowRight className="size-3.5" />
                        </Button>
                    </SignUpButton>
                </div>
            </div>
        </div>
    )
}

export default function CallToAction() {
    return (
        <section className="relative overflow-hidden py-24 md:py-28">
            <div className="dot-grid absolute inset-0 opacity-50" aria-hidden />
            <div
                aria-hidden
                className="absolute inset-0"
                style={{
                    background:
                        'radial-gradient(ellipse 55% 60% at 50% 100%, rgba(139,92,246,0.12), transparent 70%), radial-gradient(ellipse 30% 40% at 20% 80%, rgba(168,85,247,0.07), transparent 70%), radial-gradient(ellipse 30% 40% at 80% 80%, rgba(196,181,253,0.06), transparent 70%)',
                }}
            />

            <div className="relative mx-auto max-w-4xl px-6 text-center">
                <motion.p
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.5 }}
                    className="font-mono text-xs uppercase tracking-[0.3em] text-neon"
                >
                    The floor is waiting
                </motion.p>
                <motion.h2
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55, delay: 0.08 }}
                    className="mt-5 font-display text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-6xl"
                >
                    Stop losing time.
                    <br />
                    <span className="holo-text">Start moving product.</span>
                </motion.h2>
                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55, delay: 0.16 }}
                    className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-steel"
                >
                    Your next show could run on a scanner, a phone, and a vault that never forgets.
                    Set up in minutes — sell the same day.
                </motion.p>
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: '-80px' }}
                    transition={{ duration: 0.55, delay: 0.24 }}
                    className="mt-10 flex flex-wrap items-center justify-center gap-4"
                >
                    <SignUpButton mode="modal">
                        <Button
                            size="lg"
                            className="animate-pulse-glow h-13 gap-2 rounded-md bg-neon px-9 font-display text-base font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_40px_rgba(139,92,246,0.65)]"
                        >
                            Open Your Tab
                            <ArrowRight className="size-4" />
                        </Button>
                    </SignUpButton>
                    <Button
                        asChild
                        size="lg"
                        variant="outline"
                        className="h-13 border-border bg-gunmetal/60 font-display text-base text-foreground transition-all duration-200 hover:border-neon/50 hover:text-neon hover:shadow-[0_0_18px_rgba(139,92,246,0.2)]"
                    >
                        <a href="#features">See the arsenal</a>
                    </Button>
                </motion.div>
            </div>
        </section>
    )
}
