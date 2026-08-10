"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  ExternalLink,
  FileBarChart,
  LayoutDashboard,
  Layers,
  MoreHorizontal,
  Package,
  PackageSearch,
  PlusCircle,
  Search,
  Settings,
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

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
};

const showFloorNav: NavItem[] = [
  { href: "/pos", label: "Sell", icon: ShoppingCart, exact: true },
  { href: "/pos/find", label: "Find", icon: Search },
  { href: "/pos/pulls", label: "Pulls", icon: PackageSearch },
  { href: "/pos/stats", label: "Stats", icon: BarChart3 },
  { href: "/pos/more", label: "More", icon: MoreHorizontal },
];

const backOfficeNav: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/intake", label: "Intake", icon: PlusCircle },
  { href: "/admin/staging", label: "Staging", icon: Layers },
  { href: "/admin/inventory", label: "Inventory", icon: Package },
  { href: "/admin/resticker", label: "Resticker", icon: Sticker },
  { href: "/admin/paperweight", label: "Paperweight", icon: PackageSearch },
];

const operationsNav: NavItem[] = [
  { href: "/admin/shopify/sync", label: "Shopify Sync", icon: Store },
  { href: "/admin/shopify/review", label: "Shopify Review", icon: Store },
  { href: "/admin/import", label: "CSV Import", icon: Upload },
  { href: "/admin/reconciliation", label: "Reconciliation", icon: FileBarChart },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

function isNavActive(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  const pathname = usePathname();

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="font-mono text-[10px] uppercase tracking-[0.22em] text-steel/70">
        {label}
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map(({ href, label: itemLabel, icon: Icon, exact }) => (
            <SidebarMenuItem key={href}>
              <SidebarMenuButton
                asChild
                isActive={isNavActive(pathname, href, exact)}
                tooltip={itemLabel}
                className="border-l-2 border-l-transparent transition-all duration-200 data-[active=true]:border-l-neon data-[active=true]:bg-neon/10 data-[active=true]:text-neon data-[active=true]:[text-shadow:0_0_12px_rgba(139,92,246,0.45)] hover:border-l-neon/40 hover:text-foreground"
              >
                <Link href={href}>
                  <Icon />
                  <span>{itemLabel}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

export function ProductSidebar(props: React.ComponentProps<typeof Sidebar>) {
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
              <Link href="/pos">
                <StashTabMark />
                <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-display font-bold text-foreground">
                    Stash<span className="text-neon">Tab</span>
                  </span>
                  <span className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-steel/70">
                    Cockpit v6
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="overflow-x-hidden">
        <NavGroup label="Show Floor" items={showFloorNav} />
        <SidebarSeparator className="bg-border" />
        <NavGroup label="Back Office" items={backOfficeNav} />
        <SidebarSeparator className="bg-border" />
        <NavGroup label="Operations" items={operationsNav} />
      </SidebarContent>

      <SidebarFooter className="overflow-x-hidden border-t border-border">
        <SidebarMenu>
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
