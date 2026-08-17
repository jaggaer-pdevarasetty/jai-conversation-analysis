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
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    fetchRegions()
      .then((items) => {
        setRegions(items);
        // Keep a saved region only if it is still reachable; else default to all.
        const next = saved && items.some((r) => r.label === saved && r.reachable !== false) ? saved : "";
        setRegionState(next);
        if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, next);
      })
      .catch(() => setRegions([]))
      .finally(() => setLoading(false));
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
