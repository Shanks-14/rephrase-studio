import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(null);

function getSystemPref() {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(mode) {
  const root = document.documentElement;
  const resolved = mode === "system" ? getSystemPref() : mode;
  if (resolved === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(() => localStorage.getItem("theme") || "system");

  useEffect(() => {
    applyTheme(mode);
    localStorage.setItem("theme", mode);
    if (mode === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => applyTheme("system");
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
  }, [mode]);

  const cycle = () => {
    setMode((m) => (m === "light" ? "dark" : m === "dark" ? "system" : "light"));
  };

  return (
    <ThemeContext.Provider value={{ mode, setMode, cycle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);