'use client'

import React, { useRef, useEffect, useState, useCallback } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Button } from '@/components/ui/button'
import { SignUpButton } from '@clerk/nextjs'
import { ArrowRight, ChevronDown } from 'lucide-react'

gsap.registerPlugin(ScrollTrigger)

/* ─── Tunable constants ─────────────────────────────────────────────── */

/** Damping factor per second — higher = snappier, lower = smoother.
    Tuned higher so the playhead tracks scroll with minimal perceived lag. */
const DAMPING_PER_SECOND = 9

/** Minimum time delta (seconds) before we issue a seek */
const SEEK_THRESHOLD = 0.03

/** Hero scroll height on desktop (vh) */
const HERO_HEIGHT_DESKTOP = 240

/** Hero scroll height on mobile (vh) */
const HERO_HEIGHT_MOBILE = 170

/** Narrative overlay messages with their progress ranges [start, end] */
const NARRATIVE_MESSAGES = [
  { text: 'Every card enters.', range: [0.05, 0.22] as const },
  { text: 'Every card stays identified.', range: [0.25, 0.42] as const },
  { text: 'Every sale stays connected.', range: [0.45, 0.62] as const },
  { text: 'Your inventory, under control.', range: [0.65, 0.80] as const },
]

/** Progress at which all overlays fade out before the phone push-in.
    The video's own end frame carries the final branding composition, so
    every HTML overlay is cleared before that moment. */
const OVERLAY_FADE_END = 0.84

/* ─── Component ─────────────────────────────────────────────────────── */

export default function ScrollVideoHero() {
  const sectionRef = useRef<HTMLElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const rafRef = useRef<number>(0)
  const targetTimeRef = useRef(0)
  const currentTimeRef = useRef(0)
  const isSeekingRef = useRef(false)
  const durationRef = useRef(0)
  const triggerRef = useRef<ScrollTrigger | null>(null)
  const lastFrameTimeRef = useRef(0)

  const [isReady, setIsReady] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [progress, setProgress] = useState(0)
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  /* Detect reduced motion preference */
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setPrefersReducedMotion(mq.matches)
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  /* Detect mobile viewport */
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    setIsMobile(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  /* Video metadata loaded */
  const handleLoadedMetadata = useCallback(() => {
    const video = videoRef.current
    if (!video || !video.duration || !isFinite(video.duration)) return
    durationRef.current = video.duration
    setIsReady(true)
  }, [])

  /* Video error fallback */
  const handleError = useCallback(() => {
    setHasError(true)
  }, [])

  /* Force the video to begin loading metadata and add a safety timeout
     so the loading state never gets stuck. */
  useEffect(() => {
    if (prefersReducedMotion || hasError) return
    const video = videoRef.current
    if (!video) return

    // Explicitly kick off loading (some browsers won't fetch metadata
    // from preload="auto" alone without a play/load call).
    video.muted = true // React doesn't always apply `muted` as a property
    video.load()

    // Safety net: if metadata still hasn't arrived, try to recover.
    const timeout = window.setTimeout(() => {
      if (video.duration && isFinite(video.duration)) {
        durationRef.current = video.duration
        setIsReady(true)
      } else if (video.readyState >= 1) {
        // HAVE_METADATA — duration should be available
        durationRef.current = video.duration
        setIsReady(true)
      }
    }, 4000)

    return () => window.clearTimeout(timeout)
  }, [prefersReducedMotion, hasError])

  /* Main GSAP + RAF engine */
  useEffect(() => {
    if (!isReady || prefersReducedMotion || hasError) return

    const video = videoRef.current
    const section = sectionRef.current
    if (!video || !section) return

    const duration = durationRef.current
    if (!duration) return

    // Initialize refs
    targetTimeRef.current = 0
    currentTimeRef.current = 0
    isSeekingRef.current = false
    lastFrameTimeRef.current = performance.now()

    // Prevent video from autoplaying
    video.pause()

    /* ScrollTrigger: map hero scroll progress → target video time */
    const trigger = ScrollTrigger.create({
      trigger: section,
      start: 'top top',
      end: `bottom bottom`,
      scrub: true,
      onUpdate: (self) => {
        const p = self.progress
        targetTimeRef.current = p * duration
        // Throttle React state updates for overlays
        setProgress(p)
      },
    })
    triggerRef.current = trigger

    /* RAF loop: ease internal playhead toward target with damping */
    const tick = (now: number) => {
      const dt = Math.min((now - lastFrameTimeRef.current) / 1000, 0.1)
      lastFrameTimeRef.current = now

      const target = targetTimeRef.current
      const current = currentTimeRef.current
      const diff = target - current

      // Frame-rate-independent exponential damping
      const alpha = 1 - Math.exp(-DAMPING_PER_SECOND * dt)
      const next = current + diff * alpha

      // Only seek if the delta exceeds threshold and we're not mid-seek
      if (Math.abs(next - current) > 0.0001) {
        currentTimeRef.current = next

        if (!isSeekingRef.current && Math.abs(next - video.currentTime) > SEEK_THRESHOLD) {
          isSeekingRef.current = true
          video.currentTime = next
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    // When the video finishes seeking, allow the next one
    const onSeeked = () => {
      isSeekingRef.current = false
    }
    video.addEventListener('seeked', onSeeked)

    rafRef.current = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(rafRef.current)
      video.removeEventListener('seeked', onSeeked)
      trigger.kill()
      triggerRef.current = null
    }
  }, [isReady, prefersReducedMotion, hasError])

  /* Cleanup on unmount (StrictMode safe) */
  useEffect(() => {
    return () => {
      cancelAnimationFrame(rafRef.current)
      if (triggerRef.current) {
        triggerRef.current.kill()
        triggerRef.current = null
      }
    }
  }, [])

  /* Determine active narrative message */
  const activeMessage = NARRATIVE_MESSAGES.find(
    (m) => progress >= m.range[0] && progress <= m.range[1]
  )

  /* Compute narrative opacity (fade in/out within range) */
  const narrativeOpacity = activeMessage
    ? (() => {
        const [start, end] = activeMessage.range
        const mid = (start + end) / 2
        const halfSpan = (end - start) / 2
        const dist = Math.abs(progress - mid) / halfSpan
        return Math.max(0, 1 - dist * 1.2)
      })()
    : 0

  /* All overlays fade out before the phone push-in. The video's final
     frame already contains the headline + CTA composition, so we never
     layer a duplicate HTML headline over it. */
  const overlayVisible = progress < OVERLAY_FADE_END
  const overlayOpacity = overlayVisible
    ? Math.min(1, (OVERLAY_FADE_END - progress) / 0.06)
    : 0

  const heroHeight = isMobile ? HERO_HEIGHT_MOBILE : HERO_HEIGHT_DESKTOP

  function scrollToWorkflow() {
    document.getElementById('workflow')?.scrollIntoView({ behavior: 'smooth' })
  }

  /* ─── Reduced motion / error fallback ─── */
  if (prefersReducedMotion || hasError) {
    return (
      <section
        ref={sectionRef}
        className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-obsidian px-6"
        aria-label="StashTab hero"
      >
        {/* Static branded background */}
        <div className="dot-grid absolute inset-0 opacity-40" aria-hidden />
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse 55% 50% at 50% 40%, rgba(139,92,246,0.12), transparent 70%)',
          }}
        />
        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            Own the Booth.{' '}
            <span className="text-glow-accent text-neon">Master the Inventory.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-steel">
            Import, organize, price and sell your trading-card inventory from one
            connected POS system.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <SignUpButton mode="modal">
              <Button
                size="lg"
                className="h-13 gap-2 rounded-md bg-neon px-8 font-display text-base font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_36px_rgba(139,92,246,0.6)]"
              >
                Get Early Access
                <ArrowRight className="size-4" />
              </Button>
            </SignUpButton>
            <Button
              size="lg"
              variant="outline"
              onClick={scrollToWorkflow}
              className="h-13 border-border bg-gunmetal/60 font-display text-base text-foreground transition-all duration-200 hover:border-neon/50 hover:text-neon"
            >
              See How It Works
            </Button>
          </div>
        </div>
      </section>
    )
  }

  /* ─── Cinematic scroll-scrubbed hero ─── */
  return (
    <section
      ref={sectionRef}
      className="relative"
      style={{ height: `${heroHeight}vh` }}
      aria-label="StashTab cinematic hero"
    >
      {/* Fixed video container — only fixed while hero is in view */}
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        {/* Loading state — branded with the StashTab logo */}
        {!isReady && !hasError && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-obsidian">
            <div className="dot-grid absolute inset-0 opacity-30" aria-hidden />
            <div className="relative flex flex-col items-center gap-5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/Black%20BG%20Logo%20+%20Brand.png"
                alt="StashTab"
                className="h-24 w-auto object-contain sm:h-28"
              />
              <div className="flex items-center gap-3">
                <div className="size-4 animate-spin rounded-full border-2 border-neon/30 border-t-neon" />
                <p className="font-mono text-xs uppercase tracking-[0.25em] text-steel">
                  Loading experience
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Native video element */}
        <video
          ref={videoRef}
          muted
          playsInline
          preload="auto"
          disablePictureInPicture
          onLoadedMetadata={handleLoadedMetadata}
          onCanPlay={handleLoadedMetadata}
          onError={handleError}
          className="absolute inset-0 h-full w-full object-cover"
          aria-hidden
        >
          <source src="/final-vid.mp4" type="video/mp4" />
        </video>

        {/* Dark scrim for text legibility */}
        <div
          className="absolute inset-0 bg-gradient-to-b from-obsidian/60 via-transparent to-obsidian/80"
          aria-hidden
        />

        {/* Narrative overlay messages */}
        <div
          className="absolute inset-0 z-10 flex items-center justify-start px-8 sm:px-16 lg:px-24"
          aria-hidden
          style={{ opacity: overlayOpacity }}
        >
          {activeMessage && (
            <p
              className="max-w-md font-display text-2xl font-semibold leading-snug text-white drop-shadow-[0_2px_12px_rgba(0,0,0,0.8)] sm:text-3xl lg:text-4xl"
              style={{ opacity: narrativeOpacity }}
            >
              {activeMessage.text}
            </p>
          )}
        </div>

        {/* Scroll indicator — fades out as user scrolls */}
        <div
          className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2"
          style={{ opacity: Math.max(0, 1 - progress * 8) }}
          aria-hidden
        >
          <div className="flex flex-col items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/60">
              Scroll
            </span>
            <ChevronDown className="size-4 animate-bounce text-white/60" />
          </div>
        </div>
      </div>
    </section>
  )
}
