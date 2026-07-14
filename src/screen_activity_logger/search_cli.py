"""sal-search CLIエントリポイント（Issue #5）。DI組み立てと表示を担う。"""

from __future__ import annotations

import argparse
from pathlib import Path

from screen_activity_logger.application.search_use_cases import (
    IndexWorklogs,
    SearchWorklogs,
)
from screen_activity_logger.domain.search import SearchHit
from screen_activity_logger.infrastructure.numpy_index import NumpyVectorIndex
from screen_activity_logger.infrastructure.ruri_embedder import (
    DEFAULT_EMBEDDING_MODEL,
    RuriEmbedder,
)
from screen_activity_logger.infrastructure.worklog_reader import (
    read_worklog_records,
)


def build_index_use_case(model: str = DEFAULT_EMBEDDING_MODEL) -> IndexWorklogs:
    return IndexWorklogs(
        embedder=RuriEmbedder(model=model),
        index=NumpyVectorIndex(),
        read_records=read_worklog_records,
        model_name=model,
    )


def build_query_use_case(model: str = DEFAULT_EMBEDDING_MODEL) -> SearchWorklogs:
    return SearchWorklogs(
        embedder=RuriEmbedder(model=model),
        index=NumpyVectorIndex(),
        model_name=model,
    )


def format_hit(rank: int, hit: SearchHit) -> str:
    doc = hit.document
    time_range = doc.t if doc.t_end is None else f"{doc.t}〜{doc.t_end}"
    app = f"  {doc.app_guess}" if doc.app_guess else ""
    return (
        f"{rank}. [{hit.score:.3f}] {time_range}  {doc.source}{app}\n"
        f"   {doc.action}"
    )


def _run_with_friendly_errors(func) -> int:
    """索引未作成・モデル不一致等の想定内エラーをtracebackなしで表示する。"""
    try:
        return func()
    except (FileNotFoundError, ValueError) as error:
        print(f"エラー: {error}", flush=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sal-search",
        description="worklog.jsonlの意味検索（Ruri v3、完全ローカル）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="索引を作成する")
    index_parser.add_argument("jsonl", type=Path, nargs="+", metavar="worklog.jsonl")
    index_parser.add_argument("-o", "--index-dir", type=Path, required=True)
    index_parser.add_argument(
        "--model", default=DEFAULT_EMBEDDING_MODEL,
        help=f"埋め込みモデル（既定: {DEFAULT_EMBEDDING_MODEL}）",
    )

    query_parser = subparsers.add_parser("query", help="意味検索する")
    query_parser.add_argument("text", help="検索クエリ（日本語可）")
    query_parser.add_argument("-i", "--index-dir", type=Path, required=True)
    query_parser.add_argument("-k", type=int, default=5, help="上位件数（既定: 5）")
    query_parser.add_argument(
        "--model", default=DEFAULT_EMBEDDING_MODEL,
        help="クエリ埋め込みモデル（索引作成時と同一である必要あり）",
    )

    args = parser.parse_args(argv)

    if args.command == "index":
        for path in args.jsonl:
            if not path.exists():
                parser.error(f"ファイルが見つかりません: {path}")

        def run_index() -> int:
            count = build_index_use_case(model=args.model).execute(
                args.jsonl, index_dir=args.index_dir
            )
            print(f"索引を作成しました: {count}件 → {args.index_dir}")
            return 0

        return _run_with_friendly_errors(run_index)

    def run_query() -> int:
        hits = build_query_use_case(model=args.model).execute(
            args.text, index_dir=args.index_dir, k=args.k
        )
        if not hits:
            print("該当なし")
            return 0
        for rank, hit in enumerate(hits, start=1):
            print(format_hit(rank, hit))
        return 0

    # 索引未作成・モデル不一致は生tracebackにしない（4AIレビューR3で未配線を検出）
    return _run_with_friendly_errors(run_query)


if __name__ == "__main__":
    raise SystemExit(main())
