"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import PersonOutlineRoundedIcon from "@mui/icons-material/PersonOutlineRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import {
  Alert,
  AlertTitle,
  Avatar,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  InputAdornment,
  Link as MuiLink,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StatCard } from "../../../src/components/StatCard";
import { fetchTenants, fetchTenantUsers, type Tenant, type TenantUser } from "../../../src/services/dashboardApi";

export default function TenantUsersPage() {
  const params = useParams();
  const tenantId = String(params.tenantId);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [users, setUsers] = useState<TenantUser[] | null>(null);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([fetchTenants(), fetchTenantUsers(tenantId)])
      .then(([tenants, tenantUsers]) => {
        setTenant(tenants.find((item) => item.tenant_id === tenantId) ?? null);
        setUsers(tenantUsers);
      })
      .catch(() => setError("The tenant users could not be loaded. Check the API connection and try again."));
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const roles = useMemo(() => [...new Set((users ?? []).map((user) => user.role).filter((value): value is string => Boolean(value)))].sort(), [users]);
  const visibleUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (users ?? []).filter((user) =>
      (!role || user.role === role) &&
      (!query || user.user_name.toLowerCase().includes(query) || user.user_id.toLowerCase().includes(query)),
    );
  }, [role, search, users]);

  if (error) {
    return <Alert severity="error" action={<Button color="inherit" onClick={load}>Try again</Button>}><AlertTitle>Tenant unavailable</AlertTitle>{error}</Alert>;
  }

  if (!users) {
    return <Stack spacing={2.5} aria-label="Loading tenant users"><Skeleton variant="rounded" height={120} /><Skeleton variant="rounded" height={320} /></Stack>;
  }

  const conversations = users.reduce((total, user) => total + user.conversations, 0);
  const average = users.length ? Math.round(conversations / users.length) : 0;
  const tenantName = tenant?.name ?? `Tenant ${tenantId}`;

  return (
    <Stack spacing={3}>
      <Breadcrumbs aria-label="Tenant navigation">
        <MuiLink component={Link} href="/tenants" underline="hover">Tenants</MuiLink>
        <Typography color="text.primary">{tenantName}</Typography>
      </Breadcrumbs>

      <Box>
        <Typography variant="overline" color="primary.main">Tenant workspace</Typography>
        <Typography variant="h1" component="h1">{tenantName}</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>Browse users and open their conversation histories. Tenant ID {tenantId}.</Typography>
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
        <StatCard label="Users" value={users.length.toLocaleString()} helper="Users with conversation history" icon={<GroupsOutlinedIcon />} />
        <StatCard label="Conversations" value={conversations.toLocaleString()} helper="Across all users in this tenant" icon={<ForumOutlinedIcon />} tone="#16815D" />
        <StatCard label="Average per user" value={average.toLocaleString()} helper="Conversations per listed user" icon={<PersonOutlineRoundedIcon />} tone="#356BB3" />
      </Box>

      <Paper sx={{ p: 2, display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(260px, 1fr) 220px" }, gap: 1.5 }}>
        <TextField
          size="small"
          label="Search users"
          placeholder="User name or ID"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
        />
        <TextField fullWidth select size="small" label="Role" value={role} onChange={(event) => setRole(event.target.value)}>
          <MenuItem value="">All roles</MenuItem>
          {roles.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
        </TextField>
      </Paper>

      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Typography variant="h3">Users</Typography>
        <Typography variant="body2" color="text.secondary">{visibleUsers.length} of {users.length}</Typography>
      </Box>

      {visibleUsers.length ? (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" }, gap: 1.5 }}>
          {visibleUsers.map((user) => (
            <Paper
              key={user.user_id}
              component={Link}
              href={`/tenants/${tenantId}/users/${user.user_id}`}
              sx={{
                p: 2.25,
                display: "grid",
                gridTemplateColumns: "auto minmax(0, 1fr) auto",
                gap: 1.75,
                alignItems: "center",
                color: "inherit",
                textDecoration: "none",
                transition: "border-color 150ms ease, box-shadow 150ms ease",
                "&:hover": { borderColor: "primary.main", boxShadow: "0 7px 20px rgba(16, 24, 40, 0.07)" },
              }}
            >
              <Avatar sx={{ bgcolor: "#EEF2F7", color: "secondary.main", fontWeight: 750 }}>{user.user_name.trim().charAt(0).toUpperCase() || "U"}</Avatar>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontWeight: 750, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.user_name}</Typography>
                <Typography variant="caption" color="text.secondary">User ID {user.user_id}</Typography>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
                  <Chip size="small" label={user.role || "No role"} variant="outlined" />
                  <Typography variant="caption" color="text.secondary">{user.conversations} {user.conversations === 1 ? "conversation" : "conversations"}</Typography>
                </Stack>
              </Box>
              <ArrowForwardRoundedIcon sx={{ color: "text.secondary" }} />
            </Paper>
          ))}
        </Box>
      ) : (
        <Paper sx={{ py: 8, px: 3, textAlign: "center" }}>
          <SearchRoundedIcon sx={{ fontSize: 36, color: "text.disabled" }} />
          <Typography variant="h3" sx={{ mt: 1 }}>No users match</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Try another name, user ID, or role.</Typography>
          <Button sx={{ mt: 2 }} onClick={() => { setSearch(""); setRole(""); }}>Clear filters</Button>
        </Paper>
      )}
    </Stack>
  );
}
