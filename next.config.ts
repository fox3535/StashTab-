import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.pokemontcg.io" },
      { protocol: "https", hostname: "placehold.co" },
      { protocol: "https", hostname: "cards.scryfall.io" },
      { protocol: "https", hostname: "optcgapi.com" },
    ],
  },
};

export default nextConfig;
