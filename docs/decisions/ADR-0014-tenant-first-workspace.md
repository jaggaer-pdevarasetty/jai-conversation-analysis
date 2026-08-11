# ADR-0014 — Tenant-first administration workspace

**Status:** Accepted (2026-08-11)

## Context
The health-overview landing page in ADR-0013 did not match the required operator journey. The
product already has authorised dashboard endpoints for tenants, users, and user conversations,
but tenant routing was absent from primary navigation and those routes were disconnected tables.
Reviewers need to enter through a tenant, choose a user, inspect that user's conversations, and
then open an analysed record. The pooled review queue remains useful as a separate cross-tenant
workflow.

## Options considered
1. **Keep the health overview and add Tenants to navigation.** Smallest change, but leaves an
   unwanted landing page and makes the tenant workflow secondary.
2. **Make Tenants the landing workflow and keep the pooled queue separate.** Clear navigation,
   preserves the distinct privacy scopes, and uses the existing dashboard API.
3. **Merge tenant and pooled data into one dashboard.** Fewer routes, but mixes identity-bearing
   admin data with de-identified records and creates an overloaded screen.

## Decision
Choose option 2. `/` redirects to `/tenants`. Primary navigation contains **Tenants** and
**Review queue**, with no health-overview route. Tenant pages form one breadcrumbed workflow:
**tenant directory → tenant users → user conversations → conversation review**. Each level adds
search, useful counts, explicit loading/error/empty states, and context identifiers. Pending or
analysing conversations remain visible but cannot open a detail record until analysis completes.

The shell labels tenant routes as an **Authorised admin view** and pooled conversation routes as a
**De-identified review** so the two privacy scopes are not presented as equivalent.

## Consequences
- The default experience now depends on the read-only chat DB-backed dashboard endpoints.
- Tenant/user identity is confined to the explicitly authorised admin workflow; pooled list/detail
  APIs retain the ADR-0007 conversation-ID-only contract.
- No backend contract or dependency was added; existing lazy-analysis status is preserved.
