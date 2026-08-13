"use client";

import PublicRoundedIcon from "@mui/icons-material/PublicRounded";
import { Box, MenuItem, TextField } from "@mui/material";
import { useRouter } from "next/navigation";
import { useRegion } from "./RegionContext";

/** Global region switcher in the app bar. Changing it refreshes every data page. */
export function RegionSelect() {
  const { region, setRegion, regions } = useRegion();
  const router = useRouter();

  return (
    <TextField
      select
      size="small"
      value={region}
      onChange={(event) => {
        setRegion(event.target.value);
        router.push("/");
      }}
      aria-label="Region"
      sx={{ minWidth: 172, bgcolor: "#FFFFFF", "& .MuiInputBase-root": { borderRadius: 2 } }}
      InputProps={{
        startAdornment: <PublicRoundedIcon sx={{ fontSize: 18, mr: 0.75, color: "text.secondary" }} />,
      }}
    >
      <MenuItem value="">All regions</MenuItem>
      {regions.map((info) => (
        <MenuItem key={info.label} value={info.label} disabled={info.reachable === false}>
          <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
            <Box
              component="span"
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor: info.reachable === false ? "error.main" : "success.main",
              }}
            />
            {info.label.toUpperCase()}
            {info.reachable === false ? " · unreachable" : ""}
          </Box>
        </MenuItem>
      ))}
    </TextField>
  );
}
