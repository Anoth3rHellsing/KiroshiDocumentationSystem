import textwrap

TUTORIAL_STEPS: list[dict[str, object]] = [
    {
        "id": "welcome",
        "title": "Welcome to Kiroshi",
        "visual": "layout_map",
        "description": textwrap.dedent(
            """
            Welcome to your first launch of Kiroshi! This guided tour walks through every tab,
            table, and input you will use to document cases. Follow the prompts, explore the
            visuals, and use the navigation buttons to move between steps.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which main tab gives you an instant view of workload and priorities?",
            "options": ["Dashboard", "Settings", "Kiroshi Chat"],
            "answer": "Dashboard",
            "success": "Exactly — the Dashboard summarises tracked work at a glance.",
            "failure": "Hint: it's the first tab filled with charts and case tables.",
        },
    },
    {
        "id": "dashboard",
        "title": "Dashboard Tables",
        "visual": "dashboard_tables",
        "description": textwrap.dedent(
            """
            The Dashboard tab hosts every operational table:
            • **Tracked Cases** – live statuses, ownership, and quick actions.
            • **Dell Escalations & FedEx Replacements** – vendor-specific queues with ETAs.
            • **All My Saved Cases** – browse and reload anything stored on disk.
            Use the search bar to filter and the action buttons to load or stop tracking directly from the table rows.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Check each item after you review how the Dashboard tables work.",
            "items": [
                "I know where to search and filter tracked cases.",
                "I understand the Dell/FedEx table highlights vendor priorities.",
                "I can load a saved case from the All My Saved Cases table.",
            ],
            "success": "Great! You're ready to use the Dashboard tables day to day.",
            "instruction": "Mark every checkbox once you've read the descriptions above.",
        },
    },
    {
        "id": "case_workspace",
        "title": "Case Workspace & Inputs",
        "visual": "case_sections",
        "description": textwrap.dedent(
            """
            Every case tab is a full workspace that captures customer details, troubleshooting steps,
            escalation information, optional hardware diagnostics, attachments, and AI helpers. Toggle
            hardware or escalation fields when needed and use the Tables tab to copy a spreadsheet-ready
            summary of every input.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Where do you find the Excel-style snapshot of every captured field?",
            "options": [
                "Tables tab inside the case workspace",
                "Dashboard tab",
                "Report tab",
            ],
            "answer": "Tables tab inside the case workspace",
            "success": "Correct — each case includes a Tables tab for copy/paste exports.",
            "failure": "Try again: the Tables tab lives inside each case workspace.",
        },
    },
    {
        "id": "issue_reporter",
        "title": "Instant Issue Reporter",
        "visual": "issue_reporter_flow",
        "description": textwrap.dedent(
            """
            Launch the Issue Reporter from any case to bundle call notes, logs, and screenshots into a
            single vendor-ready packet. Kiroshi maps your troubleshooting narrative into the structured
            summary that partners expect, attaches the latest evidence, and stores a timestamped copy in
            your database for follow-up.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "What does the Issue Reporter automatically include before you submit?",
            "options": [
                "Only the text from your root cause field",
                "Screenshots, selected logs, and the troubleshooting summary",
                "A blank template you must fill in manually",
            ],
            "answer": "Screenshots, selected logs, and the troubleshooting summary",
            "success": "Yes — it packages artifacts and notes so vendors see the full story.",
            "failure": "Remember, the Issue Reporter assembles evidence for you before sending.",
        },
    },
    {
        "id": "escalations",
        "title": "Escalation Control Tower",
        "visual": "escalation_matrix",
        "description": textwrap.dedent(
            """
            Use the escalations drawer to track every hand-off. Capture vendor queue IDs, urgency, and
            response targets, then pin critical follow-ups to the dashboard badge strip. Shared escalation
            history keeps teams synchronized while automated reminders flag anything approaching its SLA.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Mark each checklist item once you have seen where to manage escalations.",
            "items": [
                "I can open the escalation drawer from a case tab.",
                "I know where SLA timers appear on the dashboard.",
                "I saw how vendor queue IDs are stored with the case.",
            ],
            "success": "Great — you can now coordinate escalations without losing context.",
            "instruction": "Check every box after reviewing the escalation features above.",
        },
    },
    {
        "id": "reporting",
        "title": "Reporting & Exports",
        "visual": "report_overview",
        "description": textwrap.dedent(
            """
            The Report tab turns AI Educate insights into visuals and downloadable PDFs. When AI Educate is enabled,
            refresh the dataset, inspect root-cause metrics, run the Bug Detector, and export a polished report.
            From any case you can also generate PDF summaries and ZIP bundles with attachments.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which tab generates the AI Educate PDF analytics report?",
            "options": ["Dashboard", "Report", "Kiroshi Chat"],
            "answer": "Report",
            "success": "Exactly — open the Report tab once AI Educate is enabled to export insights.",
            "failure": "The analytics live in the Report tab right next to Settings.",
        },
    },
    {
        "id": "analytics",
        "title": "Operations Analytics",
        "visual": "analytics_suite",
        "description": textwrap.dedent(
            """
            The analytics suite blends saved case metrics, Issue Reporter outcomes, and escalation load
            into a unified view. Trendlines spotlight recurring failure types, while the resolution heat
            map highlights where teams are beating or missing their targets.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Which visual helps you spot workload bottlenecks over the week?",
            "options": [
                "Resolution heat map",
                "Issue Reporter draft list",
                "Kiroshi Chat history",
            ],
            "answer": "Resolution heat map",
            "success": "Exactly — the heat map shows when cases cluster above SLA thresholds.",
            "failure": "Hint: look for the analytic that compares days to SLA performance.",
        },
    },
    {
        "id": "settings",
        "title": "Settings & Personalisation",
        "visual": "settings_overview",
        "description": textwrap.dedent(
            """
            Settings control 2nd Line mode, debug tools, AI Educate options, and now your onboarding
            history. Use this panel to toggle advanced assistance, import or export Educate datasets, and
            relaunch this tutorial whenever you like. Completion metadata records when you finished the
            tour and the version you saw.
            """
        ),
        "interaction": {
            "type": "radio",
            "prompt": "Where can you replay the onboarding tutorial after today?",
            "options": ["Dashboard", "Settings", "Case workspace"],
            "answer": "Settings",
            "success": "That's right — the Settings tab now includes a Repeat Tutorial button.",
            "failure": "Look in Settings for the onboarding controls and status badge.",
        },
    },
    {
        "id": "ui_refresh",
        "title": "Polished Interface & Shortcuts",
        "visual": "ui_refresh",
        "description": textwrap.dedent(
            """
            Subtle gradients, animated progress badges, and keyboard-aware navigation make the refreshed
            UI easier to scan. Tutorial step selectors, card highlights, and quick access buttons guide new
            users without getting in your way.
            """
        ),
        "interaction": {
            "type": "checkbox_group",
            "prompt": "Tick the enhancements you noticed in the new interface.",
            "items": [
                "Animated progress badges in the tutorial",
                "Improved contrast on cards and tables",
                "Step selector for jumping around the tour",
            ],
            "success": "Nicely spotted — those touches keep the workflow feeling fast.",
            "instruction": "Mark each enhancement after you've seen it in action.",
        },
    },
    {
        "id": "kiroshi_chat",
        "title": "Kiroshi Chat & Resources",
        "visual": "chat_resources",
        "description": textwrap.dedent(
            """
            Kiroshi Chat keeps a searchable manual database, including a new quick-reference summary of the README
            and Kiroshi workflow. Upload your own notes, search the knowledge base, or ask the assistant to cross-reference
            the "Kiroshi Quick Reference" entry any time you need a refresher.
            """
        ),
        "interaction": {
            "type": "text_confirm",
            "prompt": "Type READY to finish the tour and jump into Kiroshi.",
            "answer": "READY",
            "success": "Tutorial complete! You're ready to document real cases.",
            "failure": "Enter READY in all caps to confirm you're set.",
        },
    },
]
