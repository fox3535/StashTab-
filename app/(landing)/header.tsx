'use client'
import Link from 'next/link'
import { Loader2, Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StashTabMark } from '@/components/logo'
import React from 'react'
import { cn } from '@/lib/utils'

import {
    SignInButton,
    SignUpButton,
    SignedIn,
    SignedOut,
    UserButton,
    useAuth,
} from "@clerk/nextjs";

import { dark } from '@clerk/themes'

const menuItems = [
    { name: 'How It Works', href: '#workflow' },
    { name: 'Inventory', href: '#features' },
    { name: 'Sell Anywhere', href: '#pipeline' },
    { name: 'Compare', href: '#compare' },
    { name: 'Pricing', href: '#pricing' },
    { name: 'FAQ', href: '#faq' },
]

export { StashTabMark }

export const HeroHeader = () => {
    const [menuState, setMenuState] = React.useState(false)
    const [isScrolled, setIsScrolled] = React.useState(false)
    /** Header stays hidden while the cinematic video hero is on screen and
     *  reveals once the visitor scrolls past it into the main landing page. */
    const [pastHero, setPastHero] = React.useState(false)
    const { isLoaded } = useAuth()

    React.useEffect(() => {
        const sentinel = document.getElementById('after-cinematic')
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 24)
            if (sentinel) {
                // Reveal once the boundary right after the cinematic hero
                // has risen into (or above) the viewport.
                const threshold = sentinel.offsetTop - window.innerHeight * 0.9
                setPastHero(window.scrollY > threshold)
            } else {
                setPastHero(window.scrollY > 400)
            }
        }
        handleScroll()
        window.addEventListener('scroll', handleScroll, { passive: true })
        window.addEventListener('resize', handleScroll)
        return () => {
            window.removeEventListener('scroll', handleScroll)
            window.removeEventListener('resize', handleScroll)
        }
    }, [])

    return (
        <header>
            <nav
                data-state={menuState && 'active'}
                className={cn(
                    'fixed inset-x-0 top-0 z-40 px-3 transition-all duration-300 ease-out motion-reduce:transition-none',
                    pastHero
                        ? 'translate-y-0 opacity-100'
                        : 'pointer-events-none -translate-y-full opacity-0'
                )}
            >
                <div
                    className={cn(
                        'mx-auto mt-3 max-w-6xl rounded-lg border border-transparent px-5 transition-all duration-200 lg:px-6',
                        isScrolled &&
                            'glass-panel border-border shadow-lg shadow-black/40'
                    )}
                >
                    <div className="relative flex flex-wrap items-center justify-between gap-4 py-3">
                        <div className="flex w-full justify-between lg:w-auto">
                            <Link href="/" aria-label="StashTab home" className="flex items-center gap-3">
                                <StashTabMark className="size-10 text-base" />
                                <span className="font-display text-xl font-bold tracking-tight text-foreground">
                                    Stash<span className="text-neon">Tab</span>
                                </span>
                            </Link>

                            <button
                                onClick={() => setMenuState(!menuState)}
                                aria-label={menuState ? 'Close Menu' : 'Open Menu'}
                                className="relative z-20 -m-2.5 -mr-2 block cursor-pointer p-2.5 text-foreground lg:hidden"
                            >
                                <Menu className="in-data-[state=active]:rotate-180 in-data-[state=active]:scale-0 in-data-[state=active]:opacity-0 m-auto size-6 duration-200" />
                                <X className="in-data-[state=active]:rotate-0 in-data-[state=active]:scale-100 in-data-[state=active]:opacity-100 absolute inset-0 m-auto size-6 -rotate-180 scale-0 opacity-0 duration-200" />
                            </button>
                        </div>

                        <div className="absolute inset-0 m-auto hidden size-fit lg:block">
                            <ul className="flex gap-7 text-sm font-medium">
                                {menuItems.map((item, index) => (
                                    <li key={index}>
                                        <Link
                                            href={item.href}
                                            className="block text-steel transition-colors duration-200 hover:text-neon"
                                        >
                                            <span>{item.name}</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="glass-panel in-data-[state=active]:block mb-6 hidden w-full flex-wrap items-center justify-end space-y-6 rounded-lg border border-border p-6 lg:m-0 lg:flex lg:w-fit lg:gap-3 lg:space-y-0 lg:border-transparent lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
                            <div className="lg:hidden">
                                <ul className="space-y-4 text-base">
                                    {menuItems.map((item, index) => (
                                        <li key={index}>
                                            <Link
                                                href={item.href}
                                                onClick={() => setMenuState(false)}
                                                className="block text-steel transition-colors duration-200 hover:text-neon"
                                            >
                                                <span>{item.name}</span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="flex w-full flex-col gap-3 sm:flex-row sm:space-y-0 md:w-fit">
                                {!isLoaded ? (
                                    <div className="flex items-center justify-center">
                                        <Loader2 className="size-8 animate-spin p-2 text-neon" />
                                    </div>
                                ) : (
                                    <>
                                        <SignedIn>
                                            <Button
                                                asChild
                                                size="sm"
                                                className="border border-neon/40 bg-neon/10 text-neon hover:bg-neon/20 hover:shadow-[0_0_18px_rgba(139,92,246,0.35)]"
                                            >
                                                <Link href="/pos">
                                                    <span>Open POS</span>
                                                </Link>
                                            </Button>
                                            <Button asChild size="sm" variant="outline">
                                                <Link href="/admin/dashboard">
                                                    <span>Admin</span>
                                                </Link>
                                            </Button>
                                            <UserButton appearance={{ baseTheme: dark }} />
                                        </SignedIn>

                                        <SignedOut>
                                            <SignInButton mode="modal">
                                                <Button variant="ghost" size="sm" className="text-steel hover:text-foreground">
                                                    Login
                                                </Button>
                                            </SignInButton>
                                            <SignUpButton mode="modal">
                                                <Button
                                                    size="sm"
                                                    className="bg-neon font-semibold text-white hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
                                                >
                                                    Open Your Tab
                                                </Button>
                                            </SignUpButton>
                                        </SignedOut>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </nav>
        </header>
    )
}
