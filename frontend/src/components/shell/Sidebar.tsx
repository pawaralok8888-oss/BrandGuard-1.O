import { NavLink } from "react-router-dom";
import { Activity, BellRing, BookOpen, CheckSquare, ClipboardList, FileText, PackageCheck, Send, Settings, ShieldCheck, X } from "lucide-react";
import type { UserRole } from "@/types";
import { cn } from "@/lib/utils";

type SidebarProps = {
  role: UserRole;
  mobileOpen: boolean;
  onClose: () => void;
  alertCount?: number;
};

const navigation = [
  { label: "Content", to: "/content", icon: FileText, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
  { label: "Review Queue", to: "/review-queue", icon: CheckSquare, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
  { label: "Brand Guidelines", to: "/guidelines", icon: BookOpen, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
  { label: "Products and Facts", to: "/facts", icon: PackageCheck, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
  { label: "Alerts", to: "/alerts", icon: BellRing, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
  { label: "Analytics", to: "/analytics", icon: Activity, roles: ["manager", "reviewer", "admin"] as UserRole[] },
  { label: "Brand Rules", to: "/brand-rules", icon: ShieldCheck, roles: ["manager", "admin"] as UserRole[] },
  { label: "Brand Intake", to: "/intake", icon: ClipboardList, roles: ["manager", "admin"] as UserRole[] },
  { label: "Notifications", to: "/notifications", icon: Send, roles: ["manager", "admin"] as UserRole[] },
  { label: "Settings", to: "/settings", icon: Settings, roles: ["creator", "manager", "reviewer", "admin"] as UserRole[] },
];

export function Sidebar({ role, mobileOpen, onClose, alertCount }: SidebarProps) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-navy/40 transition md:hidden",
          mobileOpen ? "visible opacity-100" : "invisible opacity-0"
        )}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={cn(
          "fixed bottom-0 left-0 top-14 z-50 flex w-[220px] flex-col border-r border-[#E3E8F2] bg-white transition-transform duration-200 md:sticky md:top-14 md:z-10 md:h-[calc(100vh-56px)] md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Main navigation"
      >
        <div className="flex h-12 items-center justify-between border-b border-slate-100 px-4 md:hidden">
          <span className="text-xs font-semibold text-slate-500">Navigation</span>
          <button
            onClick={onClose}
            className="focus-ring rounded-md p-1.5 text-slate-500 hover:bg-slate-100"
            aria-label="Close navigation"
          >
            <X size={16} />
          </button>
        </div>
        <nav className="space-y-1 px-2 py-4" aria-label="Workspace">
          {navigation
            .filter((item) => item.roles.includes(role))
            .map((item) => {
              const Icon = item.icon;
              const badge =
                item.to === "/alerts" && alertCount && alertCount > 0
                  ? String(alertCount)
                  : undefined;

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex h-10 items-center gap-3 rounded-md border-l-[3px] px-3 text-[13px] font-medium transition-colors",
                      isActive
                        ? "border-l-[#2F5BEA] bg-[#EAF1FF] text-[#2F5BEA]"
                        : "border-l-transparent text-[#52627B] hover:bg-[#F6F8FC] hover:text-[#14213D]"
                    )
                  }
                >
                  <Icon size={17} strokeWidth={1.9} aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  {badge && (
                    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-slate-100 px-1 text-[10px] font-semibold text-slate-600 group-[.active]:bg-blue-100">
                      {badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
        </nav>
        <div className="mt-auto border-t border-slate-100 p-3">
          <div className="inline-flex h-6 items-center gap-1.5 rounded-full border border-[#DCE6F6] bg-[#F7FAFF] px-2.5 text-[11px] font-medium text-[#62718A]">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Connected to Database
          </div>
        </div>
      </aside>
    </>
  );
}