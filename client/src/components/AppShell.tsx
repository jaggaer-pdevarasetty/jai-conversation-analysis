"use client";

import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import BusinessRoundedIcon from "@mui/icons-material/BusinessRounded";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import ThumbsUpDownOutlinedIcon from "@mui/icons-material/ThumbsUpDownOutlined";
import {
  AppBar,
  Box,
  Chip,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { RegionSelect } from "./RegionSelect";

const DRAWER_WIDTH = 264;

const NAV = [
  { href: "/", label: "Overview", icon: <DashboardRoundedIcon /> },
  { href: "/tenants", label: "Tenants", icon: <BusinessRoundedIcon /> },
  { href: "/feedback", label: "Feedback", icon: <ThumbsUpDownOutlinedIcon /> },
  { href: "/conversations", label: "Review queue", icon: <FactCheckOutlinedIcon /> },
];

function Logo() {
  return (
    <Box component={Link} href="/" sx={{ display: "flex", alignItems: "center", gap: 1.25, color: "inherit", textDecoration: "none" }}>
      <Box
        sx={{
          display: "grid",
          placeItems: "center",
          width: 40,
          height: 40,
          bgcolor: "primary.main",
          color: "#fff",
          fontWeight: 850,
          borderRadius: 2.5,
          fontSize: 16,
          letterSpacing: 0.4,
          boxShadow: "0 8px 20px rgba(228, 81, 30, 0.28)",
        }}
      >
        JAI
      </Box>
      <Box sx={{ lineHeight: 1 }}>
        <Typography sx={{ color: "#FFFFFF", fontWeight: 800, fontSize: 15, letterSpacing: 0.25 }}>
          JAGGAER
        </Typography>
        <Typography sx={{ mt: 0.45, fontSize: 11.5, color: "#AEB8C8" }}>
          Conversation intelligence
        </Typography>
      </Box>
    </Box>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const overviewView = pathname === "/";
  const tenantView = pathname.startsWith("/tenants");
  const isActive = (href: string) => (href === "/" ? overviewView : pathname.startsWith(href));
  const pageTitle = overviewView
    ? "Overview"
    : pathname.startsWith("/feedback/")
      ? "Feedback review"
      : pathname === "/feedback"
        ? "User feedback"
        : pathname.includes("/users/")
          ? "User conversations"
          : pathname.startsWith("/tenants/")
            ? "Tenant users"
            : tenantView
              ? "Tenants"
              : pathname.startsWith("/conversations/")
                ? "Conversation review"
                : "Review queue";

  useEffect(() => setMobileOpen(false), [pathname]);

  const drawer = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ display: "flex", alignItems: "center", minHeight: 76, px: 2.5 }}>
        <Logo />
      </Box>
      <Box sx={{ px: 2, pt: 2.5 }}>
        <Typography variant="overline" sx={{ color: "#77849A", px: 1.25 }}>
          Workspace
        </Typography>
        <List sx={{ mt: 0.75, p: 0 }}>
          {NAV.map((item) => (
            <ListItemButton
              key={item.href}
              component={Link}
              href={item.href}
              selected={isActive(item.href)}
              sx={{
                minHeight: 46,
                borderRadius: 2.5,
                mb: 0.65,
                color: "#BAC3D0",
                "& .MuiListItemIcon-root": { color: "#7E8BA0" },
                "&:hover": { bgcolor: "rgba(255,255,255,0.06)", color: "#FFFFFF" },
                "&.Mui-selected": {
                  bgcolor: "rgba(228,81,30,0.16)",
                  color: "#FFFFFF",
                  "&:hover": { bgcolor: "rgba(228,81,30,0.2)" },
                },
                "&.Mui-selected .MuiListItemIcon-root": { color: "#FF8A5F" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 38 }}>{item.icon}</ListItemIcon>
              <ListItemText primaryTypographyProps={{ fontWeight: 650, fontSize: 14 }} primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Box>
      <Box sx={{ mt: "auto", p: 2 }}>
        <Box sx={{ p: 1.6, borderRadius: 2.5, bgcolor: "rgba(255,255,255,0.045)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "#D8DEE8" }}>
            <LockOutlinedIcon sx={{ fontSize: 16 }} />
            <Typography variant="caption" sx={{ fontWeight: 700 }}>
              Internal workspace
            </Typography>
          </Box>
          <Typography variant="caption" sx={{ color: "#8996AA", display: "block", mt: 0.6, lineHeight: 1.45 }}>
            Tenant administration and pooled conversation review
          </Typography>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{ width: { md: `calc(100% - ${DRAWER_WIDTH}px)` }, ml: { md: `${DRAWER_WIDTH}px` }, backdropFilter: "blur(14px)" }}
      >
        <Toolbar sx={{ minHeight: { xs: 64, md: 72 } }}>
          <IconButton
            color="inherit"
            edge="start"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
            sx={{ mr: 1.5, display: { md: "none" } }}
          >
            <MenuRoundedIcon />
          </IconButton>
          <Typography sx={{ fontSize: 15, fontWeight: 720 }}>{pageTitle}</Typography>
          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ ml: "auto" }}>
            <RegionSelect />
            <Chip
              icon={tenantView ? <AdminPanelSettingsOutlinedIcon /> : <LockOutlinedIcon />}
              label={overviewView ? "Operational overview" : tenantView ? "Authorised admin view" : "De-identified review"}
              size="small"
              variant="outlined"
              sx={{ color: "text.secondary", borderColor: "divider", bgcolor: "#FFFFFF", display: { xs: "none", sm: "flex" } }}
            />
          </Stack>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }} aria-label="Primary navigation">
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{ display: { xs: "block", md: "none" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, bgcolor: "#111A2A", border: 0 } }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{ display: { xs: "none", md: "block" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, bgcolor: "#111A2A", border: 0 } }}
        >
          {drawer}
        </Drawer>
      </Box>

      <Box component="main" sx={{ flexGrow: 1, width: { md: `calc(100% - ${DRAWER_WIDTH}px)` }, minWidth: 0 }}>
        <Toolbar sx={{ minHeight: { xs: 64, md: 72 } }} />
        <Box sx={{ width: "100%", maxWidth: 1560, mx: "auto", px: { xs: 2, sm: 3, lg: 4 }, py: { xs: 2.5, md: 4 } }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
