"use client";

import {
  Alert,
  Breadcrumbs,
  Link as MuiLink,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchTenantUsers, type TenantUser } from "../../../src/services/dashboardApi";

export default function TenantUsersPage() {
  const params = useParams();
  const tenantId = String(params.tenantId);
  const [users, setUsers] = useState<TenantUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTenantUsers(tenantId).then(setUsers).catch(() => setError("Could not load users."));
  }, [tenantId]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!users) return <Typography>Loading…</Typography>;

  return (
    <>
      <Breadcrumbs sx={{ mb: 1 }}>
        <MuiLink component={Link} href="/tenants">
          Tenants
        </MuiLink>
        <Typography color="text.primary">Users</Typography>
      </Breadcrumbs>
      <Typography variant="h4" gutterBottom>
        Users
      </Typography>
      <TableContainer component={Paper}>
        <Table aria-label="Users">
          <TableHead>
            <TableRow>
              <TableCell>User</TableCell>
              <TableCell>Role</TableCell>
              <TableCell align="right">Conversations</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.user_id} hover>
                <TableCell>
                  <MuiLink
                    component={Link}
                    href={`/tenants/${tenantId}/users/${u.user_id}`}
                    sx={{ fontWeight: 600 }}
                  >
                    {u.user_name}
                  </MuiLink>
                </TableCell>
                <TableCell>{u.role ?? "—"}</TableCell>
                <TableCell align="right">{u.conversations}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
