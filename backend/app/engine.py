from pathlib import Path
from datetime import datetime,timezone
from app.config import settings
from app.graph import build
from app.integrations import GSC,GA4,GitHub,Vercel

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
    def website(self,p):
        return {
            "package.json":'{"scripts":{"build":"next build","dev":"next dev","start":"next start"},"dependencies":{"next":"^16.0.0","react":"^19.0.0","react-dom":"^19.0.0"}}',
            "tsconfig.json":'{"compilerOptions":{"target":"ES2020","lib":["dom","es2020"],"strict":true,"jsx":"preserve","module":"esnext","moduleResolution":"bundler","noEmit":true},"include":["**/*.ts","**/*.tsx"]}',
            "app/layout.tsx":f'export default function Layout({children}:{{children:React.ReactNode}}){{return <html lang="{p.language}"><body>{children}</body></html>}}',
            "app/page.tsx":f'export default function Home(){{return <main><h1>{p.name}</h1><p>Independent information website for {p.domain}.</p></main>}}',
            "app/robots.ts":'export default function robots(){return {rules:{userAgent:"*",allow:"/"},sitemap:"/sitemap.xml"}}',
            "app/sitemap.ts":f'export default function sitemap(){{return [{{url:"https://{p.domain}",lastModified:new Date()}}]}}'
        }
    def provision(self,p):
        s=settings(); result={"status":"planned","steps":[]}
        if not s.PROVISIONING_ENABLED:return result
        gh=GitHub(); repo_name=(p.repo.split("/",1)[-1] if p.repo else p.domain.replace(".","-"))
        if s.ALLOW_REPO_CREATION and gh.token and gh.owner:
            repo=gh.create_repo(repo_name,f"Autonomous website for {p.domain}")
            result["github"]=repo;result["steps"].append("github_repo")
            if repo.get("full_name"):
                branch=f"autonomous-{p.id}-initial";gh.branch(branch,gh.client().get_repo(repo["full_name"]))
                result["github_files"]=gh.files(branch,self.website(p),"Initial autonomous website",gh.client().get_repo(repo["full_name"]))
        if s.ALLOW_VERCEL_PROVISIONING and s.VERCEL_TOKEN and result.get("github",{}).get("full_name"):
            v=Vercel();vp=v.create_project(repo_name,result["github"]["full_name"]);result["vercel"]=vp;result["steps"].append("vercel_project")
            if s.ALLOW_DOMAIN_BINDING and vp.get("name"):
                try:result["domain"]=v.add_domain(vp["name"],p.domain);result["steps"].append("domain")
                except Exception as e:result["domain"]={"status":"pending","error":str(e)}
        return result
    def cycle(self,p):
        evidence={"gsc":GSC().query(["query","page"]),"ga4":GA4().report()};ops=self.opportunities(evidence["gsc"])
        brain=self.graph.invoke({"project_id":p.id,"objective":p.goal,"evidence":evidence,"opportunities":ops})
        files=self.website(p);root=Path(settings().WORKSPACE_ROOT)/str(p.id);root.mkdir(parents=True,exist_ok=True)
        for n,c in files.items():
            x=(root/n).resolve()
            if root.resolve() not in x.parents:raise RuntimeError("path escape")
            x.parent.mkdir(parents=True,exist_ok=True);x.write_text(c,encoding="utf-8")
        brain["release"]={"status":"dry_run","files":list(files)}
        if not p.dry_run and not settings().AUTONOMY_DRY_RUN:
            brain["provisioning"]=self.provision(p)
            if brain["provisioning"].get("github_files",{}).get("status")=="committed":brain["release"]={"status":"committed","repository":brain["provisioning"].get("github",{}).get("full_name")}
        return brain
