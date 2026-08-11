# ADR-0017 — Privacy modes (admin vs pooled) + PII controls

**Status:** Accepted (2026-08-11)

## Context
The ticket's NFR (AC-10 / ADR-0007) requires the reviewer area to be **pooled and
de-identified** — conversation ID only, no tenant/user, no PII. In practice the team also
wanted an **authorised admin view** that drills tenant → user → conversation. These conflict,
so we make it an explicit, configurable choice rather than a silent decision.

## Decision
A single setting **`PRIVACY_MODE`**:

- **`admin`** (default today): tenant/user identity is shown (internal reviewer dashboard).
  Broader than AC-10 — acceptable only for authorised internal reviewers.
- **`pooled`** (AC-10 compliant): the API exposes **no tenant/user identity** —
  - tenant/user names become **stable pseudonyms** (`tenant-ab12`, `user-cd34`) so grouping
    still works without revealing who; tenant/user **ids and conversation titles are dropped**
    (`app/privacy.py::apply_meta`, applied inside `dashboard.conversation_meta`, so `/feedback`
    and the conversation detail inherit it);
  - the **per-tenant drill-down endpoints are disabled** (`/dashboard/tenants…` → 403).

## PII controls (both modes)
Redaction runs **before text reaches the LLM** and **before it is stored** (`app/pii.py`):
- **Regex** (`scrub_pii`): email, phone, **IBAN, card, IPv4, SSN**.
- **NER** (spaCy `en_core_web_sm`): PERSON / ORG / GPE / LOC / FAC → tagged, degrades to
  regex-only if the model is absent.

## GDPR / privacy checklist
- **Data minimisation:** pooled mode = conversation-id-only; PII scrubbed everywhere. ✅
- **No model training on data:** Vertex AI enterprise tier (prompts not used for training). ✅
- **Access control:** reviewer RBAC gate exists but auth is **deferred** (not enabled) — ⚠️ TODO.
- **Retention:** results store keyed by conversation_id; **retention policy TBD** — ⚠️ TODO.
- **Right to erasure:** deletable by conversation_id from our store (chat DB is read-only). ✅ (needs an endpoint)
- **International transfer:** LangSmith/Vertex region must match data residency (EU vs US) — ⚠️ confirm.
- **Read-only source:** we never write to the chat DB. ✅

## Consequences
- Default `admin` intentionally does NOT meet AC-10; set `PRIVACY_MODE=pooled` for the
  compliant reviewer deployment. This is now a one-line, tested switch.
- Retention + erasure endpoint + auth remain open items (tracked in the roadmap / this list).
