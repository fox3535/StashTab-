'use client'

import React from 'react'
import { motion } from 'framer-motion'

const faqs = [
  {
    q: 'What games does StashTab support?',
    a: 'StashTab uses a multi-TCG architecture with a universal schema. Pokémon and One Piece are fully supported today, with MTG and Lorcana compatibility built into the data model. New games can be added without restructuring your existing inventory.',
  },
  {
    q: 'Do I need special hardware to run the POS?',
    a: 'No. The POS runs in any mobile or desktop browser. A standard USB or Bluetooth barcode scanner is all you need for scan-to-sell checkout. No app-store installs, no paired terminals.',
  },
  {
    q: 'How does the Collectr import work?',
    a: 'Connect your Collectr portfolio and StashTab synchronizes your holdings locally. Every imported card receives a persistent SKU and barcode, so nothing needs to be re-keyed or re-stickered when it enters your system.',
  },
  {
    q: 'What happens when I acquire cards through a trade?',
    a: 'Create a trade bucket, add cards, and StashTab distributes the total trade cost across each card by market-value weight. Your cost basis is tracked to the cent automatically — no spreadsheet math required.',
  },
  {
    q: 'What is the Paperweight Rule?',
    a: 'Any inventory item sitting unsold for 60+ days is automatically flagged as stagnant. StashTab surfaces these items so you can discount, bundle, or move them before they become dead capital.',
  },
  {
    q: 'Is StashTab free?',
    a: 'StashTab Free includes the mobile POS for selling on the floor. Pro unlocks intake management, Collectr reconciliation, Shopify sync, the pricing engine, and team seats. Early-access pricing is available now.',
  },
]

export default function Faq() {
  return (
    <section id="faq" className="relative py-20 md:py-24">
      <div className="mx-auto max-w-3xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.55 }}
          className="text-center"
        >
          <p className="font-mono text-xs uppercase tracking-[0.28em] text-neon">
            Questions
          </p>
          <h2 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Straight answers.
          </h2>
        </motion.div>

        <div className="mt-12 space-y-0 divide-y divide-border">
          {faqs.map((faq, i) => (
            <motion.details
              key={faq.q}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="group py-6"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                <h3 className="font-display text-lg font-semibold text-foreground transition-colors group-hover:text-neon">
                  {faq.q}
                </h3>
                <span
                  className="flex size-7 shrink-0 items-center justify-center rounded-full border border-border text-steel transition-all duration-200 group-open:rotate-45 group-open:border-neon group-open:text-neon"
                  aria-hidden
                >
                  +
                </span>
              </summary>
              <p className="mt-3 text-base leading-relaxed text-steel">{faq.a}</p>
            </motion.details>
          ))}
        </div>
      </div>
    </section>
  )
}
