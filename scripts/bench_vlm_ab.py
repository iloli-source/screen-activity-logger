"""VLMバックエンドのA/B交互ベンチマーク（Issue #8）。

ABBA順×Nブロックで熱ドリフトを相殺し、ペア比の中央値で比較する。
A=Ollama(qwen3-vl:8b)、B=vllm-mlx(OpenAI互換、Qwen3-VL-8B-4bit)。
固定セット（/tmp/sal-issue8-bench/bench_set.json）を両者に同一入力。

使い方:
    python scripts/bench_vlm_ab.py [--blocks 3] [--vllm-port 8991]
"""

from __future__ import annotations

import argparse
import base64
import json
import statistics
import time
from pathlib import Path

import httpx

_BENCH_SET = Path("/tmp/sal-issue8-bench/bench_set.json")
_TIMEOUT = 600.0


def call_ollama(item: dict) -> tuple[float, str]:
    start = time.monotonic()
    response = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen3-vl:8b",
            "messages": [
                {
                    "role": "user",
                    "content": item["prompt"],
                    "images": [base64.b64encode(
                        Path(item["png"]).read_bytes()
                    ).decode()],
                }
            ],
            "stream": False,
            "think": False,
            "options": {"num_ctx": 8192, "temperature": 0},
            "keep_alive": "30m",
        },
        timeout=_TIMEOUT,
    )
    elapsed = time.monotonic() - start
    return elapsed, response.json()["message"]["content"]


def call_vllm(item: dict, port: int) -> tuple[float, str]:
    image_b64 = base64.b64encode(Path(item["png"]).read_bytes()).decode()
    start = time.monotonic()
    response = httpx.post(
        f"http://localhost:{port}/v1/chat/completions",
        json={
            "model": "mlx-community/Qwen3-VL-8B-Instruct-4bit",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": item["prompt"]},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 512,
        },
        timeout=_TIMEOUT,
    )
    elapsed = time.monotonic() - start
    return elapsed, response.json()["choices"][0]["message"]["content"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--vllm-port", type=int, default=8991)
    parser.add_argument("--mode", choices=["ab", "cache"], default="ab")
    args = parser.parse_args()

    bench_set = json.loads(_BENCH_SET.read_text(encoding="utf-8"))

    if args.mode == "cache":
        # V2: 同一フレーム再送×5（vllm-mlxのcache効果）
        item = bench_set[0]
        for i in range(5):
            elapsed, _ = call_vllm(item, args.vllm_port)
            print(f"再送{i+1}: {elapsed:.1f}s")
        # V3: 類似フレーム列（隣接、非同一ピクセル）
        print("--- 類似フレーム列 ---")
        for i, item in enumerate(bench_set):
            elapsed, _ = call_vllm(item, args.vllm_port)
            print(f"frame{i}: {elapsed:.1f}s")
        return 0

    ratios: list[float] = []
    outputs: dict = {"ollama": [], "vllm": []}
    for block in range(args.blocks):
        for item_index, item in enumerate(bench_set):
            # ABBA: ペア内で順序を反転して熱ドリフトを相殺
            a1, out_a1 = call_ollama(item)
            b1, out_b1 = call_vllm(item, args.vllm_port)
            b2, _ = call_vllm(item, args.vllm_port)
            a2, _ = call_ollama(item)
            t_a, t_b = (a1 + a2) / 2, (b1 + b2) / 2
            ratios.append(t_a / t_b)
            outputs["ollama"].append(out_a1)
            outputs["vllm"].append(out_b1)
            print(
                f"block{block} frame{item_index}: "
                f"A={t_a:.1f}s B={t_b:.1f}s ratio={t_a/t_b:.2f}"
            )
    print(f"\n比の中央値（A/B, >1でvllm-mlxが速い）: {statistics.median(ratios):.2f}")
    Path("/tmp/sal-issue8-bench/outputs.json").write_text(
        json.dumps(outputs, ensure_ascii=False), encoding="utf-8"
    )
    print("出力品質評価用: /tmp/sal-issue8-bench/outputs.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
