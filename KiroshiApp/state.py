from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List

AUTOSAVE_FILE = Path("autosave.json")


@dataclass
class SectionState:
    name: str
    content: str = ""
    completed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectionState":
        return cls(
            name=payload.get("name", ""),
            content=payload.get("content", ""),
            completed=bool(payload.get("completed", False)),
        )


@dataclass
class CaseState:
    title: str = "Untitled Case"
    case_id: str = ""
    tracked_case_path: str | None = None
    sections: Dict[str, SectionState] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)

    def ensure_section(self, name: str) -> SectionState:
        if name not in self.sections:
            self.sections[name] = SectionState(name=name)
        return self.sections[name]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "case_id": self.case_id,
            "tracked_case_path": self.tracked_case_path,
            "attachments": list(self.attachments),
            "sections": {name: section.to_dict() for name, section in self.sections.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "CaseState":
        sections = {
            name: SectionState.from_dict(data)
            for name, data in (payload.get("sections") or {}).items()
        }
        return cls(
            title=payload.get("title", "Untitled Case"),
            case_id=payload.get("case_id", ""),
            tracked_case_path=payload.get("tracked_case_path"),
            attachments=payload.get("attachments", []) or [],
            sections=sections,
        )


def save_autosave(cases: List[CaseState]) -> None:
    payload = {"cases": [case.to_dict() for case in cases]}
    AUTOSAVE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_autosave() -> List[CaseState]:
    if not AUTOSAVE_FILE.exists():
        return []
    try:
        data = json.loads(AUTOSAVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [CaseState.from_dict(item) for item in data.get("cases", [])]
