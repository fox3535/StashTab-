import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

import { ClerkProvider } from '@clerk/nextjs'
import ConvexClientProvider from '@/components/ConvexClientProvider'

/** Body / UI text */
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

/** Headings / display */
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

/** Data: SKUs, prices, inventory counts */
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "StashTab | Keep Tabs on Your Inventory.",
  description:
    "The all in one TCG inventory management and POS app. Run sales and manage your stash seamlessly.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "StashTab",
  },
  icons: {
    icon: "/icon-192.png",
    apple: "/apple-touch-icon.png",
  },
};

export const dynamic = "force-dynamic";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const appTree = clerkPublishableKey ? (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <ConvexClientProvider>{children}</ConvexClientProvider>
    </ClerkProvider>
  ) : (
    <ConvexClientProvider>{children}</ConvexClientProvider>
  );

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} font-sans antialiased overscroll-none bg-obsidian text-foreground`}
        suppressHydrationWarning
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          {appTree}
        </ThemeProvider>
      </body>
    </html>
  );
}
