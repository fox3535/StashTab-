import Link from 'next/link'

const productLinks = [
    { title: 'How It Works', href: '#workflow' },
    { title: 'Inventory', href: '#features' },
    { title: 'Sell Anywhere', href: '#pipeline' },
    { title: 'Compare', href: '#compare' },
    { title: 'Pricing', href: '#pricing' },
    { title: 'FAQ', href: '#faq' },
]

const appLinks = [
    { title: 'Open POS', href: '/pos' },
    { title: 'Admin console', href: '/admin/dashboard' },
    { title: 'Sign up', href: '/sign-up' },
]

export default function FooterSection() {
    return (
        <footer className="bg-gunmetal/30 pb-28 pt-16 md:pt-20">
            <div className="mx-auto max-w-6xl px-6">
                <div className="flex flex-col gap-12 md:flex-row md:items-start md:justify-between">
                    <div className="max-w-sm">
                        <Link href="/" aria-label="StashTab home" className="inline-block">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src="/Black%20BG%20Logo%20+%20Brand.png"
                                alt="StashTab"
                                className="h-20 w-auto object-contain"
                            />
                        </Link>
                        <p className="mt-4 text-[15px] leading-relaxed text-steel">
                            The relentless inventory and POS engine for TCG vendors. Built for show
                            floors, card shops, and everything between.
                        </p>
                        <div className="mt-5 flex gap-2">
                            <span className="rounded border border-holo-gold/30 bg-holo-gold/5 px-2 py-1 font-mono text-[11px] tracking-wider text-holo-gold/90">
                                POKÉMON
                            </span>
                            <span className="rounded border border-holo-pink/30 bg-holo-pink/5 px-2 py-1 font-mono text-[11px] tracking-wider text-holo-pink/90">
                                ONE PIECE
                            </span>
                        </div>
                    </div>

                    <div className="flex gap-16">
                        <div>
                            <p className="font-mono text-xs uppercase tracking-[0.22em] text-steel/80">
                                Product
                            </p>
                            <ul className="mt-4 space-y-2.5 text-sm">
                                {productLinks.map((link) => (
                                    <li key={link.title}>
                                        <Link
                                            href={link.href}
                                            className="text-steel transition-colors duration-200 hover:text-neon"
                                        >
                                            {link.title}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div>
                            <p className="font-mono text-xs uppercase tracking-[0.22em] text-steel/80">
                                App
                            </p>
                            <ul className="mt-4 space-y-2.5 text-sm">
                                {appLinks.map((link) => (
                                    <li key={link.title}>
                                        <Link
                                            href={link.href}
                                            className="text-steel transition-colors duration-200 hover:text-neon"
                                        >
                                            {link.title}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>

                <div className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-border pt-6 sm:flex-row">
                    <span className="text-xs text-steel/70">
                        © {new Date().getFullYear()} StashTab. Built for TCG show floors and card shops.
                    </span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-steel/60">
                        v6.0 · cockpit build
                    </span>
                </div>
            </div>
        </footer>
    )
}
