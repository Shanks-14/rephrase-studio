import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export default function AuthModal({ open, onOpenChange, defaultTab = "login" }) {
  const { login, register } = useAuth();
  const [tab, setTab] = useState(defaultTab);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", name: "" });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (tab === "login") {
        await login(form.email, form.password);
        toast.success("Welcome back!");
      } else {
        await register(form.email, form.password, form.name);
        toast.success("Account created — you're in.");
      }
      onOpenChange(false);
      setForm({ email: "", password: "", name: "" });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="auth-modal">
        <DialogHeader>
          <DialogTitle className="text-2xl font-semibold tracking-tight">
            {tab === "login" ? "Welcome back" : "Create your account"}
          </DialogTitle>
          <DialogDescription>
            Unlock full-length rephrasing, AI checks & plagiarism scoring.
          </DialogDescription>
        </DialogHeader>
        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="grid grid-cols-2 w-full">
            <TabsTrigger value="login" data-testid="auth-tab-login">Sign in</TabsTrigger>
            <TabsTrigger value="register" data-testid="auth-tab-register">Register</TabsTrigger>
          </TabsList>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            {tab === "register" && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  data-testid="auth-input-name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Jane Doe"
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                data-testid="auth-input-email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                data-testid="auth-input-password"
                required
                minLength={6}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="At least 6 characters"
              />
            </div>
            <Button
              type="submit"
              className="w-full rounded-full"
              disabled={loading}
              data-testid="auth-submit-button"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {tab === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}