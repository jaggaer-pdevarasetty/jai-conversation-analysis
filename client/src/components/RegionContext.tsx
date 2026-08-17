"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchRegions, type RegionInfo } from "../services/dashboardApi";

interface RegionContextValue {
  region: string; // "" means all regions
  setRegion: (region: string) => void;
  regions: RegionInfo[];
  loading: boolean;
}

const RegionContext = createContext<RegionContextValue>({
  region: "",
  setRegion: () => {},
  regions: [],
  loading: true,
});

/** Global selected region — read by every data page so changing it refreshes all data. */
export const useRegion = () => useContext(RegionContext);

const STORAGE_KEY = "jai.region";

export function RegionProvider({ children }: { children: ReactNode }) {
  const [region, setRegionState] = useState("");
  const [regions, setRegions] = useState<RegionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    const apply = (items: RegionInfo[]) => {
      if (cancelled) return;
      setRegions(items);
      // Keep a saved region only if it is still reachable; else default to all.
      const next = saved && items.some((r) => r.label === saved && r.reachable !== false) ? saved : "";
      setRegionState(next);
      if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, next);
      setLoading(false);
    };
    const load = (attempt: number) => {
      fetchRegions()
        .then(apply)
        .catch(() => {
          if (cancelled) return;
          // The backend may be (re)starting — retry with backoff instead of leaving the
          // region dropdown permanently empty until a manual page reload.
          if (attempt < 5) {
            window.setTimeout(() => load(attempt + 1), Math.min(1000 * (attempt + 1), 5000));
          } else {
            setRegions([]);
            setLoading(false);
          }
        });
    };
    load(0);
    return () => {
      cancelled = true;
    };
  }, []);

  const setRegion = (next: string) => {
    setRegionState(next);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <RegionContext.Provider value={{ region, setRegion, regions, loading }}>
      {children}
    </RegionContext.Provider>
  );
}
