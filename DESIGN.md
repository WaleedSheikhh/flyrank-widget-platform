# Design Doc — Embeddable Widget & Lead-Capture Platform

## Problem

Let a customer (tenant) create an embeddable widget — a signup form or a CTA popover — get a one-line script tag, and paste it onto any website. Visitors on that site submit the widget; submissions must be validated, rate-limited, spam-filtered, enriched with geo data, and stored safely — even when any single piece of that chain fails. The owner views submissions and basic stats in a dashboard.

## Data model

**Widget**
- `id` (int, PK)
- `tenant_id` (string — Supabase user ID, indexed)
- `type` (enum: `signup_form`, `cta_popover`)
- `title` (string)
- `description` (string, nullable)
- `fields` (JSON — list of form field definitions, e.g. `[{"name": "email", "type": "email", "required": true}]`)
- `button_text` (string, default "Submit")
- `display_options` (JSON — e.g. color, position)
- `created_at` (datetime)

**Submission**
- `id` (int, PK)
- `widget_id` (int, FK → Widget, indexed)
- `tenant_id` (string, indexed — denormalized from widget, so tenant-isolation queries never need a join)
- `data` (JSON — the actual submitted form fields)
- `ip_address` (string)
- `country` (string, nullable — from geo enrichment)
- `city` (string, nullable)
- `geo_provider_used` (string, nullable — "provider_a" / "provider_b" / null if both failed)
- `created_at` (datetime)

**Tenant isolation:** every query on `Widget` or `Submission` filters by `tenant_id`, derived from the authenticated user's token — never from a request parameter. This is enforced at the query layer, not just checked after the fact.

## The embed flow

1. Owner creates a widget via the authenticated Widget Management API → gets back a `widget_id`.
2. Owner is given: `<script src="https://api.example.com/widget.js?id={widget_id}"></script>`
3. Customer pastes that script on their site (a different origin from the API).
4. The script fetches `GET /widgets/{id}/config` (public, cached, CORS-enabled) — gets the widget's fields, type, display options.
5. The script renders a form based on that config.
6. Visitor fills it out, submits → `POST /submissions` (public, CORS-enabled, validated, rate-limited, spam-checked).
7. Server enriches with geo (fallback chain), stores, fires a non-blocking confirmation side effect, returns success.
8. Owner later views it via the authenticated Dashboard API.

## API surface

**Widget management (authenticated)**
- `POST /widgets` — create
- `GET /widgets` — list own widgets
- `GET /widgets/{id}` — get one (tenant-checked)
- `PUT /widgets/{id}` — update (tenant-checked)
- `DELETE /widgets/{id}` — delete (tenant-checked)

**Public delivery**
- `GET /widgets/{id}/config` — public, cached, returns widget config as JSON
- `GET /widget.js` — public, cached long, versioned, the loader script

**Public submission**
- `POST /submissions` — public, CORS-enabled, validated, rate-limited, spam-checked

**Dashboard (authenticated)**
- `GET /dashboard/widgets/{id}/submissions` — list submissions for one widget (tenant-checked)
- `GET /dashboard/widgets/{id}/stats` — counts over time, geo breakdown

## Explicit non-goal

This capstone does not build a visual widget-design UI (drag-and-drop styling, live preview editor). Widget configuration is done via API calls with a JSON `display_options` field — the grade lives in the backend, not a form builder. A minimal HTML test page proves the render/submit flow works; it is not a polished customer-facing editor.