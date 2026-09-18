import re
from pathlib import Path

test_path = Path('tests/test_dpi_ls_end_to_end.py')
content = test_path.read_text(encoding='utf-8')

import_jwt = "import jwt\n    from datetime import datetime, timedelta, timezone\n    "
token_gen = """
    token = jwt.encode(
        {"sub": "admin", "role": "ADMIN", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        "SUPER_SECRET_JWT_KEY_FOR_DPI_LS",
        algorithm="HS256"
    )
    headers = {"Authorization": f"Bearer {token}"}
"""

content = content.replace(
    'r = httpx.get(f"{info.base_url}/agents/e2e-agent/score", timeout=5.0)',
    import_jwt + token_gen + '    r = httpx.get(f"{info.base_url}/agents/e2e-agent/score", timeout=5.0, headers=headers)'
)

test_path.write_text(content, encoding='utf-8')
