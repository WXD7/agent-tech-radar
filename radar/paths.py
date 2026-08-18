from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"
PROPOSALS_ROOT = PROJECT_ROOT / "proposals"
INBOX_ROOT = PROJECT_ROOT / "inbox"
EXPERIMENTS_ROOT = PROJECT_ROOT / "experiments"
STATE_ROOT = PROJECT_ROOT / ".radar"
DATABASE_PATH = STATE_ROOT / "radar.db"

