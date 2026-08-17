from dataclasses import dataclass
from typing import Callable,Any
@dataclass(frozen=True)
class ToolSpec:
    name:str;permission:str;description:str;handler:Callable[...,Any]|None=None;risk:str="low";reversible:bool=True
class ToolRegistry:
    def __init__(self):self._tools:dict[str,ToolSpec]={}
    def register(self,spec:ToolSpec):self._tools[spec.name]=spec
    def get(self,name:str)->ToolSpec:
        if name not in self._tools:raise KeyError(f"tool_not_registered:{name}")
        return self._tools[name]
    def allowed(self,name,permissions):return self.get(name).permission in set(permissions)
    def list_allowed(self,permissions):return [x for x in self._tools.values() if x.permission in set(permissions)]
    async def execute(self,name,permissions,**kwargs):
        spec=self.get(name)
        if not self.allowed(name,permissions):raise PermissionError(f"tool_forbidden:{name}")
        if spec.handler is None:raise RuntimeError(f"tool_not_implemented:{name}")
        result=spec.handler(**kwargs);return await result if hasattr(result,"__await__") else result

def default_registry():
    from app.integrations import GSC,GA4,GitHub,Vercel
    import httpx
    from pathlib import Path
    from app.qa import run_qa_sync,run_cmd
    r=ToolRegistry()
    r.register(ToolSpec("search_console","analyze","Read project Search Console",lambda oauth,site:GSC(oauth=oauth,site=site).query(["query","page"])))
    r.register(ToolSpec("get_ga4","analyze","Read project Analytics",lambda oauth:GA4(oauth=oauth).report()))
    r.register(ToolSpec("read_github","read","Read project GitHub",lambda credentials:GitHub(credentials).test()))
    r.register(ToolSpec("write_github","write","Create a private project repository",lambda credentials,name,description:GitHub(credentials).create_repo(name,description),risk="high"))
    r.register(ToolSpec("create_branch","write","Create isolated branch",lambda credentials,name:GitHub(credentials).branch(name)))
    r.register(ToolSpec("create_commit","write","Create bounded commit",lambda credentials,branch,files,message:GitHub(credentials).files(branch,files,message),risk="high"))
    r.register(ToolSpec("create_pr","write","Create pull request",lambda credentials,branch:GitHub(credentials).pr(branch),risk="high"))
    r.register(ToolSpec("deploy_vercel","deploy","Deploy with project Vercel credentials",lambda credentials,project:Vercel(credentials).deploy(project),risk="high"))
    r.register(ToolSpec("check_deployment","test","Inspect Vercel deployment",lambda credentials,deployment_id:Vercel(credentials).request("GET",f"/v13/deployments/{deployment_id}")))
    r.register(ToolSpec("rollback_deployment","rollback","Promote a known-good deployment",lambda credentials,project_id,deployment_id:Vercel(credentials).request("POST",f"/v10/projects/{project_id}/promote/{deployment_id}"),risk="high"))
    r.register(ToolSpec("crawl_page","research","Fetch a public page",lambda url:httpx.get(url,timeout=20,follow_redirects=True).text[:50000]))
    r.register(ToolSpec("crawl_site","research","Fetch a bounded sitemap",lambda url:httpx.get(url,timeout=20,follow_redirects=True).text[:50000]))
    r.register(ToolSpec("analyze_keywords","analyze","Rank Search Console rows",lambda rows:sorted(rows,key=lambda x:float(x.get("impressions",0)),reverse=True)[:100]))
    r.register(ToolSpec("run_tests","test","Run executable QA checks",lambda root:run_qa_sync(root).model_dump()))
    r.register(ToolSpec("run_build","test","Run the production build",lambda root:run_cmd(["npm","run","build"],Path(root))))
    r.register(ToolSpec("run_lighthouse","test","Run Lighthouse only when the binary is installed",lambda url:run_cmd(["npx","--no-install","lighthouse",url,"--output=json","--quiet"],Path.cwd())))
    r.register(ToolSpec("security_scan","test","Run executable QA security checks",lambda root:run_qa_sync(root).model_dump()))
    r.register(ToolSpec("publish_content","publish","Content publishing requires a project adapter",risk="high"))
    r.register(ToolSpec("search_web","research","Web search adapter must be configured by worker"))
    return r
