# Adding a New Monitoring Data Source

Phase 2 deliverable — how to extend monitoring with a fifth source (e.g.
CISA alerts, an internal SIEM feed, a new breach database) without
touching the alert engine, the schema, or the dashboard.

## 1. Add a signal type (if it doesn't fit an existing one)

`app/services/monitoring/types.py` — a plain dataclass. Reuse
`BreachSignal`/`NewsSignal`/etc. where the shape already fits; a genuinely
new *category* of alert (as opposed to a new source of an existing
category) needs a new alert_type in the schema's `alert_type` enum first
(`cve` and `regulatory` are already there, unused, for exactly this).

## 2. Implement the provider interface

`app/services/monitoring/providers.py` defines the ABC your new source
implements (or add a new one if it's a new category). Two implementations:

```python
# mock_providers.py — deterministic, offline, free, default
class MockYourSourceProvider(YourSourceProvider):
    async def check(self, vendor: VendorInfo) -> list[YourSignal]:
        ...

# live_providers.py — real HTTP call
class LiveYourSourceProvider(YourSourceProvider):
    async def check(self, vendor: VendorInfo) -> list[YourSignal]:
        ...
```

Determinism matters for the mock: the alert engine only raises a *new*
alert when there's no already-open one for that vendor+type, so a mock
that returns fresh random data every call will look broken (either
constant duplicate-looking alerts if dedup weren't in place, or — since it
is — a mock whose signal silently changes underneath an already-open alert
without anyone re-evaluating it). Derive mock output from a stable hash of
the vendor id (see `mock_providers._stable_fraction`), not `random`.

## 3. Wire the factory

`app/services/monitoring/factory.py` — add a `get_your_source_provider()`
reading a new `your_source_provider: str = "mock"` setting from
`app/config.py` (plus any API key fields the live implementation needs).

## 4. Register the source row

Add a `(code, name)` tuple to `app/seed/seed_monitoring_sources.py` — this
is what shows up on the Monitoring Status panel and what `source_code`
you'll pass to `alert_engine.raise_alert`.

## 5. Add the check function and wire it into `run_all_checks`

`app/services/monitoring/monitoring_service.py` — a `run_your_source_check`
function following the same shape as the four existing ones (fetch active
vendors, call the provider, decide severity, call `alert_engine.raise_alert`,
update the source's health via `_touch_source`). Add it to `run_all_checks`
and to the `/admin/monitoring/run-checks` response schema
(`app/schemas/monitoring.py`'s `RunChecksOut`).

## 6. Add the DAG

A new file in `airflow_dags/`, same shape as the existing ones — see that
directory's `README.md` for the schedule table and why these aren't
executed in this project's dev environment.

## 7. Test it

- Unit: assert your mock provider is deterministic (same vendor → same
  signal across calls) and that the incident-scenario vendor
  (`primary_domain == mock_providers.INCIDENT_VENDOR_DOMAIN`) produces
  something sensible if relevant to your source.
- If the live implementation calls a real, free, keyless API — write a
  network test like `tests/test_live_providers_network.py`'s, skipped
  automatically when offline rather than left untested.
- Integration: extend `test_full_incident_scenario_end_to_end` (or add a
  sibling) to assert your alert_type shows up in the incident vendor's
  alert set.

Nothing above touches `alert_engine.py`, the dashboard components, or the
schema — the whole point of the provider interface is that a new source is
additive.
