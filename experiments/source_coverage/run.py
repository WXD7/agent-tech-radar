import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from radar.store import load_catalog


def run() -> dict:
    catalog = load_catalog()
    rows = []
    for technology in catalog.technologies:
        checks = {
            "homepage": bool(technology.homepage),
            "repository": bool(technology.repository),
            "capabilities": bool(technology.capability_ids),
            "sources": bool(technology.source_ids),
        }
        rows.append(
            {
                "technology_id": technology.id,
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
    result = {
        "experiment_id": "exp-source-coverage",
        "technology_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "all_passed": all(row["passed"] for row in rows),
        "rows": rows,
    }
    output = Path(__file__).with_name("result.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["all_passed"] else 1)
