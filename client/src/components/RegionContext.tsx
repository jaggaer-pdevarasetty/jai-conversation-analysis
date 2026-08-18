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
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    const apply = (items: RegionInfo[]) => {
      if (cancelled) return;
      setRegions(items);
      const known = !!saved && items.some((r) => r.label === saved);
      const usable = !!saved && items.some((r) => r.label === saved && r.reachable !== false);
      // Use the saved region only if it is reachable now; otherwise fall back to all for THIS
      // session. Don't erase a saved region that merely became unreachable (e.g. during a
      // backend restart) — keep it so it's restored once the region recovers. Only forget it
      // if it no longer exists at all.
      setRegionState(usable ? saved! : "");
      if (typeof window !== "undefined" && saved && !known) {
        window.localStorage.removeItem(STORAGE_KEY);
      }
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
            retryTimer = setTimeout(() => load(attempt + 1), Math.min(1000 * (attempt + 1), 5000));
          } else {
            setRegions([]);
            setLoading(false);
          }
        });
    };
    load(0);
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
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
