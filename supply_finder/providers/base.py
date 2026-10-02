from __future__ import annotations

from typing import Protocol

from ..models import ProviderResult


class ProviderConfigError(Exception):
    """API 키 누락 등 설정 문제. 메시지를 그대로 사용자에게 보여준다."""


class SupplierProvider(Protocol):
    def search(self, purchase_type: str, item_name: str) -> ProviderResult: ...
