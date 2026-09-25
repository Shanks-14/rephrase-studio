import { useMemo } from "react";
import ScoreCard from "@/components/ScoreCard";

const POS_CATEGORIES = [
  { id: "nouns", label: "Nouns", varName: "--pos-noun" },
  { id: "verbs", label: "Verbs", varName: "--pos-verb" },
  { id: "adjectives", label: "Adjectives", varName: "--pos-adj" },
  { id: "adverbs", label: "Adverbs", varName: "--pos-adv" },
  { id: "prepositions", label: "Prepositions", varName: "--pos-prep" },
];

export default function Sidebar({ pos, scores }) {
  const buckets = pos || { nouns: [], verbs: [], adjectives: [], adverbs: [], prepositions: [] };
  const totalWords = useMemo(
    () => Object.values(buckets).reduce((n, arr) => n + arr.length, 0),
    [buckets]
  );

  return (
    <aside
      className="w-full flex flex-col gap-5"
      data-testid="left-sidebar"
    >
      <div className="rounded-3xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-lg font-semibold tracking-tight">Parts of Speech</h2>
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
            {totalWords} tokens
          </span>
        </div>
        <div className="space-y-4">
          {POS_CATEGORIES.map((cat) => {
            const words = buckets[cat.id] || [];
            return (
              <div key={cat.id} data-testid={`pos-${cat.id}-section`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ background: `var(${cat.varName})` }}
                    />
                    <span className="text-sm font-medium">{cat.label}</span>
                  </div>
                  <span className="text-xs font-mono text-muted-foreground">
                    {words.length}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5 min-h-[28px]">
                  {words.length === 0 ? (
                    <span className="text-xs text-muted-foreground italic">
                      — start typing —
                    </span>
                  ) : (
                    words.slice(0, 24).map((w, i) => (
                      <span
                        key={`${cat.id}-${i}`}
                        data-testid={`pos-${cat.id}-badge`}
                        className="text-xs px-2 py-0.5 rounded-full border font-mono"
                        style={{
                          color: `var(${cat.varName})`,
                          borderColor: `color-mix(in srgb, var(${cat.varName}) 40%, transparent)`,
                          background: `color-mix(in srgb, var(${cat.varName}) 8%, transparent)`,
                        }}
                      >
                        {w}
                      </span>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-3xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-lg font-semibold tracking-tight">Verification</h2>
          <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
            Scores
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <ScoreCard
            testId="circular-plagiarism-scorecard"
            label="Plagiarism"
            score={scores?.plagiarism_score ?? null}
            colorVar="--pos-adv"
          />
          <ScoreCard
            testId="circular-ai-scorecard"
            label="AI Detector"
            score={scores?.ai_score ?? null}
            colorVar="--pos-verb"
          />
        </div>
        <p className="mt-4 text-xs text-muted-foreground leading-relaxed">
          Sign in and run <span className="font-mono">Check AI</span> or{" "}
          <span className="font-mono">Check Plagiarism</span> to populate scores.
        </p>
      </div>
    </aside>
  );
}