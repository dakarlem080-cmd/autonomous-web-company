from pathlib import Path
from datetime import datetime,timezone
from app.config import settings
from app.graph import build
from app.integrations import GSC,GA4,GitHub
class Engine:
    def __init__(self):self.graph=build()
    def opportunities(self,rows):
        out=[]
        for r in rows:
            imp=float(r.get("impressions",0));ctr=float(r.get("ctr",0));pos=float(r.get("position",100))
            if imp<=0:continue
            score=(imp**0.5)*(1+max(0,.08-ctr)*10)*(0.5+max(0,min(1,(20-pos)/16)))
            out.append({"kind":"search","title":" | ".join(r.get("keys",[])),"score":round(score,3),"evidence":r})
        return sorted(out,key=lambda x:x["score"],reverse=True)[:50]
    def website(self,p):return {"package.json":'{"scripts":{"build":"next build","dev":"next dev","start":"next start"},"dependencies":{"next":"^16.0.0","react":"^19.0.0","react-dom":"^19.0.0"}}',"app/page.tsx":f'export default function Home(){{return <main><h1>{p.name}</h1><p>Autonomous website.</p></main>}}',"app/robots.ts":'export default function robots(){return {rules:{userAgent:"*",allow:"/"},sitemap:"/sitemap.xml"}}',"app/sitemap.ts":f'export default function sitemap(){{return [{{url:"https://{p.domain}",lastModified:new Date()}}]}}'}
    def cycle(self,p):
        evidence={"gsc":GSC().query(["query","page"]),"ga4":GA4().report()};ops=self.opportunities(evidence["gsc"]);brain=self.graph.invoke({"project_id":p.id,"objective":p.goal,"evidence":evidence,"opportunities":ops})
        files=self.website(p);root=Path(settings().WORKSPACE_ROOT)/str(p.id);root.mkdir(parents=True,exist_ok=True)
        for n,c in files.items():
            x=(root/n).resolve()
            if root.resolve() not in x.parents:raise RuntimeError("path escape")
            x.parent.mkdir(parents=True,exist_ok=True);x.write_text(c,encoding="utf-8")
        brain["release"]={"status":"dry_run","files":list(files)}
        if p.dry_run or settings().AUTONOMY_DRY_RUN:return brain
        branch=f"autonomous-{p.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}";gh=GitHub();gh.branch(branch);commit=gh.files(branch,files,"autonomous website update");brain["release"]={"commit":commit,"pull_request":gh.pr(branch)};return brain
