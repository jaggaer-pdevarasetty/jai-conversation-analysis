# ADR-0014 — Overview with tenant administration workspace

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
Choose option 1 following product-owner clarification. `/` is the operational **Overview**, and
primary navigation contains **Overview**, **Tenants**, and **Review queue**. The Overview combines
aggregate tenant/user/source-conversation coverage with pooled analysis outcomes, telemetry health,
latest-run status, and recent records. Tenant pages remain one breadcrumbed workflow: **tenant
directory → tenant users → user conversations → conversation review**. Pending or analysing
conversations remain visible but cannot open a detail record until analysis completes.

The shell labels `/` as **Operational overview**, tenant routes as an **Authorised admin view**, and
pooled conversation routes as a **De-identified review** so the privacy scopes remain explicit.

## Consequences
- The default Overview uses the pooled analysis API and enriches it with aggregate dashboard counts;
  it still renders analysis data if the chat DB-backed aggregate request is unavailable.
- Tenant/user identity is confined to the explicitly authorised admin workflow; pooled list/detail
  APIs retain the ADR-0007 conversation-ID-only contract.
- No backend contract or dependency was added; existing lazy-analysis status is preserved.
