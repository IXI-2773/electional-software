from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExtensionRecord:
    extension_id: str
    extension_type: str
    status: str
    module_path: str
    version: str
    dependencies: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["dependencies"] = list(self.dependencies)
        payload["warnings"] = list(self.warnings)
        return payload


def get_extension_registry() -> dict[str, object]:
    records = (
        ExtensionRecord("pdf_text_extractor_pypdf", "text_extractor", "active", "backend.electional.source_documents", "v1", ("pypdf",)),
        ExtensionRecord("source_knowledge_json", "source_index", "active", "backend.electional.source_knowledge", "v1"),
        ExtensionRecord("report_templates", "report_template", "active", "backend.electional.report_templates", "v1"),
        ExtensionRecord("objective_packs_json", "objective_pack", "active", "backend.electional.objective_packs", "v1"),
        ExtensionRecord("release_gate_checks", "release_check", "active", "backend.electional.governance.release_gates", "v1"),
    )
    return {"extensions": [record.to_json() for record in records], "count": len(records)}


def get_extension(extension_id: str) -> dict[str, object]:
    for record in get_extension_registry()["extensions"]:
        if record["extension_id"] == extension_id:
            return record
    return {"extension_id": extension_id, "status": "unknown", "warnings": ["unknown_extension"]}

