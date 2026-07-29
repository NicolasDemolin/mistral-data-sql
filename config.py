"""
Configuration for ACPR Text-to-Data Workflow.
Loads environment variables from .env file and sets up sys.path for the client-python SDK.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from .env if present
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# Database Path
DB_NAME = os.environ.get("DATABASE_PATH", "acpr_reporting.db")
DB_PATH = BASE_DIR / DB_NAME

# Add the cloned client-python SDK to sys.path so `from mistralai.client import Mistral` works
SDK_SRC = BASE_DIR / "client-python" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

# ── Mistral AI Settings ──────────────────────────────────────────────────
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_AGENT_ID = os.environ.get("MISTRAL_AGENT_ID", "")

# Models available on AI Studio
MODEL_LARGE = os.environ.get("MISTRAL_MODEL_LARGE", "mistral-large-latest")
MODEL_MEDIUM = os.environ.get("MISTRAL_MODEL_MEDIUM", "mistral-medium-latest")
MODEL_CODE = os.environ.get("MISTRAL_MODEL_CODE", "codestral-latest")
MODEL_EMBED = os.environ.get("MISTRAL_MODEL_EMBED", "mistral-embed")

# ── Web Server Settings ──────────────────────────────────────────────────
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))

# ── Defaults ─────────────────────────────────────────────────────────────
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "EUR")
DEFAULT_PERIOD = os.environ.get("DEFAULT_PERIOD", "2023-Q4")
