"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchEnvironments } from "../services/dashboardApi";
import { getEnv, persistEnv } from "../services/env";

interface EnvState {
  env: string; // current environment (uit/prod)
  setEnv: (env: string) => void;
  environments: string[]; // configured environments
  loading: boolean;
}

const EnvCtx = createContext<EnvState>({
  env: "uit",
  setEnv: () => {},
  environments: ["uit"],
  loading: true,
});

export const useEnv = () => useContext(EnvCtx);

export function EnvProvider({ children }: { children: ReactNode }) {
  const [env, setCurrentEnv] = useState("uit");
  const [environments, setEnvironments] = useState<string[]>(["uit"]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setCurrentEnv(getEnv());
    fetchEnvironments()
      .then((d) => {
        if (!cancelled && d.items?.length) setEnvironments(d.items.map((i) => i.env));
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setEnv = (next: string) => {
    if (!next || next === getEnv()) return;
    persistEnv(next);
    // Switching environment is a context switch: full reload so every provider + page re-fetches
    // for the new environment (regions, data, filters) and there's no cross-env carryover.
    if (typeof window !== "undefined") window.location.assign("/");
  };

  return <EnvCtx.Provider value={{ env, setEnv, environments, loading }}>{children}</EnvCtx.Provider>;
}
