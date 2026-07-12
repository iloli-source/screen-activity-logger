"""画面コンテキストの抽出（純粋・依存ゼロ）。

OCR行（一次情報）から「開いているアプリ・リソース・位置」という事実を
保守的なパターンで抽出する。解釈が誤っても一次情報（OCR行）は
呼び出し側で保持される前提（Issue #12の不変条件）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable

from screen_activity_logger.domain.models import ActivityDescription
from screen_activity_logger.domain.resource_sanitizer import (
    sanitize_url,
    url_domain,
)

# ファイル名（拡張子必須で保守的に）
_FILENAME_PATTERN = re.compile(
    r"([\w\-()（）&．.]+\.(?:xlsx?|pptx?|docx?|pdf|csv|numbers|key|pages|"
    r"md|txt|py|ts|js|json|yaml|yml|html))",
    re.IGNORECASE,
)
# 「<リソース> - <アプリ>」のタイトルバー型
_TITLE_BAR_PATTERN = re.compile(r"^(.+?)\s*[-–—]\s*([A-Za-z][\w .]*)$")
# URL（https?:// または ドメイン風）
_URL_PATTERN = re.compile(
    r"(https?://\S+|(?:[\w-]+\.)+(?:com|jp|net|org|io|dev|ai)(?:/\S*)?)"
)
# 位置表現
_LOCATION_PATTERNS = (
    re.compile(r"スライド\s*\d+\s*/\s*\d+"),
    re.compile(r"\d+\s*/\s*\d+\s*ページ"),
    re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"^Sheet\d+$"),
)


@dataclass(frozen=True)
class ScreenContext:
    """OCRから抽出した画面コンテキストの事実。"""

    app: str | None
    resource: str | None
    location: str | None


def parse_screen_context(ocr_lines: Iterable[str]) -> ScreenContext:
    """OCR行からアプリ・リソース・位置を抽出する。該当なしはNone。"""
    lines = tuple(ocr_lines)
    app, resource = _find_app_and_resource(lines)
    location = _find_location(lines)
    return ScreenContext(app=app, resource=resource, location=location)


def _find_app_and_resource(
    lines: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for line in lines:
        file_match = _FILENAME_PATTERN.search(line)
        if file_match and not _is_inside_url(line, file_match):
            resource = file_match.group(1)
            title_match = _TITLE_BAR_PATTERN.match(line.strip())
            app = title_match.group(2).strip() if title_match else None
            return app, resource
    for line in lines:
        url_match = _URL_PATTERN.search(line)
        if url_match:
            return None, sanitize_url(url_match.group(1))
    return None, None


def _is_inside_url(line: str, file_match: re.Match) -> bool:
    """ファイル名マッチがURLのスパン内にある（=URLの末尾断片）か。

    Issue #17 S1: 「.../4410.html」の断片をファイル名と誤認しないための判定。
    タイトルバーのファイル名（URL外）はURLより優先という現行仕様は維持する。
    """
    return any(
        m.start() <= file_match.start() and file_match.end() <= m.end()
        for m in _URL_PATTERN.finditer(line)
    )


def enrich_description(
    desc: ActivityDescription, ocr_lines: Iterable[str]
) -> ActivityDescription:
    """OCR由来の事実（タイトルバー等）でVLM推測を上書きする。

    OCRが該当を見つけられなかったフィールドはVLMの値を残す。
    actionは変更しない。
    """
    ctx = parse_screen_context(ocr_lines)
    return replace(
        desc,
        app_guess=ctx.app or desc.app_guess,
        resource=_merge_resource(ctx.resource, desc.resource),
        location=ctx.location or desc.location,
    )


def _merge_resource(
    ocr_resource: str | None, vlm_resource: str | None
) -> str | None:
    """OCRの事実とVLM推測のresourceをマージする（Issue #17）。

    原則はOCR優先。ただしOCR値がURL形で、VLM値がそのドメインを含む場合は
    VLM値を採る（OCRの事実がVLMの「タイトル＋URL併記」を裏付けた＝豊かな方）。
    """
    if ocr_resource is None:
        return vlm_resource
    if vlm_resource and _URL_PATTERN.fullmatch(ocr_resource):
        domain = url_domain(ocr_resource)
        if domain and domain in vlm_resource:
            return vlm_resource
    return ocr_resource


def _find_location(lines: tuple[str, ...]) -> str | None:
    for line in lines:
        for pattern in _LOCATION_PATTERNS:
            match = pattern.search(line.strip())
            if match:
                return match.group(0)
    return None
