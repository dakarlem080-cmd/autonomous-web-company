import asyncio
import json
from pathlib import Path
from urllib.parse import urljoin
import httpx
from app.ai_schemas import QAResult

async def _run(cmd:list[str], cwd:Path, timeout:int=300):
    try:
        p=await asyncio.create_subprocess_exec(*cmd,cwd=str(cwd),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        out,_=await asyncio.wait_for(p.communicate(),timeout=timeout)
        return p.returncode,out.decode(errors="replace")[-12000:]
    except asyncio.TimeoutError:
        p.kill();return 124,"timeout"

def static_checks(root:Path)->dict:
    checks={"metadata":(root/"app/layout.tsx").exists(),"canonical":False,"robots":(root/"app/robots.ts").exists(),"sitemap":(root/"app/sitemap.ts").exists()}
    layout=root/"app/layout.tsx"
    if layout.exists():
        text=layout.read_text(encoding="utf-8",errors="replace");checks["canonical"]="canonical" in text
    return checks

async def run_qa(root:str, smoke_url:str|None=None)->QAResult:
    path=Path(root).resolve(); errors=[];warnings=[];executed=[];checks={}
    if not path.exists():return QAResult(passed=False,checks={},errors=["workspace_missing"],executed_checks=[])
    checks.update(static_checks(path));executed += ["metadata","canonical","robots","sitemap"]
    pkg=path/"package.json"
    if pkg.exists():
        try:
            data=json.loads(pkg.read_text()); scripts=data.get("scripts",{})
            if "build" in scripts:
                code,out=await _run(["npm","run","build"],path);executed.append("npm_build");checks["build"]=code==0
                if code!=0:errors.append("npm_build_failed:"+out[-2000:])
            if "test" in scripts:
                code,out=await _run(["npm","test","--","--runInBand"],path);executed.append("npm_test");checks["tests"]=code==0
                if code!=0:errors.append("npm_test_failed:"+out[-2000:])
        except Exception as exc:errors.append("package_validation:"+str(exc))
    forbidden=["eval(","new Function(","sk_live_","-----BEGIN PRIVATE KEY-----"]
    text="\n".join(p.read_text(encoding="utf-8",errors="replace") for p in path.rglob("*.ts") if p.is_file())
    checks["basic_secret_scan"]=not any(x in text for x in forbidden);executed.append("basic_secret_scan")
    if not checks["basic_secret_scan"]:errors.append("potential_secret_or_dynamic_code")
    if smoke_url:
        try:
            async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
                r=await client.get(smoke_url);checks["http_smoke"]=200<=r.status_code<400;executed.append("http_smoke")
                if not checks["http_smoke"]:errors.append(f"smoke_status:{r.status_code}")
        except Exception as exc:checks["http_smoke"]=False;errors.append("smoke_failed:"+str(exc))
    passed=not errors and all(v is not False for v in checks.values())
    return QAResult(passed=passed,checks=checks,errors=errors,warnings=warnings,executed_checks=executed)
