"use client";

import { ToggleButton, ToggleButtonGroup } from "@mui/material";
import { useEnv } from "./EnvContext";

/** UIT / PROD environment switch in the app bar. Switching reloads the app into that
 * environment (data, regions, filters all follow). PROD is highlighted so it's obvious you're
 * on live data. Hidden unless more than one environment is configured. */
export function EnvToggle() {
  const { env, setEnv, environments } = useEnv();
  if (environments.length < 2) return null;

  return (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={env}
      onChange={(_, next) => next && setEnv(next)}
      aria-label="Environment"
      sx={{ bgcolor: "#FFFFFF", borderRadius: 2 }}
    >
      {environments.map((e) => (
        <ToggleButton
          key={e}
          value={e}
          aria-label={e}
          sx={{
            px: 1.5,
            fontWeight: 700,
            ...(e === "prod"
              ? { "&.Mui-selected": { bgcolor: "warning.main", color: "#3a2a00", "&:hover": { bgcolor: "warning.dark" } } }
              : {}),
          }}
        >
          {e.toUpperCase()}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}
