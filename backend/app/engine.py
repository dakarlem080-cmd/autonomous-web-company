import json
from pathlib import Path
from app.config import settings
from app.graph import build
from app.integrations import GSC,GA4,GitHub,Vercel
from app.autonomy import AgentRole,AutonomousTask,CompanyLoop
from app.ai_schemas import DecisionSchema
from app.qa import run_qa_sync
from app.tool_registry import default_registry

class Engine:
    def __init__(self):self.graph=build();self.company=CompanyLoop();self.tools=default_registry()
    def opportunities(self,rows):
        out=[]
        for r in rows:
            imp=float(r.get("impressions",0));ctr=float(r.get("ctr",0));pos=float(r.get("position",100))
            if imp<=0:continue
            score=(imp**0.5)*(1+max(0,.08-ctr)*10)*(0.5+max(0,min(1,(20-pos)/16)))
            out.append({"kind":"search","title":" | ".join(r.get("keys",[])),"score":round(score,3),"evidence":r})
        return sorted(out,key=lambda x:x["score"],reverse=True)[:50]
    def website(self,p):
        domain=(p.domain or "").replace("https://","").replace("http://","").rstrip("/");name=p.name.replace('"','');base=f"https://{domain}"
        schema=json.dumps({"@context":"https://schema.org","@type":"WebSite","name":name,"url":base},ensure_ascii=False,separators=(",",":"));schema_literal=json.dumps(schema)
        return {
          "package.json":'{"scripts":{"build":"next build","dev":"next dev","start":"next start"},"dependencies":{"next":"16.0.1","react":"19.1.1","react-dom":"19.1.1"}}',
          "tsconfig.json":'{"compilerOptions":{"target":"ES2020","lib":["dom","es2020"],"strict":true,"jsx":"preserve","module":"esnext","moduleResolution":"bundler","noEmit":true},"include":["**/*.ts","**/*.tsx"]}',
          "app/layout.tsx":f'import type {{Metadata}} from "next";import type {{ReactNode}} from "react";export const metadata:Metadata={{{{metadataBase:new URL("{base}"),title:"{name}",description:"Independent, evidence-backed information about {name}.",alternates:{{{{canonical:"/"}}}},robots:{{{{index:true,follow:true}}}},openGraph:{{{{title:"{name}",url:"/",type:"website"}}}},twitter:{{{{card:"summary_large_image"}}}}}}}};export default function Layout({{children}}:{{{{children:ReactNode}}}}){{{{return <html lang="{p.language}"><body>{{{{children}}}}</body></html>}}}}',
          "app/page.tsx":f'import Link from "next/link";export default function Home(){{return <main><header><h1>{name}</h1><p>Evidence-backed resources, guides and analysis.</p></header><nav><Link href="/articles">Articles</Link> · <Link href="/about">About</Link> · <Link href="/contact">Contact</Link></nav><section><h2>Latest insights</h2><p>Research-backed content will appear here as the autonomous content pipeline publishes it.</p></section><script type="application/ld+json" dangerouslySetInnerHTML={{{{__html:{schema_literal}}}}} /></main>}}',
          "app/articles/page.tsx":'export default function Articles(){return <main><h1>Articles</h1><p>Research-backed articles and practical guides.</p></main>}',
          "app/about/page.tsx":f'export default function About(){{return <main><h1>About</h1><p>{name} publishes independently researched information and transparent sources.</p></main>}}',
          "app/contact/page.tsx":'export default function Contact(){return <main><h1>Contact</h1><p>Use the published contact channel for questions or corrections.</p></main>}',
          "app/robots.ts":f'import type {{MetadataRoute}} from "next";export default function robots():MetadataRoute.Robots{{return {{{{rules:{{{{userAgent:"*",allow:"/"}}}},sitemap:"{base}/sitemap.xml"}}}}}}',
          "app/sitemap.ts":f'import type {{MetadataRoute}} from "next";export default function sitemap():MetadataRoute.Sitemap{{return ["/","/articles","/about","/contact"].map(url=>({{{{url:"{base}"+url,lastModified:new Date()}}}}))}}'
        }
    def provision(self,p):
        s=settings();result={"status":"planned","steps":[]}
        if not s.PROVISIONING_ENABLED:return result
        gh=GitHub();repo_name=(p.repo.split("/",1)[-1] if p.repo else p.domain.replace(".","-"))
        if s.ALLOW_REPO_CREATION and gh.token and gh.owner:
            repo=gh.create_repo(repo_name,f"Autonomous website for {p.domain}");result["github"]=repo;result["steps"].append("github_repo")
            if repo.get("full_name"):
                branch=f"autonomous-{p.id}-initial";gh.branch(branch,gh.client().get_repo(repo["full_name"]));result["github_files"]=gh.files(branch,self.website(p),"Initial autonomous website",gh.client().get_repo(repo["full_name"]))
                if result["github_files"].get("status")=="committed":result["pull_request"]=gh.pr(branch,gh.client().get_repo(repo["full_name"]))
        if s.ALLOW_VERCEL_PROVISIONING and s.VERCEL_TOKEN and result.get("github",{}).get("full_name"):
            v=Vercel();vp=v.create_project(repo_name,result["github"]["full_name"]);result["vercel"]=vp;result["steps"].append("vercel_project")
            if s.ALLOW_DOMAIN_BINDING and vp.get("name"):
                try:result["domain"]=v.add_domain(vp["name"],p.domain);result["steps"].append("domain")
                except Exception as e:result["domain"]={"status":"pending","error":str(e)}
        return result
    def cycle(self,p,oauth=None,site=None,progress=None,agents=None):
        def stage(name):
            if progress:progress(name)
        stage("researching");gsc=GSC(oauth=oauth,site=site);ga4=GA4(oauth=oauth);evidence={"gsc":gsc.query(["query","page"]),"ga4":ga4.report()};ops=self.opportunities(evidence["gsc"])
        stage("planning");brain=self.graph.invoke({"project_id":p.id,"objective":p.goal,"evidence":evidence,"opportunities":ops})
        available={a.get("agent") for a in (agents or [])};developer="developer" in available or not agents
        tasks=[AutonomousTask("Prioritize search opportunities",AgentRole.SEO,"rank queries and pages by growth potential",priority=90,evidence={"count":len(ops)}),AutonomousTask("Implement highest-value changes",AgentRole.DEVELOPER,"apply bounded SEO/content/site changes",priority=80,depends_on=["Prioritize search opportunities"]),AutonomousTask("Measure impact",AgentRole.ANALYST,"compare post-change performance with baseline",priority=70,depends_on=["Implement highest-value changes"])]
        confidence=min(.95,.35+min(len(ops),20)/40);decision=DecisionSchema(action="execute_selected_seo_and_development_tasks",target=str(p.domain),reason="Prioritize evidence-backed opportunities from current search and analytics data.",evidence=ops[:10],expected_impact=min(1,len(ops)/20),confidence=confidence,risk="medium" if developer else "high",reversible=True,approval_required=not developer)
        brain["autonomy"]={"agents":agents or [],"decision":decision.model_dump(),"tasks":[{"title":t.title,"agent":t.agent.value,"objective":t.objective,"priority":t.priority,"depends_on":t.depends_on,"evidence":t.evidence} for t in tasks],"tools":[t.name for t in self.tools.list_allowed([x for a in (agents or []) for x in (a.get("permissions") or [])])]}
        stage("building");files=self.website(p);root=Path(settings().WORKSPACE_ROOT)/str(p.id);root.mkdir(parents=True,exist_ok=True)
        for n,c in files.items():
            x=(root/n).resolve()
            if root.resolve() not in x.parents:raise RuntimeError("path_escape")
            x.parent.mkdir(parents=True,exist_ok=True);x.write_text(c,encoding="utf-8")
        stage("testing");qa=run_qa_sync(str(root));brain["release"]={"status":"dry_run","files":list(files),"tests":qa.model_dump()}
        if not p.dry_run and not settings().AUTONOMY_DRY_RUN:
            if not qa.passed:brain["release"]["status"]="blocked_by_qa";stage("blocked");return brain
            stage("provisioning");brain["provisioning"]=self.provision(p)
            if brain["provisioning"].get("github_files",{}).get("status")=="committed":brain["release"]={"status":"committed","repository":brain["provisioning"].get("github",{}).get("full_name"),"pull_request":brain["provisioning"].get("pull_request"),"tests":qa.model_dump()}
        stage("complete");return brain
