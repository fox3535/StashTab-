"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ArrowLeftRight,
  BadgeDollarSign,
  BarChart3,
  ExternalLink,
  LayoutDashboard,
  Layers,
  MoreHorizontal,
  Package,
  PackageSearch,
  PlusCircle,
  Receipt,
  Search,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sticker,
  Store,
  Upload,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { StashTabMark } from "@/components/logo";
import { SignOutButton } from "@/components/vendor/sign-out-button";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";

type NavItem = {
  href?: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  locked?: boolean;
};

const showFloorNav: NavItem[] = [
  { href: "/pos/find", label: "Find", icon: Search },
  { label: "Sell", icon: ShoppingCart, locked: true },
  { href: "/pos/pulls", label: "Pulls", icon: PackageSearch, locked: true },
  { href: "/pos/stats", label: "Stats", icon: BarChart3, locked: true },
  { href: "/pos/more", label: "More", icon: MoreHorizontal },
];

const backOfficeNav: NavItem[] = [
  { href: "/admin/inventory", label: "Inventory", icon: Package },
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/sales", label: "Sales History", icon: Receipt },
  { href: "/admin/reports", label: "Recent Trades", icon: ArrowLeftRight },
  { href: "/admin/price-updates", label: "Price Updates", icon: BadgeDollarSign },
  { href: "/admin/reconciliation", label: "Inventory Integrity", icon: ShieldCheck },
  { href: "/admin/intake", label: "Intake", icon: PlusCircle, locked: true },
  { href: "/admin/staging", label: "Staging", icon: Layers, locked: true },
  { href: "/admin/resticker", label: "Resticker", icon: Sticker, locked: true },
  { href: "/admin/paperweight", label: "Paperweight", icon: PackageSearch, locked: true },
];

const operationsNav: NavItem[] = [
  { href: "/admin/shopify/sync", label: "Shopify Sync", icon: Store, locked: true },
  { href: "/admin/shopify/review", label: "Shopify Review", icon: Store, locked: true },
  { href: "/admin/import", label: "CSV Import", icon: Upload, locked: true },
  { href: "/admin/settings", label: "Settings", icon: Settings, locked: true },
];

function isNavActive(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({
  label,
  items,
  onLocked,
}: {
  label: string;
  items: NavItem[];
  onLocked: (name: string) => void;
}) {
  const pathname = usePathname();

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="font-mono text-[10px] uppercase tracking-[0.22em] text-steel/70">
        {label}
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map(({ href, label: itemLabel, icon: Icon, exact, locked }) => (
            <SidebarMenuItem key={itemLabel}>
              {locked ? (
                <SidebarMenuButton
                  tooltip={`${itemLabel} is not ready`}
                  className="border-l-2 border-l-transparent text-steel/70"
                  onClick={() => onLocked(itemLabel)}
                  aria-disabled="true"
                >
                  <Icon />
                  <span>{itemLabel}</span>
                  <span className="ml-auto font-mono text-[9px] uppercase tracking-wider">
                    Not ready
                  </span>
                </SidebarMenuButton>
              ) : (
                <SidebarMenuButton
                  asChild
                  isActive={href ? isNavActive(pathname, href, exact) : false}
                  tooltip={itemLabel}
                  className="border-l-2 border-l-transparent transition-all duration-200 data-[active=true]:border-l-neon data-[active=true]:bg-neon/10 data-[active=true]:text-neon hover:border-l-neon/40 hover:text-foreground"
                >
                  <Link href={href || "/admin/inventory"}>
                    <Icon />
                    <span>{itemLabel}</span>
                  </Link>
                </SidebarMenuButton>
              )}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

export function ProductSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const [lockedFeature, setLockedFeature] = useState<string | null>(null);

  return (
    <Sidebar
      collapsible="icon"
      className="overflow-x-hidden border-r border-border bg-obsidian"
      {...props}
    >
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/admin/inventory">
                <StashTabMark />
                <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-display font-bold text-foreground">
                    Stash<span className="text-neon">Tab</span>
                  </span>
                  <span className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-steel/70">
                    Vendor shell
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="overflow-x-hidden">
        <NavGroup label="Show Floor" items={showFloorNav} onLocked={setLockedFeature} />
        <SidebarSeparator className="bg-border" />
        <NavGroup label="Back Office" items={backOfficeNav} onLocked={setLockedFeature} />
        <SidebarSeparator className="bg-border" />
        <NavGroup label="Operations" items={operationsNav} onLocked={setLockedFeature} />
        {lockedFeature ? (
          <div className="px-2">
            <FeatureNotReady
              title={`${lockedFeature} is not ready`}
              detail="This action is deferred. It will not sell, sync, or write inventory."
            />
          </div>
        ) : null}
      </SidebarContent>

      <SidebarFooter className="overflow-x-hidden border-t border-border">
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="px-2 py-1 md:hidden">
              <SignOutButton />
            </div>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Marketing site">
              <Link href="/">
                <ExternalLink className="shrink-0" />
                <span className="truncate font-mono text-xs text-steel">stashtab.app</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
