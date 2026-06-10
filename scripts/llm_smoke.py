"""Live smoke test for every configured LLM provider.

Calls each provider in the fallback chain once with a tiny JSON prompt and
reports latency + response validity. Run with: poetry run python scripts/llm_smoke.py

Options:
    --chain      also test the assembled interactive/background chain clients
    --provider X test a single provider only (e.g. --provider mistral)
"""

import argparse
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")

from app.llm import client_factory as factory  # noqa: E402

SYSTEM = "You are a test probe. Respond with valid JSON only."
USER = 'Reply with exactly this JSON: {"status": "ok"}'

ALL_PROVIDERS = ["groq", "groq_small", "gemini", "cerebras", "nvidia", "mistral", "openrouter", "llm7", "zai"]


async def probe(name: str, client) -> bool:
    start = time.perf_counter()
    try:
        raw = await asyncio.wait_for(client.complete_json(SYSTEM, USER), timeout=60)
        elapsed = time.perf_counter() - start
        try:
            json.loads(raw)
            print(f"  PASS  {name:<12} {elapsed:6.2f}s  valid JSON")
            return True
        except json.JSONDecodeError:
            print(f"  WARN  {name:<12} {elapsed:6.2f}s  responded but invalid JSON: {raw[:80]!r}")
            return False
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"  FAIL  {name:<12} {elapsed:6.2f}s  {type(e).__name__}: {str(e)[:120]}")
        return False


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", action="store_true")
    parser.add_argument("--provider")
    args = parser.parse_args()

    providers = [args.provider] if args.provider else ALL_PROVIDERS
    results = {}

    print("Per-provider probes (only configured providers are built):")
    for name in providers:
        leaf = factory._build_leaf(name)
        if leaf is None:
            print(f"  SKIP  {name:<12}         not configured")
            continue
        results[name] = await probe(name, leaf)

    if args.chain:
        print("\nAssembled chain clients:")
        for profile in ("interactive", "background"):
            client = factory.LLMClientFactory.create(profile)
            results[f"chain:{profile}"] = await probe(f"chain:{profile}", client)

    failed = [k for k, ok in results.items() if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f" — failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
