from __future__ import annotations

from ..config import get_setting
from .base import ProviderConfigError, SupplierProvider
from .mock import MockSupplierProvider
from .openai_provider import OpenAISupplierProvider

__all__ = ["ProviderConfigError", "SupplierProvider", "get_supplier_provider"]


def get_supplier_provider() -> SupplierProvider:
    """데이터 공급원을 고른다. 기본값은 실제 업체를 조사하는 "ai".

    가상 업체 샘플("mock")은 개발·테스트용으로, SUPPLIER_PROVIDER=mock 일 때만 쓴다.
    """
    name = get_setting("SUPPLIER_PROVIDER") or "ai"
    if name == "ai":
        return OpenAISupplierProvider()
    if name == "mock":
        return MockSupplierProvider()
    raise ProviderConfigError(f"알 수 없는 SUPPLIER_PROVIDER: {name}")
