from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ..analysis.tactical import build_tactical_analysis_report
from ..backup_restore import backup_reliability_data, restore_reliability_data
from ..source_documents import extract_pdf_text, register_pdf_source
from ..source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation, search_source_chunks


def run_workflow_audit() -> dict[str, object]:
    checks: list[dict[str, object]] = []
    errors: list[str] = []
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks.append(_run("fast_lane_demo", lambda: build_tactical_analysis_report({"score": 80, "grade": "B", "hard_reject": False}).fast_lane.to_json()))
        def source_flow() -> None:
            pdf = root / "demo.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource\n%%EOF")
            doc = register_pdf_source(pdf, root=root / "source")
            extract_pdf_text(doc.document_id, root=root / "source", extractor=lambda _path: (["Mercury supports messages."], 1))
            chunk = chunk_extracted_text(doc.document_id, root=root / "source")[0]
            search_source_chunks("Mercury", root=root / "source")
            create_manual_proposal(doc.document_id, chunk.chunk_id, "Manual note.", root=root / "source")
            create_source_citation(doc.document_id, chunk.chunk_id, "Citation note.", root=root / "source")
        checks.append(_run("source_knowledge_demo", source_flow))
        def backup_flow() -> None:
            (root / "data" / "reliability").mkdir(parents=True)
            (root / "data" / "reliability" / "sample.json").write_text("{}", encoding="utf-8")
            backup = backup_reliability_data(output_dir=root / "backups", root=root)
            restore_reliability_data(input_zip=backup["path"], root=root / "restore", dry_run=True)
        checks.append(_run("backup_dry_run", backup_flow))
    for check in checks:
        if check["status"] == "fail":
            errors.append(str(check["error"]))
    return {"workflow_audit_id": "workflow_audit_" + _now().replace(":", "").replace("-", ""), "status": "critical" if errors else "healthy", "checks": checks, "warnings": [], "errors": errors}


def _run(name: str, fn) -> dict[str, object]:
    start = datetime.now(UTC)
    try:
        fn()
        status = "pass"
        error = ""
    except Exception as exc:
        status = "fail"
        error = str(exc)
    duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
    return {"name": name, "status": status, "duration_ms": duration_ms, "error": error}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

