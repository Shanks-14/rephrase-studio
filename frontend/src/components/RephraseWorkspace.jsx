import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Sparkles, Trash2, Copy, ClipboardPaste, ScanLine, Shield, Loader2, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import WordReplacementModal from "@/components/WordReplacementModal";
import ReportModal from "@/components/ReportModal";
import { useAuth } from "@/contexts/AuthContext";

const MODES = [
  { value: "synonym", label: "Synonym shift" },
  { value: "antonym", label: "Antonym inversion" },
  { value: "rhyme", label: "Rhymed flow" },
  { value: "syllable", label: "Syllable flip" },
  { value: "academic", label: "Academic tone" },
  { value: "conversational", label: "Conversational (AI bypass)" },
];

const SAMPLE_TEXT =
  "Artificial intelligence is transforming the world quickly. Many people believe that new technology will help solve important problems. However, we must think about the way it changes our life and work.";

function countWords(t) {
  const m = (t || "").match(/\b\w+\b/g);
  return m ? m.length : 0;
}

// Build output with clickable highlighted spans by finding change replacements in order.
function OutputRenderer({ output, changes, onWordClick }) {
  if (!output) {
    return (
      <div className="text-muted-foreground italic text-lg">
        Your humanized output will appear here…
      </div>
    );
  }
  if (!changes || changes.length === 0) {
    return <p className="whitespace-pre-wrap text-lg leading-relaxed">{output}</p>;
  }

  const parts = [];
  let cursor = 0;
  const text = output;
  // For each change, locate the first occurrence of replacement starting from cursor.
  const claimed = new Array(text.length).fill(false);
  const marks = [];
  for (const ch of changes) {
    const rep = ch.replacement;
    if (!rep) continue;
    // Find next occurrence not overlapping claimed
    const re = new RegExp(`\\b${rep.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g");
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      const start = m.index;
      const end = start + rep.length;
      if (!claimed.slice(start, end).some(Boolean)) {
        for (let i = start; i < end; i++) claimed[i] = true;
        marks.push({ start, end, ch });
        break;
      }
    }
  }
  marks.sort((a, b) => a.start - b.start);
  for (const mk of marks) {
    if (mk.start > cursor) {
      parts.push(
        <span key={`t-${cursor}`}>{text.slice(cursor, mk.start)}</span>
      );
    }
    parts.push(
      <span
        key={`h-${mk.ch.id}`}
        data-testid="highlighted-word-item"
        className="highlight-changed"
        onClick={() => onWordClick(mk.ch)}
        title={`Original: ${mk.ch.original}`}
      >
        {text.slice(mk.start, mk.end)}
      </span>
    );
    cursor = mk.end;
  }
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <p className="whitespace-pre-wrap text-lg leading-relaxed">{parts}</p>;
}

export default function RephraseWorkspace({ onPosUpdate, onScoresUpdate, scores }) {
  const { user } = useAuth();
  const [mode, setMode] = useState("synonym");
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(null); // 'ai' | 'plagiarism' | null
  const [modalChange, setModalChange] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportKind, setReportKind] = useState("ai");
  const [report, setReport] = useState(null);

  const inputCount = useMemo(() => countWords(input), [input]);
  const outputCount = useMemo(() => countWords(output), [output]);

  // Debounced POS analyze
  useEffect(() => {
    const t = setTimeout(() => {
      if (!input.trim()) {
        onPosUpdate({ nouns: [], verbs: [], adjectives: [], adverbs: [], prepositions: [] });
        return;
      }
      api
        .post("/analyze/pos", { text: input })
        .then(({ data }) => onPosUpdate(data.pos))
        .catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [input, onPosUpdate]);

  const doRephrase = async () => {
    if (!input.trim()) {
      toast.error("Please enter some text first.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/rephrase", { text: input, mode });
      setOutput(data.output);
      setChanges(data.changes || []);
      toast.success(`Rephrased · ${data.changes?.length || 0} words changed`);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const runDetect = async (kind) => {
    if (!user) {
      toast.error("Please sign in to run AI & plagiarism checks.");
      return;
    }
    if (!output.trim()) {
      toast.error("Rephrase something first, then run a check.");
      return;
    }
    setChecking(kind);
    try {
      const { data } = await api.post("/detect", { text: output });
      setReport(data);
      onScoresUpdate({ ai_score: data.ai_score, plagiarism_score: data.plagiarism_score });
      setReportKind(kind);
      setReportOpen(true);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setChecking(null);
    }
  };

  const applyReplacement = (id, newWord) => {
    setChanges((prev) => {
      const upd = prev.map((c) => (c.id === id ? { ...c, replacement: newWord } : c));
      // Rebuild output by replacing the previous replacement in text with newWord
      const target = prev.find((c) => c.id === id);
      if (target && target.replacement !== newWord) {
        const re = new RegExp(`\\b${target.replacement.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
        setOutput((o) => o.replace(re, newWord));
      }
      return upd;
    });
    toast.success("Replacement applied");
  };

  const revertReplacement = (id) => {
    setChanges((prev) => {
      const target = prev.find((c) => c.id === id);
      if (target) {
        const re = new RegExp(`\\b${target.replacement.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
        setOutput((o) => o.replace(re, target.original.replace(/[^A-Za-z]/g, "")));
      }
      return prev.filter((c) => c.id !== id);
    });
    toast.success("Reverted to original");
  };

  return (
    <>
      <section
        className="w-full rounded-3xl border border-border bg-card shadow-xl overflow-hidden relative grain"
        data-testid="center-rephrase-block"
      >
        {/* HEADER */}
        <div className="px-5 sm:px-7 py-4 border-b border-border bg-background/70 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-primary" />
            </div>
            <div>
              <div className="text-lg font-semibold tracking-tight leading-none">
                Rephrase Studio
              </div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
                {user ? "Full access" : `Guest · 350-word limit`}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase tracking-widest text-muted-foreground hidden sm:inline">
              Mode
            </span>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger
                data-testid="rephrase-mode-dropdown"
                className="w-[220px] rounded-full"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES.map((m) => (
                  <SelectItem
                    key={m.value}
                    value={m.value}
                    data-testid={`mode-option-${m.value}`}
                  >
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* BODY */}
        <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border min-h-[480px]">
          {/* Input */}
          <div className="p-6 sm:p-7 flex flex-col relative">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
                Your text
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-full text-xs gap-1.5"
                  data-testid="input-sample-button"
                  onClick={() => setInput(SAMPLE_TEXT)}
                >
                  <FileText className="w-3.5 h-3.5" /> Sample
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-full text-xs gap-1.5"
                  data-testid="input-paste-button"
                  onClick={async () => {
                    try {
                      const t = await navigator.clipboard.readText();
                      setInput(t);
                    } catch {
                      toast.error("Clipboard access denied");
                    }
                  }}
                >
                  <ClipboardPaste className="w-3.5 h-3.5" /> Paste
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-full text-xs gap-1.5 text-destructive"
                  data-testid="input-clear-button"
                  onClick={() => {
                    setInput("");
                    setOutput("");
                    setChanges([]);
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" /> Clear
                </Button>
              </div>
            </div>
            <textarea
              data-testid="input-text-area"
              className="editor-textarea flex-1 min-h-[320px]"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Paste your paragraph here. VerbaHumanize will de-plagiarize it, humanize the tone, and expose word-level swaps you can adjust with one click."
            />
          </div>

          {/* Output */}
          <div className="p-6 sm:p-7 flex flex-col relative bg-background/40">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
                Rephrased output
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-full text-xs gap-1.5"
                  data-testid="output-copy-button"
                  disabled={!output}
                  onClick={() => {
                    navigator.clipboard.writeText(output);
                    toast.success("Copied to clipboard");
                  }}
                >
                  <Copy className="w-3.5 h-3.5" /> Copy
                </Button>
                <Button
                  size="sm"
                  className="rounded-full text-xs gap-1.5"
                  data-testid="rephrase-action-button"
                  onClick={doRephrase}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  Rephrase
                </Button>
              </div>
            </div>
            <div
              data-testid="output-text-container"
              className="flex-1 min-h-[320px] overflow-y-auto"
            >
              <OutputRenderer
                output={output}
                changes={changes}
                onWordClick={(ch) => {
                  setModalChange(ch);
                  setModalOpen(true);
                }}
              />
            </div>
          </div>
        </div>

        {/* FOOTER */}
        <div className="px-5 sm:px-7 py-4 border-t border-border bg-background/70 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-5 text-sm font-mono text-muted-foreground">
            <div data-testid="footer-input-word-count">
              Input:{" "}
              <span className="text-foreground font-semibold">{inputCount}</span> words
            </div>
            <div className="text-muted-foreground/60">→</div>
            <div data-testid="footer-output-word-count">
              Output:{" "}
              <span className="text-foreground font-semibold">{outputCount}</span> words
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="rounded-full gap-2"
              data-testid="check-ai-level-button"
              onClick={() => runDetect("ai")}
              disabled={checking !== null}
            >
              {checking === "ai" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ScanLine className="w-4 h-4" />
              )}
              Check AI Level
            </Button>
            <Button
              className="rounded-full gap-2"
              data-testid="check-plagiarism-level-button"
              onClick={() => runDetect("plagiarism")}
              disabled={checking !== null}
            >
              {checking === "plagiarism" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Shield className="w-4 h-4" />
              )}
              Check Plagiarism
            </Button>
          </div>
        </div>
      </section>

      <WordReplacementModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        change={modalChange}
        mode={mode}
        onApply={applyReplacement}
        onRevert={revertReplacement}
      />
      <ReportModal
        open={reportOpen}
        onOpenChange={setReportOpen}
        report={report}
        kind={reportKind}
      />
    </>
  );
}