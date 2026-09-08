# Contributing

Contributions that make session parsing, provenance or local search more reliable are welcome.

## Development

Use Python 3.11+ with SQLite FTS5. The runtime has no third-party dependencies.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/demo.py
```

Tests and the demo use temporary, synthetic sessions. Do not use your real conversation history as a fixture or paste it into issues. For a new adapter format, reduce the shape to a fabricated example and add an extraction/exclusion test. User-visible text, stable provenance and source preservation matter more than importing every event.

Keep tool results, system/developer messages and reasoning blocks out of the visible-message index. A new source integration must stay explicit and local. Do not add telemetry, model calls or upload defaults.

Open a focused pull request describing the actual behavior and verification. Security reports belong in the private reporting channel described in [SECURITY.md](SECURITY.md).
