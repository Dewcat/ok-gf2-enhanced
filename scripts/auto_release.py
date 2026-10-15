"""Plan a stable release; --publish creates the tag and dispatches the build."""

import argparse
import json
import os
import re
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def stable_tags(tags):
    return sorted(
        (tag for tag in tags if re.fullmatch(r"v\d+\.\d+\.\d+", tag)),
        key=lambda tag: tuple(map(int, tag[1:].split("."))),
    )


def next_version(tag):
    major, minor, patch = map(int, tag[1:].split("."))
    return f"v{major}.{minor + 1}.0" if patch >= 99 else f"v{major}.{minor}.{patch + 1}"


def watched_paths():
    with open("deploy.txt", encoding="utf-8-sig") as source:
        paths = list(dict.fromkeys(line.strip() for line in source if line.strip()))
    paths += ["scripts/release_launcher.py", ".github/actions/pyappify", ".github/workflows/build.yml", "icons", "setup.py", "deploy.txt"]
    paths += [":(top,exclude)assets/downloads.svg"]
    paths += [f":(top,glob,icase,exclude)**/*.{ext}" for ext in ("md", "markdown", "rst", "adoc")]
    return paths


def complete_release(release):
    names = {asset["name"] for asset in release.get("assets", [])}
    tag = release["tag_name"]
    return not release["draft"] and not release.get("prerelease", False) and {
        f"ok-gf2-win32-dewcat-setup-{tag}.exe",
        f"ok-gf2-win32-online-setup-{tag}.exe",
        "SHA256SUMS.txt", "launcher-manifest.json",
        f"ok-gf2-win32-{tag}.zip", f"win32_sha256-{tag}.txt",
    } <= names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    repo = os.environ["GITHUB_REPOSITORY"]
    if repo != "Dewcat/ok-gf2-enhanced":
        raise RuntimeError("Auto release is restricted to Dewcat/ok-gf2-enhanced")
    tags = stable_tags(run("git", "tag", "--merged", "HEAD").splitlines())
    last = tags[-1] if tags else None
    # API errors must abort, never masquerade as a missing release.
    pages = json.loads(run("gh", "api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
    releases = {r["tag_name"]: r for page in pages for r in page}
    retry = last and (last not in releases or not complete_release(releases[last]))
    if retry:
        tag = last
    else:
        revision = f"{last}..HEAD" if last else "HEAD"
        if not run("git", "log", "-1", "--format=%H", revision, "--", *watched_paths()):
            print("No release-relevant changes; skip.")
            return
        tag = next_version(last) if last else "v0.0.1"
    print(f"{'Retry' if retry else 'Create'} release {tag}")
    if not args.publish:
        return
    runs = json.loads(run("gh", "api", f"repos/{repo}/actions/workflows/build.yml/runs?per_page=100"))["workflow_runs"]
    if any(r["status"] != "completed" and r["head_branch"] == tag for r in runs):
        print(f"Build for {tag} is already active; skip.")
        return
    if not retry:
        # Tag the checked-out default branch head, including current build fixes.
        run("git", "tag", tag, "HEAD")
        run("git", "push", "origin", f"refs/tags/{tag}")
    # GITHUB_TOKEN tag pushes do not start push workflows. Dispatch explicitly
    # on the tag so the existing build uses the correct ref and release gate.
    run("gh", "workflow", "run", "build.yml", "--repo", repo, "--ref", tag)
    print(f"Dispatched build for {tag}")


if __name__ == "__main__":
    main()
