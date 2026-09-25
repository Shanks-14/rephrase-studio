import { useState } from "react";
import { Sun, Moon, Monitor, User, LogOut, LogIn, Feather } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import AuthModal from "@/components/AuthModal";
import { toast } from "sonner";

export default function Navbar() {
  const { mode, cycle } = useTheme();
  const { user, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);
  const [authTab, setAuthTab] = useState("login");

  const ThemeIcon = mode === "dark" ? Moon : mode === "light" ? Sun : Monitor;

  const openAuth = (tab) => {
    setAuthTab(tab);
    setAuthOpen(true);
  };

  return (
    <>
      <header
        className="sticky top-0 z-40 border-b border-border glass"
        data-testid="app-navbar"
      >
        <div className="max-w-[1400px] mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3" data-testid="navbar-brand-logo">
            <div className="w-9 h-9 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
              <Feather className="w-5 h-5" strokeWidth={2.25} />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-xl font-semibold tracking-tight">VerbaHumanize</span>
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                Rephrase · Humanize · Verify
              </span>
            </div>
          </div>

          <nav className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={cycle}
              data-testid="navbar-theme-toggle"
              title={`Theme: ${mode}`}
              className="rounded-full"
            >
              <ThemeIcon className="w-4 h-4" />
            </Button>

            {user ? (
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="rounded-full gap-2 pl-2 pr-3"
                    data-testid="navbar-user-button"
                  >
                    <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-semibold">
                      {user.name?.[0]?.toUpperCase() || "U"}
                    </div>
                    <span className="max-w-[120px] truncate">{user.name}</span>
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-56 p-2">
                  <div className="px-2 py-2 mb-1 border-b border-border">
                    <div className="text-sm font-semibold truncate">{user.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                  </div>
                  <Button
                    variant="ghost"
                    className="w-full justify-start gap-2 text-destructive"
                    data-testid="navbar-logout-button"
                    onClick={async () => {
                      await logout();
                      toast.success("Signed out");
                    }}
                  >
                    <LogOut className="w-4 h-4" /> Sign out
                  </Button>
                </PopoverContent>
              </Popover>
            ) : (
              <>
                <Button
                  variant="ghost"
                  className="rounded-full gap-2"
                  onClick={() => openAuth("login")}
                  data-testid="navbar-login-button"
                >
                  <LogIn className="w-4 h-4" /> Sign in
                </Button>
                <Button
                  className="rounded-full gap-2"
                  onClick={() => openAuth("register")}
                  data-testid="navbar-signup-button"
                >
                  <User className="w-4 h-4" /> Get started
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <AuthModal open={authOpen} onOpenChange={setAuthOpen} defaultTab={authTab} />
    </>
  );
}
