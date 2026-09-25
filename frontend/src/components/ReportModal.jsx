import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { AlertTriangle, ShieldCheck } from "lucide-react";

export default function ReportModal({ open, onOpenChange, report, kind }) {
  if (!report) return null;
  const score = kind === "ai" ? report.ai_score : report.plagiarism_score;
  const reasoning = kind === "ai" ? report.ai_reasoning : report.plagiarism_reasoning;
  const title = kind === "ai" ? "AI Detection Report" : "Plagiarism Report";
  const risky = score >= 70;
  const medium = score >= 40 && score < 70;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl" data-testid="report-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            {risky ? (
              <AlertTriangle className="w-6 h-6 text-rose-500" />
            ) : (
              <ShieldCheck className="w-6 h-6 text-emerald-500" />
            )}
            {title}
          </DialogTitle>
          <DialogDescription>
            {report.llm_used ? "Powered by LLM analysis." : "Heuristic analysis (no API key set)."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-2xl border border-border p-4 bg-background">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Overall score</span>
              <span
                className={`text-3xl font-semibold tabular-nums ${
                  risky ? "text-rose-500" : medium ? "text-amber-500" : "text-emerald-500"
                }`}
              >
                {score}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full transition-all duration-700 ${
                  risky ? "bg-rose-500" : medium ? "bg-amber-500" : "bg-emerald-500"
                }`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>

          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">
              Reasoning
            </div>
            <p className="text-base leading-relaxed">{reasoning}</p>
          </div>

          {report.risk_sentences?.length > 0 && (
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">
                Flagged sentences
              </div>
              <ul className="space-y-2">
                {report.risk_sentences.map((s, i) => (
                  <li
                    key={i}
                    className="text-sm italic border-l-2 border-amber-500 pl-3 py-1"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}