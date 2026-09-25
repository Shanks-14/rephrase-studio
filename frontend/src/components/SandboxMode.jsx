import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Fan, RotateCcw, Sparkles, Wand2, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";

const MODES = [
  { value: "synonym", label: "Synonyms" },
  { value: "antonym", label: "Antonyms" },
  { value: "rhyme", label: "Rhymes" },
  { value: "syllable", label: "Syllable flip" },
  { value: "academic", label: "Academic" },
  { value: "conversational", label: "Conversational" },
];

const IS_WORD = /^[A-Za-z][A-Za-z'-]*$/;

function tokenize(text) {
  if (!text) return [];
  const parts = text.match(/[A-Za-z][A-Za-z'-]*|[^A-Za-z\s]+|\s+/g) || [];
  return parts.map((p, i) => ({
    id: `t${i}`,
    text: p,
    isWord: IS_WORD.test(p),
    isSpace: /^\s+$/.test(p),
  }));
}

export default function SandboxMode({ initialText = "", mode: parentMode, onPullFromStudio }) {
  const [mode, setMode] = useState(parentMode || "synonym");
  const [text, setText] = useState(initialText);
  const [tokens, setTokens] = useState(() => tokenize(initialText));
  const [wordStates, setWordStates] = useState({}); // id -> { current, alternatives, index }
  const [fanActive, setFanActive] = useState(false);
  const [cursorPos, setCursorPos] = useState({ x: -100, y: -100 });
  const cycleRef = useRef({ id: null, timer: null });
  const cacheRef = useRef({}); // word_lower -> alternatives[]

  useEffect(() => {
    setMode(parentMode || "synonym");
  }, [parentMode]);

  const setTokensFromText = useCallback((t) => {
    setText(t);
    setTokens(tokenize(t));
    setWordStates({});
    cacheRef.current = {};
  }, []);

  // Global mouse tracker for fan cursor
  useEffect(() => {
    if (!fanActive) return;
    const onMove = (e) => setCursorPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", onMove);
    document.body.style.cursor = "none";
    return () => {
      window.removeEventListener("mousemove", onMove);
      document.body.style.cursor = "";
    };
  }, [fanActive]);

  const stopCycle = useCallback(() => {
    if (cycleRef.current.timer) {
      clearInterval(cycleRef.current.timer);
      cycleRef.current.timer = null;
      cycleRef.current.id = null;
    }
    setWordStates((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) {
        if (next[k]?.cycling) next[k] = { ...next[k], cycling: false };
      }
      return next;
    });
  }, []);

  const startCycle = useCallback(
    async (token) => {
      if (!token.isWord) return;
      if (cycleRef.current.id === token.id) return;
      stopCycle();

      const word = token.text;
      const key = word.toLowerCase();
      let alts = cacheRef.current[key];
      if (!alts) {
        try {
          const { data } = await api.post("/rephrase/alternatives", {
            word,
            mode,
            context: text.slice(0, 200),
          });
          alts = (data?.alternatives || []).filter(
            (a) => a && a.toLowerCase() !== key
          );
          cacheRef.current[key] = alts;
        } catch {
          alts = [];
        }
      }
      if (!alts.length) return;

      setWordStates((prev) => ({
        ...prev,
        [token.id]: {
          current: prev[token.id]?.current || word,
          alternatives: [word, ...alts],
          index: prev[token.id]?.index ?? 0,
          cycling: true,
        },
      }));

      let idx = wordStates[token.id]?.index ?? 0;
      cycleRef.current.id = token.id;
      cycleRef.current.timer = setInterval(() => {
        idx = (idx + 1) % (alts.length + 1);
        setWordStates((prev) => {
          const state = prev[token.id];
          if (!state) return prev;
          const list = state.alternatives;
          return {
            ...prev,
            [token.id]: {
              ...state,
              current: list[idx],
              index: idx,
            },
          };
        });
      }, 260);
    },
    [mode, stopCycle, text, wordStates]
  );

  const clickCycle = useCallback(
    async (token) => {
      if (!token.isWord || fanActive) return;
      const state = wordStates[token.id];
      if (state?.alternatives?.length) {
        // Advance one step
        const list = state.alternatives;
        const nextIdx = ((state.index ?? 0) + 1) % list.length;
        setWordStates((prev) => ({
          ...prev,
          [token.id]: { ...state, current: list[nextIdx], index: nextIdx },
        }));
        return;
      }
      // Fetch first time
      const word = token.text;
      const key = word.toLowerCase();
      let alts = cacheRef.current[key];
      if (!alts) {
        try {
          const { data } = await api.post("/rephrase/alternatives", {
            word,
            mode,
            context: text.slice(0, 200),
          });
          alts = (data?.alternatives || []).filter(
            (a) => a && a.toLowerCase() !== key
          );
          cacheRef.current[key] = alts;
        } catch {
          alts = [];
        }
      }
      if (!alts.length) {
        toast("No alternatives for this word");
        return;
      }
      const list = [word, ...alts];
      setWordStates((prev) => ({
        ...prev,
        [token.id]: { current: list[1], alternatives: list, index: 1, cycling: false },
      }));
    },
    [fanActive, mode, text, wordStates]
  );

  const wordCount = useMemo(() => tokens.filter((t) => t.isWord).length, [tokens]);
  const changedCount = useMemo(
    () =>
      Object.values(wordStates).filter(
        (s) => s?.current && s.alternatives && s.current !== s.alternatives[0]
      ).length,
    [wordStates]
  );

  const resetAll = () => {
    stopCycle();
    setWordStates({});
    toast.success("Sandbox reset");
  };

  const composedText = useMemo(
    () =>
      tokens
        .map((t) => (t.isWord && wordStates[t.id]?.current ? wordStates[t.id].current : t.text))
        .join(""),
    [tokens, wordStates]
  );

  return (
    <section
      className="w-full rounded-3xl border border-border bg-card shadow-xl overflow-hidden relative grain"
      data-testid="sandbox-block"
    >
      {/* Header */}
      <div className="px-5 sm:px-7 py-4 border-b border-border bg-background/70 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
            <Wand2 className="w-4 h-4 text-primary" />
          </div>
          <div>
            <div className="text-lg font-semibold tracking-tight leading-none">
              Word Sandbox
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
              Throw paint at the wall · hover with the fan
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger data-testid="sandbox-mode-dropdown" className="w-[170px] rounded-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODES.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant={fanActive ? "default" : "outline"}
            className="rounded-full gap-2"
            data-testid="sandbox-fan-toggle"
            onClick={() => {
              setFanActive((v) => {
                const next = !v;
                if (!next) stopCycle();
                return next;
              });
            }}
          >
            <Fan className={`w-4 h-4 ${fanActive ? "animate-spin" : ""}`} />
            {fanActive ? "Fan on" : "Fan mode"}
          </Button>
          <Button
            variant="ghost"
            className="rounded-full gap-2"
            data-testid="sandbox-reset"
            onClick={resetAll}
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </Button>
        </div>
      </div>

      {/* Poetic caption */}
      <div className="px-5 sm:px-7 py-3 border-b border-border bg-background/40">
        <p className="text-base italic text-muted-foreground leading-relaxed max-w-3xl">
          What happens when every word changes yet the meaning survives? Each
          rectangle is a doorway — drag the fan across them and watch language
          shape-shift while the sentence stays true.
        </p>
      </div>

      {/* Canvas */}
      <div
        className="p-5 sm:p-7 min-h-[240px] max-h-[420px] overflow-y-auto"
        onMouseLeave={stopCycle}
        data-testid="sandbox-canvas"
      >
        {tokens.length === 0 ? (
          <div className="text-center text-muted-foreground italic py-12">
            Paste text below or pull it from the Studio above to start the sandbox.
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {tokens.map((tk) => {
              if (tk.isSpace) return <span key={tk.id}>&nbsp;</span>;
              if (!tk.isWord) {
                return (
                  <span
                    key={tk.id}
                    className="inline-flex items-center px-1 text-muted-foreground self-center"
                  >
                    {tk.text}
                  </span>
                );
              }
              const state = wordStates[tk.id];
              const display = state?.current || tk.text;
              const changed = state && display !== tk.text;
              const cycling = state?.cycling;
              return (
                <span
                  key={tk.id}
                  data-testid="sandbox-word-box"
                  onMouseEnter={() => fanActive && startCycle(tk)}
                  onMouseLeave={() => fanActive && stopCycle()}
                  onClick={() => clickCycle(tk)}
                  className={[
                    "inline-flex items-center justify-center px-3 h-9 rounded-md border text-[17px] leading-none select-none transition-colors",
                    fanActive ? "cursor-none" : "cursor-pointer",
                    cycling
                      ? "border-primary text-primary bg-primary/10 animate-pulse"
                      : changed
                      ? "border-primary/60 text-primary bg-primary/5"
                      : "border-border bg-background hover:border-primary/40",
                  ].join(" ")}
                >
                  {display}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer input */}
      <div className="px-5 sm:px-7 py-4 border-t border-border bg-background/70">
        <div className="flex items-center justify-between mb-2 gap-3 flex-wrap">
          <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Sandbox source · {wordCount} words · {changedCount} altered
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="rounded-full gap-1.5 text-xs"
              data-testid="sandbox-pull-studio"
              onClick={() => {
                const t = onPullFromStudio?.();
                if (!t) {
                  toast("Nothing to pull — rephrase something in Studio first.");
                  return;
                }
                setTokensFromText(t);
                toast.success("Loaded Studio output into Sandbox");
              }}
            >
              <ArrowDown className="w-3.5 h-3.5" /> Pull from Studio
            </Button>
            <Button
              size="sm"
              className="rounded-full gap-1.5 text-xs"
              data-testid="sandbox-copy-composed"
              onClick={() => {
                navigator.clipboard.writeText(composedText);
                toast.success("Copied sandbox composition");
              }}
              disabled={!composedText.trim()}
            >
              <Sparkles className="w-3.5 h-3.5" /> Copy composition
            </Button>
          </div>
        </div>
        <textarea
          data-testid="sandbox-text-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => setTokensFromText(text)}
          placeholder="Paste text to sandbox — press Tab or click outside to spawn word tiles."
          className="w-full min-h-[68px] resize-y rounded-2xl border border-border bg-background px-3 py-2 text-[15px] leading-relaxed"
        />
      </div>

      {/* Fan cursor */}
      {fanActive && (
        <div
          aria-hidden
          className="fixed pointer-events-none z-[9999]"
          style={{
            left: cursorPos.x,
            top: cursorPos.y,
            transform: "translate(-50%, -50%)",
          }}
        >
          <Fan className="w-7 h-7 text-primary animate-spin drop-shadow-lg" />
        </div>
      )}
    </section>
  );
}