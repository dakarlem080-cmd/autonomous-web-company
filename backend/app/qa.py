import asyncio
import json
import subprocess  # nosec B404 - subprocess is used only with fixed, non-shell commands
from pathlib import Path

import httpx

from app.ai_schemas import QAResult


def static_checks(root: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {
        "metadata": (root / "app/layout.tsx").exists(),
        "canonical": False,
        "robots": (root / "app/robots.ts").exists(),
        "sitemap": (root / "app/sitemap.ts").exists(),
    }
    layout = root / "app/layout.tsx"
    if layout.exists():
        checks["canonical"] = "canonical" in layout.read_text(
            encoding="utf-8", errors="replace"
        )
    return checks


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 300):
    try:
        process = subprocess.run(  # nosec B603,B607 - fixed list-form commands; shell execution is disabled
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return process.returncode, (process.stdout + process.stderr)[-12000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def run_qa_sync(root: str, smoke_url: str | None = None) -> QAResult:
    path = Path(root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    executed: list[str] = []
    checks: dict[str, bool] = {}

    if not path.exists():
        return QAResult(passed=False, errors=["workspace_missing"])

    checks.update(static_checks(path))
    executed += list(checks)

    package = path / "package.json"
    if package.exists():
        try:
            data = json.loads(package.read_text())
            scripts = data.get("scripts", {})
            if "build" in scripts:
                code, output = run_cmd(["npm", "run", "build"], path)
                executed.append("npm_build")
                checks["build"] = code == 0
                if code != 0:
                    errors.append("npm_build_failed:" + output[-2000:])
            if "test" in scripts:
                code, output = run_cmd(
                    ["npm", "test", "--", "--runInBand"], path
                )
                executed.append("npm_test")
                checks["tests"] = code == 0
                if code != 0:
                    errors.append("npm_test_failed:" + output[-2000:])
        except Exception as exc:
            errors.append("package_validation:" + str(exc))

    source = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in path.rglob("*.ts")
        if p.is_file()
    )
    checks["basic_secret_scan"] = not any(
        x in source for x in ["-----BEGIN PRIVATE KEY-----", "sk_live_"]
    )
    executed.append("basic_secret_scan")
    if not checks["basic_secret_scan"]:
        errors.append("potential_secret_detected")

    if smoke_url:
        try:
            response = httpx.get(
                smoke_url,
                timeout=20,
                follow_redirects=True,
            )
            checks["http_smoke"] = 200 <= response.status_code < 400
            executed.append("http_smoke")
            if not checks["http_smoke"]:
                errors.append(f"smoke_status:{response.status_code}")
        except Exception as exc:
            checks["http_smoke"] = False
            errors.append("smoke_failed:" + str(exc))

    return QAResult(
        passed=not errors and all(v is not False for v in checks.values()),
        checks=checks,
        errors=errors,
        warnings=warnings,
        executed_checks=executed,
    )


async def run_qa(root: str, smoke_url: str | None = None) -> QAResult:
    return await asyncio.to_thread(run_qa_sync, root, smoke_url)
