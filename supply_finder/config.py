"""설정값 읽기: 로컬은 .env, Streamlit Community Cloud는 Secrets(st.secrets)에서 읽는다."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent

# 이미 설정된 환경변수(배포 환경 등)는 덮어쓰지 않는다.
load_dotenv(APP_DIR / ".env", override=False)


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        # secrets.toml이 없거나 Streamlit 밖(테스트 등)에서 실행 중
        pass
    return default
