"use client";

import {
  AppBar,
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from "@mui/material";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const DRAWER_WIDTH = 240;

const NAV = [
  { href: "/", label: "Overview", icon: <DashboardOutlinedIcon /> },
  { href: "/tenants", label: "Tenants", icon: <BusinessOutlinedIcon /> },
  { href: "/conversations", label: "All conversations", icon: <ForumOutlinedIcon /> },
];

function Logo() {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Box
        sx={{
          bgcolor: "primary.main",
          color: "#fff",
          fontWeight: 800,
          borderRadius: 1.5,
          px: 1,
          py: 0.25,
          fontSize: 18,
          letterSpacing: 0.5,
        }}
      >
        JAI
      </Box>
      <Box sx={{ lineHeight: 1 }}>
        <Typography sx={{ fontWeight: 800, fontSize: 15 }}>JAGGAER</Typography>
        <Typography sx={{ fontSize: 11, color: "text.secondary" }}>Conversation Analysis</Typography>
      </Box>
    </Box>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "#fbfbfd" }}>
      <AppBar position="fixed" elevation={0} sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Logo />
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", bgcolor: "#ffffff" },
        }}
      >
        <Toolbar />
        <List sx={{ px: 1, pt: 1 }}>
          {NAV.map((item) => (
            <ListItemButton
              key={item.href}
              component={Link}
              href={item.href}
              selected={isActive(item.href)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                "&.Mui-selected": { bgcolor: "#fff2ec", color: "primary.main" },
                "&.Mui-selected .MuiListItemIcon-root": { color: "primary.main" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 38 }}>{item.icon}</ListItemIcon>
              <ListItemText primaryTypographyProps={{ fontWeight: 600 }}>{item.label}</ListItemText>
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
