"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import BusinessRoundedIcon from "@mui/icons-material/BusinessRounded";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import {
  Alert,
  AlertTitle,
  Avatar,
  Box,
  Button,
  InputAdornment,
  Paper,
  Skeleton,
  Stack,
  TablePagination,
  TextField,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StatCard } from "../../src/components/StatCard";
import { fetchTenants, type Tenant } from "../../src/services/dashboardApi";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    fetchTenants().then(setTenants).catch(() => setError("The tenant directory could not be loaded. Check the API connection and try again."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredTenants = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return tenants ?? [];
    return (tenants ?? []).filter((tenant) => tenant.name.toLowerCase().includes(query) || tenant.tenant_id.toLowerCase().includes(query));
  }, [search, tenants]);
  const visibleTenants = filteredTenants.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

  if (error) {
    return (
      <Alert severity="error" action={<Button color="inherit" onClick={load}>Try again</Button>}>
        <AlertTitle>Tenant directory unavailable</AlertTitle>
        {error}
      </Alert>
    );
  }

  if (!tenants) {
    return (
      <Stack spacing={2.5} aria-label="Loading tenants">
        <Skeleton variant="rounded" height={100} />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
          {[1, 2, 3].map((item) => <Skeleton key={item} variant="rounded" height={126} />)}
        </Box>
        <Skeleton variant="rounded" height={280} />
      </Stack>
    );
  }

  const userCount = tenants.reduce((total, tenant) => total + tenant.users, 0);
  const conversationCount = tenants.reduce((total, tenant) => total + tenant.conversations, 0);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="overline" color="primary.main">Organisation directory</Typography>
        <Typography variant="h1" component="h1">Tenants</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
          Choose a tenant to inspect its users, conversation volume, analysis status, and individual records.
        </Typography>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
        <StatCard label="Tenants" value={tenants.length.toLocaleString()} helper="Organisations in the authorised view" icon={<BusinessRoundedIcon />} />
        <StatCard label="Users" value={userCount.toLocaleString()} helper="Distinct users across tenants" icon={<GroupsOutlinedIcon />} tone="#356BB3" />
        <StatCard label="Conversations" value={conversationCount.toLocaleString()} helper="Available source conversations" icon={<ForumOutlinedIcon />} tone="#16815D" />
      </Box>

      <Paper sx={{ p: 2 }}>
        <TextField
          fullWidth
          size="small"
          label="Search tenants"
          placeholder="Tenant name or ID"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(0); }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
      </Paper>

      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Typography variant="h3">Tenant directory</Typography>
        <Typography variant="body2" color="text.secondary">{filteredTenants.length} {filteredTenants.length === 1 ? "tenant" : "tenants"}</Typography>
      </Box>

      {visibleTenants.length ? (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "repeat(2, minmax(0, 1fr))" }, gap: 2 }}>
          {visibleTenants.map((tenant) => (
            <Paper
              key={tenant.tenant_id}
              component={Link}
              href={`/tenants/${tenant.tenant_id}`}
              sx={{
                p: 2.5,
                display: "grid",
                gridTemplateColumns: "auto minmax(0, 1fr) auto",
                gap: 2,
                alignItems: "center",
                color: "inherit",
                textDecoration: "none",
                transition: "border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease",
                "&:hover": { borderColor: "primary.main", transform: "translateY(-1px)", boxShadow: "0 8px 24px rgba(16, 24, 40, 0.08)" },
                "&:focus-visible": { outline: "3px solid", outlineColor: "primary.light", outlineOffset: 2 },
              }}
            >
              <Avatar sx={{ width: 48, height: 48, bgcolor: "#FFF0E9", color: "primary.main" }}><BusinessRoundedIcon /></Avatar>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="h3" sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tenant.name}</Typography>
                <Typography variant="caption" color="text.secondary">Tenant ID {tenant.tenant_id}</Typography>
                <Stack direction="row" spacing={2.5} sx={{ mt: 1.5 }}>
                  <Box><Typography variant="body2" sx={{ fontWeight: 750 }}>{tenant.users.toLocaleString()}</Typography><Typography variant="caption" color="text.secondary">Users</Typography></Box>
                  <Box><Typography variant="body2" sx={{ fontWeight: 750 }}>{tenant.conversations.toLocaleString()}</Typography><Typography variant="caption" color="text.secondary">Conversations</Typography></Box>
                </Stack>
              </Box>
              <ArrowForwardRoundedIcon sx={{ color: "text.secondary" }} />
            </Paper>
          ))}
        </Box>
      ) : (
        <Paper sx={{ py: 8, px: 3, textAlign: "center" }}>
          <SearchRoundedIcon sx={{ fontSize: 36, color: "text.disabled" }} />
          <Typography variant="h3" sx={{ mt: 1 }}>No tenants match</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try searching with a different tenant name or ID.</Typography>
          <Button sx={{ mt: 2 }} onClick={() => { setSearch(""); setPage(0); }}>Clear search</Button>
        </Paper>
      )}

      {filteredTenants.length > rowsPerPage && (
        <Paper sx={{ overflow: "hidden" }}>
          <TablePagination
            component="div"
            count={filteredTenants.length}
            page={page}
            rowsPerPage={rowsPerPage}
            rowsPerPageOptions={[12, 24, 48]}
            onPageChange={(_, nextPage) => setPage(nextPage)}
            onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
            labelRowsPerPage="Tenants per page"
          />
        </Paper>
      )}
    </Stack>
  );
}
