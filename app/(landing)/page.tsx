import ScrollVideoHero from "./scroll-video-hero";
import { HeroHeader } from "./header";
import HeroSection from "./hero-section";
import Workflow from "./workflow";
import FeatureGrid from "./feature-grid";
import PosPipeline from "./pos-pipeline";
import ProfitStagnant from "./profit-stagnant";
import InfraStrip from "./infra-strip";
import ComparisonMatrix from "./comparison-matrix";
import CallToAction, { StickyCtaBar } from "./call-to-action";
import Faq from "./faq";
import Footer from "./footer";
import CustomClerkPricing from "@/components/custom-clerk-pricing";

export default function Home() {
  return (
    <div className="bg-obsidian">
      {/* 1. Cinematic scroll-video hero (no chrome overlays) */}
      <ScrollVideoHero />

      {/* Boundary sentinel — the header reveals once this point is reached */}
      <div id="after-cinematic" aria-hidden className="h-px" />

      {/* Site header — hidden during the cinematic hero, appears after it */}
      <HeroHeader />

      {/* 2. Classic hero — headline, live UI phone screenshot, CTAs + marquee */}
      <HeroSection />

      {/* 3. From intake to checkout workflow */}
      <Workflow />

      {/* 4. Inventory intake and persistent identification */}
      <FeatureGrid />

      {/* 5–6. Barcode POS, mobile checkout, trade acquisition, weighted cost */}
      <PosPipeline />

      {/* 7. Profit visibility and stagnant inventory management */}
      <ProfitStagnant />

      {/* 8. Infrastructure and multi-TCG support */}
      <InfraStrip />

      {/* 9. Comparison section */}
      <ComparisonMatrix />

      {/* 10. Pricing / early access */}
      <section id="pricing" className="relative bg-gunmetal/30 py-20 md:py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto mb-14 max-w-2xl space-y-4 text-center">
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
              Early access
            </p>
            <h2 className="font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              Free on the floor. Pro in the back office.
            </h2>
            <p className="text-lg leading-relaxed text-steel">
              StashTab Free includes mobile POS for selling anywhere. Pro unlocks
              intake, Collectr reconciliation, Shopify sync, pricing engine, and
              team seats. Built for card stores, convention vendors, and
              high-volume dealers.
            </p>
          </div>
          <CustomClerkPricing />
        </div>
      </section>

      {/* 11. FAQ */}
      <Faq />

      {/* 12. Final conversion */}
      <CallToAction />
      <Footer />
      <StickyCtaBar />
    </div>
  );
}
