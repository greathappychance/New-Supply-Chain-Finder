from __future__ import annotations

from dataclasses import dataclass

from .constants import ITEM_NAME_MAX_LENGTH, ITEM_NAME_MIN_LENGTH, PURCHASE_TYPES


@dataclass(frozen=True)
class ValidationErrors:
    purchase_type: str | None = None
    item_name: str | None = None

    @property
    def has_errors(self) -> bool:
        return self.purchase_type is not None or self.item_name is not None


def validate_recommend_input(purchase_type: object, item_name: object) -> ValidationErrors:
    """입력 검증 (PRD §3.2)"""
    type_error: str | None = None
    if not isinstance(purchase_type, str) or purchase_type == "":
        type_error = "구매 유형을 선택해주세요."
    elif purchase_type not in PURCHASE_TYPES:
        type_error = "올바른 구매 유형이 아닙니다."

    item_error: str | None = None
    if not isinstance(item_name, str) or item_name.strip() == "":
        item_error = "품목명을 입력해주세요."
    else:
        # 파이썬 문자열 길이는 코드 포인트 단위라 이모지도 1자로 센다.
        length = len(item_name.strip())
        if length < ITEM_NAME_MIN_LENGTH:
            item_error = f"품목명은 {ITEM_NAME_MIN_LENGTH}자 이상 입력해주세요."
        elif length > ITEM_NAME_MAX_LENGTH:
            item_error = f"품목명은 {ITEM_NAME_MAX_LENGTH}자 이하로 입력해주세요."

    return ValidationErrors(purchase_type=type_error, item_name=item_error)
