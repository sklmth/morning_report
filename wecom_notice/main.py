import os
import sys
from pathlib import Path

import uvicorn

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == "__main__":
    uvicorn.run(
        "wecom_notice.api:app",
        host=os.environ.get("WECOM_NOTICE_HOST", "127.0.0.1"),
        port=int(os.environ.get("WECOM_NOTICE_PORT", "8996")),
    )
