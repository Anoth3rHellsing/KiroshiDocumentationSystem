import pandas as pd

from KiroshiApp.models import CaseData
from KiroshiApp.services.pdf_generator import category_dataframe, dell_escalation_dataframe
from KiroshiApp.constants import DELL_ESCALATION_FIELD_LABELS


def _get_value(df: pd.DataFrame, field_label: str) -> str:
    match = df.loc[df["Field"] == field_label, "Value"]
    assert not match.empty
    return match.iloc[0]


def test_category_dataframe_value_column_is_string_preserving_text() -> None:
    cat_map = {
        "GENERAL": [
            "company_name",
            "scanner_previous_replacements",
            "hardware_test",
        ]
    }
    case = CaseData(
        company_name="ACME Dental",
        scanner_previous_replacements=3,
        hardware_test="Ran full diagnostics",
    )

    df = category_dataframe("GENERAL", case, cat_map)

    assert list(df.columns) == ["Field", "Value"]
    assert all(isinstance(value, str) for value in df["Value"])
    assert _get_value(df, "Company Name") == "ACME Dental"
    assert _get_value(df, "Scanner Previous Replacements") == "3"
    assert _get_value(df, "Hardware Test") == "Ran full diagnostics"


def test_dell_escalation_dataframe_value_column_is_string() -> None:
    case = CaseData(dell_issue_start_date="2024-01-05", dell_command_updates_status="Pending")

    df = dell_escalation_dataframe(case)

    assert list(df.columns) == ["Field", "Value"]
    assert all(isinstance(value, str) for value in df["Value"])
    label_map = dict(DELL_ESCALATION_FIELD_LABELS)
    assert _get_value(df, label_map["dell_issue_start_date"]) == "2024-01-05"
    assert _get_value(df, label_map["dell_command_updates_status"]) == "Pending"
