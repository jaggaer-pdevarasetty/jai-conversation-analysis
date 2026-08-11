"use client";

import AutorenewRoundedIcon from "@mui/icons-material/AutorenewRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Skeleton,
  Stack,
  TablePagination,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { fetchQueue, type QueueStats } from "../services/analysisApi";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  return new Intl.DateTimeFormat("en", { timeStyle: "medium" }).format(date);
}

export function AnalysisQueuePanel() {
  const [data, setData] = useState<QueueStats | null>(null);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const load = useCallback(() => {
    fetchQueue(rowsPerPage, page * rowsPerPage)
      .then((stats) => {
        setData(stats);
        setError(false);
        if (page > 0 && page * rowsPerPage >= stats.in_flight_or_queued) {
          setPage(Math.max(0, Math.ceil(stats.in_flight_or_queued / rowsPerPage) - 1));
        }
      })
      .catch(() => setError(true));
  }, [page, rowsPerPage]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [load]);

  if (!data && !error) return <Skeleton variant="rounded" height={150} aria-label="Loading analysis queue" />;
  if (!data) return <Alert severity="warning">Live analysis queue status is temporarily unavailable.</Alert>;

  return (
    <Paper aria-label="Live analysis queue" sx={{ overflow: "hidden" }}>
      <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2, display: "flex", alignItems: { xs: "flex-start", sm: "center" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
        <Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {data.in_flight > 0 ? <CircularProgress size={18} thickness={5} /> : <CheckCircleOutlineRoundedIcon color="success" sx={{ fontSize: 20 }} />}
            <Typography variant="h3">Live analysis queue</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
            Real conversations currently waiting, retrying, or being analysed by {data.workers} workers.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Chip size="small" label={`${data.queued} queued`} variant="outlined" />
          <Chip size="small" label={`${data.in_flight} analysing`} color={data.in_flight ? "primary" : "default"} />
          {data.dead_letter > 0 && <Chip size="small" icon={<ErrorOutlineRoundedIcon />} label={`${data.dead_letter} failed`} color="error" variant="outlined" />}
        </Stack>
      </Box>
      <Divider />

      {!data.started ? (
        <Typography variant="body2" color="text.secondary" sx={{ px: 2.5, py: 2 }}>Queue workers are inactive for the current server source.</Typography>
      ) : data.items.length ? (
        <Stack divider={<Divider flexItem />}>
          {data.items.map((item) => (
            <Box key={item.conversation_id} sx={{ px: { xs: 2, md: 2.5 }, py: 1.4, display: "grid", gridTemplateColumns: { xs: "1fr auto", md: "minmax(260px, 1fr) 130px 100px 130px" }, gap: 1.5, alignItems: "center" }}>
              <Typography variant="body2" sx={{ fontWeight: 700, overflowWrap: "anywhere" }}>{item.conversation_id}</Typography>
              <Chip
                size="small"
                icon={item.status === "analysing" ? <CircularProgress size={12} thickness={6} /> : item.status === "retrying" ? <AutorenewRoundedIcon /> : undefined}
                label={item.status === "analysing" ? "Analysing" : item.status === "retrying" ? "Retrying" : "Queued"}
                color={item.status === "analysing" ? "primary" : item.status === "retrying" ? "warning" : "default"}
                variant={item.status === "queued" ? "outlined" : "filled"}
                sx={{ justifySelf: { xs: "end", md: "start" } }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" } }}>Attempt {item.attempt}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" } }}>{formatDate(item.queued_at)}</Typography>
            </Box>
          ))}
        </Stack>
      ) : (
        <Box sx={{ px: 2.5, py: 2, display: "flex", alignItems: "center", gap: 1 }}>
          <CheckCircleOutlineRoundedIcon color="success" sx={{ fontSize: 19 }} />
          <Typography variant="body2" color="text.secondary">Queue is live and currently clear.</Typography>
        </Box>
      )}

      {data.started && data.in_flight_or_queued > rowsPerPage && (
        <TablePagination
          component="div"
          count={data.in_flight_or_queued}
          page={page}
          rowsPerPage={rowsPerPage}
          rowsPerPageOptions={[5, 10, 25]}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
          labelRowsPerPage="Queue items per page"
        />
      )}
    </Paper>
  );
}
