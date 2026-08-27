import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import StarRoundedIcon from "@mui/icons-material/StarRounded";
import { Chip, Stack, Tooltip } from "@mui/material";

/** Structural shape (matches EAInfo in both service modules) so this stays decoupled. */
type EALike = {
  label: string;
  product: string;
  status: string;
  privacy: string;
  privacy_sensitive: boolean;
};

/** Early Access badge shown on tenant cards + reviewer views (mirrors the Confluence roster). */
export function EABadge({ ea, size = "small" }: { ea?: EALike | null; size?: "small" | "medium" }) {
  if (!ea) return null;
  const blocked = ea.status === "blocked";
  return (
    <Stack direction="row" spacing={0.5} alignItems="center" component="span" useFlexGap flexWrap="wrap">
      <Tooltip title={`Early Access customer · ${ea.product}${ea.status ? ` · ${ea.status}` : ""}`}>
        <Chip
          size={size}
          icon={<StarRoundedIcon />}
          label={`Early Access · ${ea.product}`}
          color={blocked ? "warning" : "primary"}
          variant="outlined"
          aria-label={`Early Access customer, ${ea.product}, ${ea.status}`}
          sx={{ fontWeight: 700 }}
        />
      </Tooltip>
      {ea.privacy_sensitive && (
        <Tooltip title={ea.privacy}>
          <Chip
            size={size}
            icon={<ShieldOutlinedIcon />}
            label="Privacy"
            color="error"
            variant="outlined"
            aria-label={`Privacy sensitive: ${ea.privacy}`}
            sx={{ fontWeight: 700 }}
          />
        </Tooltip>
      )}
    </Stack>
  );
}
