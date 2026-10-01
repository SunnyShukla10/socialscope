"""Read-only checks. Run with Python 3 on the machine hosting Docker."""

from pathlib import Path
import subprocess
import sys
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def published_url(service, container_port):
    result = subprocess.run(
        ["docker", "compose", "port", service, str(container_port)],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=True,
    )
    address = result.stdout.strip().splitlines()[0]
    port = int(address.rsplit(":", 1)[1])
    return f"http://127.0.0.1:{port}"


def probe(label, url, expect_json=False):
    try:
        # Host-local checks should not be sent to an environment HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=10) as response:
            if expect_json:
                import json
                json.loads(response.read())
            print(f"PASS {label}: HTTP {response.status} {url}")
        return True
    except Exception as error:
        print(f"FAIL {label}: {url} ({error})")
        return False


def main():
    urls = {}
    for service, port in (("frontend", 3001), ("backend", 8001)):
        try:
            urls[service] = published_url(service, port)
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
            print(f"FAIL Cannot resolve {service} published port: {error}")
    checks = []
    if "frontend" in urls:
        web = urls["frontend"]
        checks.append(probe("Frontend", web + "/login"))
        checks.append(probe("Frontend-to-backend proxy", web + "/api/health", True))
        print(f"App: {web}/")
    if "backend" in urls:
        api = urls["backend"]
        checks.append(probe("Backend", api + "/api/health", True))
        print(f"API docs: {api}/api/docs")
    success = len(urls) == 2 and all(checks)
    if success:
        print("Host checks passed. If the browser still fails, check VS Code's Ports panel.")
    print("On a VM, forward the published ports and use the Ports panel's Forwarded Address.")
    print("These checks do not test the SSH tunnel or the browser on your computer.")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
