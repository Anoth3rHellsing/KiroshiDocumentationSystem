import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from case_documentation_app import (
    CaseData,
    RemoteSessionEntry,
    TrackingData,
    build_helpjuice_outline,
    generate_ai_educate_report_pdf,
    run_bug_detector,
)


def test_run_bug_detector_handles_repeated_labels_and_bug_mentions():
    dataset = {
        "cases": [
            {
                "case_id": "C-001",
                "title": "Scanner feed error",
                "root_cause": "Feeder jam",
                "solution": "Applied firmware bug fix",
                "repro_steps": "Load paper and start scan",
                "description_excerpt": "Initial jam happens and bug appears",
            },
            {
                "case_id": "C-002",
                "title": "Scanner feed error",
                "root_cause": "Feeder jam",
                "solution": "",
                "description_excerpt": "Bug occurs when feeder retries",
            },
            {
                "case_id": "C-003",
                "title": "Loose cable",
                "root_cause": "",
                "solution": "Secured the USB cable",
                "description_excerpt": "",
            },
            {
                "case_id": "C-004",
                "title": "Power failure",
                "root_cause": "Power supply",
                "solution": "Replaced adapter",
                "description_excerpt": "",
            },
        ]
    }

    bug_report = run_bug_detector(dataset)

    assert bug_report is not None
    recurring = bug_report["recurring_patterns"]
    assert len(recurring) == 1

    feeder_pattern = recurring[0]
    assert feeder_pattern["pattern"] == "Feeder jam"
    assert feeder_pattern["count"] == 2
    assert feeder_pattern["case_ids"] == ["C-001", "C-002"]

    bug_cases = bug_report["bug_cases"]
    assert {case["case_id"] for case in bug_cases} == {"C-001", "C-002"}

    summary = bug_report["summary"]
    assert "Se detectaron patrones recurrentes" in summary
    assert "Se identificaron 2 casos con referencia directa a bugs." in summary



def test_generate_ai_educate_report_pdf_renders_tables_and_bug_summary(monkeypatch):
    counts_recent = pd.DataFrame(
        [
            {"analysis_label": "Feeder jam", "count": 3},
            {"analysis_label": "Calibration", "count": 1},
        ]
    )
    counts_all_time = pd.DataFrame(
        [
            {"analysis_label": "Feeder jam", "count": 5},
            {"analysis_label": "Calibration", "count": 2},
        ]
    )
    timeline_recent = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "count": [1, 2],
        }
    )
    timeline_all = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-12-25"), pd.Timestamp("2024-01-03")],
            "count": [2, 4],
        }
    )
    recurring_df = pd.DataFrame(
        [
            {"analysis_label": "Feeder jam", "count": 5},
            {"analysis_label": "Calibration", "count": 2},
        ]
    )
    root_cause_df = pd.DataFrame(
        [
            {"root_cause": "Feeder jam", "count": 5},
            {"root_cause": "Calibration", "count": 2},
        ]
    )
    scanner_df = pd.DataFrame(
        [
            {"scanner": "Scanner X", "count": 4},
            {"scanner": "Scanner Y", "count": 1},
        ]
    )
    bug_cases_df = pd.DataFrame(
        [
            {
                "case_id": "C-001",
                "title": "Feeder jam persists",
                "saved_at": pd.Timestamp("2024-01-10"),
            }
        ]
    )

    insights = {
        "view_totals": {
            "30d": {
                "case_total": 4,
                "unique_labels": 2,
                "bug_solution_count": 1,
                "bug_mentions_count": 2,
            },
            "all_time": {
                "case_total": 10,
                "unique_labels": 3,
                "bug_solution_count": 3,
                "bug_mentions_count": 4,
            },
        },
        "counts": {"30d": counts_recent, "all_time": counts_all_time},
        "timeline": timeline_recent,
        "timeline_all": timeline_all,
        "recurring_issue_types": recurring_df,
        "common_root_causes": root_cause_df,
        "common_scanner_models": scanner_df,
        "bug_cases": bug_cases_df,
        "highlight_label": "Feeder jam",
        "highlight_count": 5,
        "highlight_case": {
            "case_id": "C-001",
            "title": "Feeder jam persists",
            "solution_excerpt": "Reset firmware",
        },
    }

    bug_report = {
        "summary": "Se detectaron patrones recurrentes",
        "recurring_patterns": [{"pattern": "Feeder jam", "count": 5}],
    }

    captured_tables: list[list[list[str]]] = []
    captured_paragraphs: list[str] = []

    class DummyParagraph:
        def __init__(self, text: str, style: object):
            self.text = text
            self.style = style
            captured_paragraphs.append(text)

    class DummyTable:
        def __init__(self, data, *args, **kwargs):
            self.data = data
            captured_tables.append(data)

        def setStyle(self, style):
            return None

    class DummySpacer:
        def __init__(self, *_, **__):
            pass

    class DummyDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer

        def build(self, story):
            self.buffer.write(b"%PDF-Stub")

    monkeypatch.setattr("case_documentation_app.Paragraph", DummyParagraph)
    monkeypatch.setattr("case_documentation_app.Table", DummyTable)
    monkeypatch.setattr("case_documentation_app.Spacer", DummySpacer)
    monkeypatch.setattr("case_documentation_app.SimpleDocTemplate", DummyDoc)

    pdf_bytes = generate_ai_educate_report_pdf(insights, bug_report)

    assert pdf_bytes.startswith(b"%PDF-Stub")
    assert any("AI Educate" in text for text in captured_paragraphs)
    assert any("Resultados de Bug Detector" in text for text in captured_paragraphs)
    assert any("Feeder jam" in text for text in captured_paragraphs)

    assert any(table[0] == ["Métrica", "30 días", "Historial"] for table in captured_tables)
    assert any(["Patrón", "Recurrencias"] in table for table in captured_tables)
    assert any(["Case ID", "Título", "Guardado"] in table for table in captured_tables)



def test_build_helpjuice_outline_compiles_metadata_and_steps():
    case = CaseData(
        company_name="ACME Dental",
        subscription_id="SUB-123",
        brief_description="Scanner outage investigation",
        case_id="CASE-42",
        repro_steps="Launch scan and observe jam",
        solution="Reset firmware module",
        root_cause="Feeder jam due to debris",
        tracking=TrackingData(priority="Critical"),
        remote_sessions=[
            RemoteSessionEntry(
                title="Diagnostics",
                notes="Collected logs and observed jam pattern",
            )
        ],
    )
    context = {"tab": "AI Insights", "timestamp": "2024-01-15T10:00:00Z"}
    matches = [
        {
            "case_id": "C-009",
            "root_cause": "Feeder jam",
            "solution": "Power cycle the device",
        }
    ]
    manual_docs = [
        {
            "title": "Firmware reset steps",
            "content": "Follow this guide to reset firmware when jam issues occur",
        },
        {"title": "Generic policy", "content": ""},
    ]

    outline = build_helpjuice_outline(
        case,
        context=context,
        logs="",
        user_notes="",
        matches=matches,
        manual_docs=manual_docs,
    )

    assert outline.startswith("# Helpjuice Guide – Scanner outage investigation")
    assert "**Company:** ACME Dental" in outline
    assert "**Case ID:** CASE-42" in outline
    assert "**Subscription:** SUB-123" in outline
    assert "**Detected in:** AI Insights" in outline
    assert "## Step-by-step remediation" in outline
    assert "Reproduce issue" in outline
    assert "Remote session recap" in outline
    assert "Cross-reference C-009" in outline
    assert "**Firmware reset steps**" in outline
    assert "## Reporter notes" not in outline
