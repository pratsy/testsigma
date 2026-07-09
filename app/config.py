import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TESTS_DIR = DATA_DIR / "tests"
RUNS_DIR = DATA_DIR / "runs"
PROMOTIONS_DIR = DATA_DIR / "promotions"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# How long the deterministic executor waits for a selector before treating it
# as UI drift and handing off to the agentic recovery path.
DETERMINISTIC_STEP_TIMEOUT_MS = 2000

# The prototype's target app is served by this same FastAPI process, so
# Playwright drives it over real HTTP rather than in-process.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")
