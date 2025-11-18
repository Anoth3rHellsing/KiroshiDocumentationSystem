# Desktop App Feature Task Plan

This document summarizes the tasks required to bring the Qt desktop application to feature parity with the Streamlit (Dev branch) experience. Tasks are grouped by functional area with key implementation notes.

## Case Tab (Case Details)
- Build full CaseData form in logical order: header (client/subscription/product/ticket), phone call details, internal notes, conclusion, questionnaire/survey answers, remote sessions.
- Add per-section completion indicators that update as users fill fields.
- Provide "Exportar a PDF" button reusing the Dev formatting logic and notifying the save location.
- Enable multitasking by letting the main window spawn multiple Case tabs, each with its own CaseData instance and tab title showing the case name/ID.

## Email Tab (Email Generation)
- List all supported templates except the “I'm Bored” mini-game; group by category (standard, 2ª línea, FedEx, Dell, etc.).
- Generate prompts with the standard greeting using current CaseData plus template-specific fields; show result in read-only text with generate/copy actions.
- Respect 2nd Line mode: only show or enable advanced templates when the flag is active and explain restrictions via tooltip/message.

## Hardware Issues Tab
- Provide PC hardware and Scanner hardware sections with aligned field/value layouts.
- Include “Copy table” buttons for each section to copy tab-delimited blocks; highlight missing critical fields (e.g., serial).

## Tables Tab
- Render a read-only consolidated table of all CaseData fields (field, value) with a "Copy all" action and blank/"N/A" for missing values.

## Debug Tab
- Inputs for OPENAI_API_KEY (placeholder) and model selector (GPT-4, GPT-3.5, Local API, Local Model); disable key when not needed.
- Show logs or session state in a multi-line read-only area with a refresh button.

## Settings Tab
- Toggle for 2nd Line mode that reveals advanced features across the app; persist between sessions.
- Toggle for autosave directly to the database, writing snapshots to `KiroshiDatabase/TrackedCases/` when enabled; persist setting.
- Include other Dev parity options (language, analytics, integrations) grouped by category.

## Dashboard / Control Tower
- Default dashboard tab with panels: tracked cases with priority, Dell escalations with SLA cues, FedEx replacements with tracking status, and recent cases list for quick reopen.
- Allow opening a selected case into a new Case tab; color-code priority/SLA states.
- Provide configuration path for Dell escalation queues/SLAs and integrate FedEx tracking numbers (manual status acceptable if API is unavailable).

## Tracking Fields in Case Tab (2nd Line)
- When 2nd Line is active, show a tracking/escalation block with fields for priority, external ticket, ETA/SLA, gated by a "Marcar este caso para seguimiento" toggle and validations.
- Ensure tracked cases populate the dashboard lists.

## Hotkeys and Copy Buttons
- Register Ctrl+Alt+1/2/3… shortcuts to copy formatted sections (phone call, internal notes, conclusion, survey/remotes, etc.) from the active Case tab.
- Add copy buttons near each section as an alternative, reusing the same formatting helpers and brief notifications on copy.

## Validation and Data Quality
- Enforce required fields (client, description, conclusion, etc.) before exports/emails/closure; highlight missing items with clear messages.
- Apply format validators for specific inputs (Case ID patterns, emails, serials) via Qt validators or on-blur checks.
- Prepare hooks for future automated verification without implementing them yet.

## Autosave and Persistence
- Autosave current CaseData to `autosave.json` after significant interactions.
- If autosave-to-DB is on, also write snapshots to `KiroshiDatabase/TrackedCases/{case_id}.json` (create folder if absent).
- On startup, detect autosaves and offer to restore them into new Case tabs, avoiding duplicate reloading.

## Onboarding and Help
- First-run tutorial (QWizard or guided modals) covering key tabs (Dashboard, Case, Email, Settings); add a "replay tutorial" option in Settings.
- Add tooltips for key controls and an in-app quick reference (e.g., from `docs/kiroshi_quick_reference.json`).

## Explicit Exclusions
- Do not include the “I'm Bored” mini-game in any template list or feature.
