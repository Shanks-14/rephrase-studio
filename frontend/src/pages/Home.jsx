import { useRef, useState } from "react";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import RephraseWorkspace from "@/components/RephraseWorkspace";
import SandboxMode from "@/components/SandboxMode";

export default function Home() {
  const [pos, setPos] = useState({
    nouns: [],
    verbs: [],
    adjectives: [],
    adverbs: [],
    prepositions: [],
  });
  const [scores, setScores] = useState({ ai_score: null, plagiarism_score: null });
  const [studioMode, setStudioMode] = useState("synonym");
  // Fan mode now lives here: it's the single source of truth for both the
  // toggle button (rendered inside RephraseWorkspace's header) and whether
  // the Word Sandbox section is mounted at all.
  const [fanActive, setFanActive] = useState(false);
  const studioOutputRef = useRef("");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-8 lg:py-12">
        {/* Hero */}
        <div className="mb-10 lg:mb-14 max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/60 px-3 py-1 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <span className="text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
              Rephrase · De-Plagiarize · Humanize
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.05]">
            Write like a{" "}
            <span className="italic text-primary">human</span>,
            <br />
            dodge the detectors.
          </h1>
          <p className="mt-5 text-lg text-muted-foreground max-w-2xl leading-relaxed">
            Paste any paragraph. Choose how to disguise it — synonyms, antonyms, rhymes,
            syllable-flips or full academic re-styling. See every change, click any
            highlighted word to swap it, then verify with real AI &amp; plagiarism scans.
          </p>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
          <div className="lg:col-span-3 order-2 lg:order-1">
            <Sidebar pos={pos} scores={scores} />
          </div>
          <div className="lg:col-span-9 order-1 lg:order-2 space-y-8">
            <RephraseWorkspace
              onPosUpdate={setPos}
              onScoresUpdate={setScores}
              scores={scores}
              onModeChange={setStudioMode}
              onOutputChange={(t) => (studioOutputRef.current = t)}
              fanActive={fanActive}
              onToggleFan={() => setFanActive((v) => !v)}
            />
            {fanActive && (
              <SandboxMode
                mode={studioMode}
                fanActive={fanActive}
                onPullFromStudio={() => studioOutputRef.current}
              />
            )}
          </div>
        </div>

        <footer className="mt-16 pt-8 border-t border-border">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="text-lg font-semibold">VerbaHumanize</div>
              <div className="text-sm text-muted-foreground">
                Editorial rephrase studio · powered by Python &amp; FastAPI
              </div>
            </div>
            <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
              Built for writers · researchers · storytellers
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}