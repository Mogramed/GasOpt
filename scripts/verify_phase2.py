"""Read-only byte regression check against the pre-platform baseline."""
import json
from hashlib import sha256
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'docs/phase3_baseline.json').read_text())
failures = []
for name, expected in manifest['files'].items():
    file = root / name
    actual = sha256(file.read_bytes()).hexdigest().upper() if file.exists() else 'MISSING'
    if actual != expected:
        failures.append(name)
if failures:
    raise SystemExit('Phase 2 baseline differs: ' + ', '.join(failures))
print(f"PASS: {len(manifest['files'])} scientific modules and empirical artifacts unchanged byte-for-byte.")
