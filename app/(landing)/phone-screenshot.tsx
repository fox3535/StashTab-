import { cn } from '@/lib/utils'

/**
 * Phone frame that wraps a real app screenshot.
 *
 * Unlike the stylized `PhoneMock` (which paints a fake header bar + mock UI),
 * this renders an actual screenshot — the image already contains the app's own
 * chrome, so we only add the bezel, dynamic-island pill, and rounded screen.
 */
export function PhoneScreenshot({
    src,
    alt,
    className,
}: {
    src: string
    alt: string
    className?: string
}) {
    return (
        <div
            className={cn(
                'relative mx-auto w-[264px] rounded-[2rem] border border-border bg-obsidian p-2 shadow-2xl shadow-black/70',
                className
            )}
        >
            {/* speaker / dynamic island */}
            <div className="absolute left-1/2 top-2 z-10 h-1.5 w-16 -translate-x-1/2 rounded-full bg-surface" />
            <div className="overflow-hidden rounded-[1.55rem] border border-border bg-gunmetal">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt={alt} className="block h-auto w-full" />
            </div>
        </div>
    )
}
