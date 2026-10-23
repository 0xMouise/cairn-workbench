"""Publish the reviewed open-source fork/preview using Git Credential Manager.

Credentials stay in memory and are never written into Git remotes or log output.
"""

import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent.parent


def client():
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    values = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    if not values.get("password"):
        raise RuntimeError("No authenticated GitHub credential is available")
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": "Bearer " + values["password"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def check(response):
    if not response.ok:
        raise RuntimeError(
            f"GitHub HTTP {response.status_code}: "
            + response.json().get("message", "request failed")
        )
    return response.json()


def prepare(session):
    user = check(session.get("https://api.github.com/user", timeout=20))["login"]
    if user.lower() != "0xmouise":
        raise RuntimeError(
            "Unexpected GitHub account; refusing to publish to another account"
        )
    repo = f"{user}/cairn-workbench"
    url = "https://api.github.com/repos/" + repo
    existing = session.get(url, timeout=20)
    if existing.status_code == 404:
        check(
            session.post(
                "https://api.github.com/repos/oritera/Cairn/forks",
                json={"name": "cairn-workbench", "default_branch_only": True},
                timeout=30,
            )
        )
        for _ in range(15):
            existing = session.get(url, timeout=10)
            if existing.ok:
                break
            time.sleep(1)
    data = check(existing)
    if data.get("parent", {}).get("full_name", "").lower() != "oritera/cairn":
        raise RuntimeError(
            "Target repository exists but is not the expected Cairn fork"
        )
    print("Prepared https://github.com/" + repo)
    return repo


def release(session, repo, files):
    version = json.loads((ROOT / "web/package.json").read_text(encoding="utf8"))["version"]
    tag = f"v{version}-workbench-preview"
    base = "https://api.github.com/repos/" + repo
    result = session.get(base + "/releases/tags/" + tag, timeout=20)
    if result.status_code == 404:
        result = session.post(
            base + "/releases",
            json={
                "tag_name": tag,
                "target_commitish": "workbench",
                "name": f"Cairn Workbench {version} Preview",
                "body": (ROOT / f"docs/RELEASE_NOTES_{version}.md").read_text(
                    encoding="utf8"
                ),
                "prerelease": True,
                "draft": False,
            },
            timeout=30,
        )
    data = check(result)
    uploaded = {asset["name"] for asset in data.get("assets", [])}
    for file in files:
        path = Path(file)
        if path.name in uploaded:
            raise RuntimeError(
                "Refusing to overwrite existing release asset " + path.name
            )
        with path.open("rb") as handle:
            check(
                session.post(
                    data["upload_url"].split("{")[0] + "?name=" + quote(path.name),
                    data=handle,
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(path.stat().st_size),
                    },
                    timeout=180,
                )
            )
        print("Uploaded", path.name)
    print(data["html_url"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--release", nargs="*")
    args = parser.parse_args()
    session = client()
    repo = prepare(session)
    if args.release is not None:
        release(session, repo, args.release)
