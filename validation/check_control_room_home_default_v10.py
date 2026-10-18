#!/usr/bin/env python3
"""Contract test for the Control Room v10 Home loader (no browser or data mocks)."""
from pathlib import Path

LOADER = Path("site/control-room-preview/index.html")


def main():
    html = LOADER.read_text(encoding="utf-8")
    expected = (
        "window.__GMFQ_ROUTE_QUERY__=(name==='home' && "
        "!new URLSearchParams(query).has('mode')) ? 'mode=live' : query;"
    )
    checks = {
        "32 original payload parts still used": 'Array.from({length:32}' in html,
        "fail closed if preview payload unavailable": 'if(!response.ok)throw new Error' in html,
        "payload integrity kept": 'Controllo integrità dell\'anteprima non superato' in html,
        "unique route marker enforced": 'html.split(routeMarker).length!==2' in html,
        "Home becomes live only absent explicit mode": expected in html,
        "illustrated design remains opt-in": 'mode=design' in html,
        "read-only certified data adapter remains within original pages": "document.write(certifiedDefault)" in html,
        "no manual demo values added": "106.42" not in html,
        "legacy website is not targeted": "website-v1/" not in html,
    }
    for label, ok in checks.items():
        print(f'{"PASS" if ok else "FAIL"}: {label}')
    if not all(checks.values()):
        raise SystemExit(1)
    print("CONTROL_ROOM_V10_HOME_DEFAULT_CONTRACT_PASS")


if __name__ == "__main__":
    main()
