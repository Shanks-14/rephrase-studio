import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { Loader2, RotateCcw, Check } from "lucide-react";

export default function WordReplacementModal({ open, change, mode, onOpenChange, onApply, onRevert }) {
  const [alternatives, setAlternatives] = useState([]);
  const [selected, setSelected] = useState("");
  const [custom, setCustom] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !change) return;
    setSelected(change.replacement || "");
    setCustom("");
    const initial = change.alternatives || [];
    setAlternatives(initial);
    if (initial.length < 3) {
      setLoading(true);
      api
        .post("/rephrase/alternatives", {
          word: change.original,
          mode,
          context: change.context || "",
        })
        .then(({ data }) => {
          const merged = Array.from(
            new Set([...(initial || []), ...(data.alternatives || [])])
          );
          setAlternatives(merged);
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [open, change, mode]);

  if (!change) return null;

  const apply = () => {
    const value = custom.trim() || selected;
    if (!value) return;
    onApply(change.id, value);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="word-replacement-modal">
        <DialogHeader>
          <DialogTitle className="text-2xl font-semibold tracking-tight">
            Replace <span className="italic text-primary">{change.original}</span>
          </DialogTitle>
          <DialogDescription>
            Currently:{" "}
            <span className="font-mono text-foreground">{change.replacement}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Alternatives {loading && <Loader2 className="inline w-3 h-3 animate-spin ml-1" />}
          </div>
          <div className="flex flex-wrap gap-2">
            {alternatives.length === 0 && !loading && (
              <span className="text-sm text-muted-foreground italic">
                No alternatives found. Enter your own below.
              </span>
            )}
            {alternatives.map((alt, i) => (
              <button
                key={`${alt}-${i}`}
                data-testid="modal-synonym-option"
                onClick={() => {
                  setSelected(alt);
                  setCustom("");
                }}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  selected === alt && !custom
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-secondary text-secondary-foreground border-border hover:border-primary"
                }`}
              >
                {alt}
              </button>
            ))}
          </div>

          <div className="pt-2">
            <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1.5">
              Or type your own
            </div>
            <Input
              data-testid="modal-custom-input"
              value={custom}
              placeholder={`Custom replacement for "${change.original}"`}
              onChange={(e) => setCustom(e.target.value)}
            />
          </div>

          <div className="flex items-center justify-between pt-3">
            <Button
              variant="outline"
              className="gap-2 rounded-full"
              data-testid="modal-revert-button"
              onClick={() => {
                onRevert(change.id);
                onOpenChange(false);
              }}
            >
              <RotateCcw className="w-4 h-4" /> Revert original
            </Button>
            <Button
              className="gap-2 rounded-full"
              data-testid="modal-apply-button"
              onClick={apply}
            >
              <Check className="w-4 h-4" /> Apply replacement
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}