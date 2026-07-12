"""worklog.jsonl再演によるコンテキスト浄化のオフライン検証（Issue #17 R9）。

保存済みworklog.jsonlの生OCR行（一次情報）とresource等の保存値から
enrich_descriptionを現行コードで再実行し、old→newの差分と症状の残存を表示する。
VLM/ASRのフル再処理（Issue #15の推論遅延で数時間級）を回避する。

注意: 保存値は「昇格後」の値であり生VLM出力ではない近似。ただし4症状の検証には
十分（S1/S2はOCR経路、S3はOCR沈黙フレーム＝保存値がVLM生値、S4は接尾辞剥がし）。

使い方:
    python scripts/replay_context.py "glob1" ["glob2" ...]
"""

from __future__ import annotations

import glob
import json
import sys

from screen_activity_logger.domain.models import ActivityDescription, VideoTimestamp
from screen_activity_logger.domain.screen_context import enrich_description

# 症状の残存判定: 断片はresource全体が断片そのもの（フルURL内の部分一致は正常）、
# ボイラープレートは部分一致、重複はresource+location連結時の二重括弧で検出
_FRAGMENT_VALUES = ("4410.html", "IRW", "EZEO")
_BOILERPLATE_MARKER = "Web page titled"


def _has_symptom(resource: str | None, location: str | None) -> bool:
    if resource in _FRAGMENT_VALUES:
        return True
    if resource and _BOILERPLATE_MARKER in resource:
        return True
    if resource and location:
        for open_p, close_p in (("(", ")"), ("（", "）")):
            if resource.rstrip().endswith(f"{open_p}{location}{close_p}"):
                return True  # 見出しで「(loc)（loc）」になる重複
    return False


def replay_record(record: dict) -> dict:
    """1レコードを再演し、old/newのresource・locationを返す。"""
    desc = ActivityDescription(
        timestamp=VideoTimestamp(seconds=0.0),
        action=record.get("action") or "（記録なし）",
        app_guess=record.get("app_guess"),
        resource=record.get("resource"),
        location=record.get("location"),
        focus=record.get("focus"),
    )
    enriched = enrich_description(desc, ocr_lines=tuple(record.get("ocr", ())))
    return {
        "t": record.get("t"),
        "old_resource": record.get("resource"),
        "new_resource": enriched.resource,
        "old_location": record.get("location"),
        "new_location": enriched.location,
    }


def main(patterns: list[str]) -> int:
    paths = sorted(p for pattern in patterns for p in glob.glob(pattern))
    if not paths:
        print("対象ファイルなし", file=sys.stderr)
        return 1
    changed = 0
    total = 0
    remaining_symptoms = 0
    for path in paths:
        printed_header = False
        for line in open(path, encoding="utf-8"):
            record = json.loads(line)
            total += 1
            result = replay_record(record)
            is_changed = (
                result["old_resource"] != result["new_resource"]
                or result["old_location"] != result["new_location"]
            )
            if _has_symptom(result["new_resource"], result["new_location"]):
                remaining_symptoms += 1
            if is_changed:
                changed += 1
                if not printed_header:
                    print(f"=== {path} ===")
                    printed_header = True
                print(
                    f"  [{result['t']}] resource: {result['old_resource']!r}"
                    f" → {result['new_resource']!r}"
                )
                if result["old_location"] != result["new_location"]:
                    print(
                        f"           location: {result['old_location']!r}"
                        f" → {result['new_location']!r}"
                    )
    print(f"\n合計 {total} エントリ / 変化 {changed} / 症状マーカー残存 {remaining_symptoms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
