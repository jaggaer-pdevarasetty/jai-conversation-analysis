"use client";

import {
  Alert,
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
import { useEffect, useState } from "react";
import { fetchTenants, type Tenant } from "../../src/services/dashboardApi";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTenants().then(setTenants).catch(() => setError("Could not load tenants."));
  }, []);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!tenants) return <Typography>Loading…</Typography>;

  return (
    <>
      <Typography variant="h4" gutterBottom>
        Tenants
      </Typography>
      <TableContainer component={Paper}>
        <Table aria-label="Tenants">
          <TableHead>
            <TableRow>
              <TableCell>Tenant</TableCell>
              <TableCell align="right">Users</TableCell>
              <TableCell align="right">Conversations</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tenants.map((t) => (
              <TableRow key={t.tenant_id} hover>
                <TableCell>
                  <MuiLink component={Link} href={`/tenants/${t.tenant_id}`} sx={{ fontWeight: 600 }}>
                    {t.name}
                  </MuiLink>
                </TableCell>
                <TableCell align="right">{t.users}</TableCell>
                <TableCell align="right">{t.conversations}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
