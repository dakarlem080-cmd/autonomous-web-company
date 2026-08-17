from dataclasses import dataclass
from typing import Callable, Any

@dataclass(frozen=True)
class ToolSpec:
    name:str
    permission:str
    description:str
    handler:Callable[...,Any] | None = None
    risk:str="low"
    reversible:bool=True

class ToolRegistry:
    def __init__(self): self._tools:dict[str,ToolSpec]={}
    def register(self,spec:ToolSpec): self._tools[spec.name]=spec
    def get(self,name:str)->ToolSpec:
        if name not in self._tools: raise KeyError(f"tool_not_registered:{name}")
        return self._tools[name]
    def allowed(self,name:str,permissions:list[str])->bool:
        return self.get(name).permission in set(permissions)
    def list_allowed(self,permissions:list[str])->list[ToolSpec]:
        return [x for x in self._tools.values() if x.permission in set(permissions)]
    async def execute(self,name:str,permissions:list[str],**kwargs):
        spec=self.get(name)
        if not self.allowed(name,permissions): raise PermissionError(f"tool_forbidden:{name}")
        if spec.handler is None: raise RuntimeError(f"tool_not_implemented:{name}")
        result=spec.handler(**kwargs)
        if hasattr(result,"__await__"): result=await result
        return result

def default_registry()->ToolRegistry:
    r=ToolRegistry()
    specs=[
      ("search_web","research","Search public web sources"),("crawl_page","research","Fetch and inspect a page"),("crawl_site","research","Crawl allowed site URLs"),
      ("search_console","analyze","Read Search Console metrics"),("get_ga4","analyze","Read Analytics metrics"),("analyze_keywords","analyze","Analyze query opportunities"),
      ("read_github","read","Read repository content"),("write_github","write","Write bounded repository changes", "high"),("create_branch","write","Create isolated branch"),("create_commit","write","Create commit"),("create_pr","write","Create pull request"),
      ("run_tests","test","Run repository tests"),("run_build","test","Run production build"),("run_lighthouse","test","Run Lighthouse checks"),("security_scan","test","Run security checks"),
      ("deploy_vercel","deploy","Deploy preview/production", "high"),("check_deployment","test","Check deployment health"),("rollback_deployment","rollback","Rollback to known-good deployment", "high"),
      ("publish_content","publish","Publish reviewed content", "high")]
    for item in specs:
        name,perm,desc,*risk=item;r.register(ToolSpec(name,perm,desc,risk=risk[0] if risk else "low"))
    return r
