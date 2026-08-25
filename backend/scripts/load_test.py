"""Lightweight load test (Phase 5 spec §2d) — concurrent requests against a
*running* backend (`uvicorn app.main:app`), reporting real p50/p95/p99
latency and error rate. Not a mocked benchmark; this hits the actual HTTP
server, actual middleware stack (including rate limiting), and actual
database connection pool.

Deliberately a ~60-line asyncio script rather than pulling in locust/k6:
this project's traffic shape (a few hundred concurrent GRC staff/vendors,
not internet-scale) doesn't need a distributed load-generation framework,
and a script anyone can read top-to-bottom in a minute is worth more here
than a tool with its own learning curve.

Usage:
    uvicorn app.main:app &
    python scripts/load_test.py --endpoint /health/ready --concurrency 50 --requests 500
    python scripts/load_test.py --endpoint /admin/vendors --admin-key dev-admin-key --concurrency 20 --requests 200
"""

import argparse
import asyncio
import time

import httpx


async def _one_request(client: httpx.AsyncClient, endpoint: str) -> tuple[float, int | None]:
    start = time.perf_counter()
    try:
        r = await client.get(endpoint)
        return time.perf_counter() - start, r.status_code
    except httpx.HTTPError:
        return time.perf_counter() - start, None


async def run(base_url: str, endpoint: str, headers: dict, concurrency: int, total_requests: int):
    results: list[tuple[float, int | None]] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30) as client:
        async def bounded():
            async with sem:
                results.append(await _one_request(client, endpoint))

        await asyncio.gather(*(bounded() for _ in range(total_requests)))
    return results


def _percentile(data: list[float], p: float) -> float:
    data = sorted(data)
    idx = min(int(len(data) * p), len(data) - 1)
    return data[idx]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/health/ready")
    parser.add_argument("--admin-key", default=None)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--requests", type=int, default=500)
    args = parser.parse_args()

    headers = {"X-Admin-Key": args.admin_key} if args.admin_key else {}
    started = time.perf_counter()
    results = asyncio.run(run(args.base_url, args.endpoint, headers, args.concurrency, args.requests))
    wall_clock = time.perf_counter() - started

    latencies = [r[0] for r in results]
    statuses = [r[1] for r in results]
    ok = sum(1 for s in statuses if s == 200)
    rate_limited = sum(1 for s in statuses if s == 429)
    other_errors = len(results) - ok - rate_limited

    print(f"Endpoint:        {args.endpoint}")
    print(f"Total requests:  {len(results)}  (concurrency={args.concurrency})")
    print(f"Wall clock:      {wall_clock:.2f}s  ({len(results) / wall_clock:.1f} req/s)")
    print(f"200 OK:          {ok} ({ok / len(results) * 100:.1f}%)")
    print(f"429 rate-limited:{rate_limited} ({rate_limited / len(results) * 100:.1f}%)")
    print(f"Other errors:    {other_errors}")
    print(f"Latency (ms):    p50={_percentile(latencies, 0.5) * 1000:.1f}  "
          f"p95={_percentile(latencies, 0.95) * 1000:.1f}  "
          f"p99={_percentile(latencies, 0.99) * 1000:.1f}  "
          f"max={max(latencies) * 1000:.1f}")


if __name__ == "__main__":
    main()
