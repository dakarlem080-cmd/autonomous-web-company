import json
from pathlib import Path

from app.ai_schemas import DecisionSchema
from app.autonomy import AgentRole, AutonomousTask, CompanyLoop
from app.config import settings
from app.graph import build
from app.integrations import GA4, GSC, GitHub, Vercel
from app.qa import run_qa_sync
from app.tool_registry import default_registry


class Engine:
    def __init__(self):
        self.graph = build()
        self.company = CompanyLoop()
        self.tools = default_registry()

    def opportunities(self, rows):
        opportunities = []
        for row in rows:
            impressions = float(row.get("impressions", 0))
            ctr = float(row.get("ctr", 0))
            position = float(row.get("position", 100))
            if impressions <= 0:
                continue
            score = (impressions**0.5) * (
                1 + max(0, 0.08 - ctr) * 10
            ) * (0.5 + max(0, min(1, (20 - position) / 16)))
            opportunities.append(
                {
                    "kind": "search",
                    "title": " | ".join(row.get("keys", [])),
                    "score": round(score, 3),
                    "evidence": row,
                }
            )
        return sorted(
            opportunities,
            key=lambda item: item["score"],
            reverse=True,
        )[:50]

    def website(self, project):
        domain = (
            (project.domain or "")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
        name = project.name.replace('"', "")
        base = f"https://{domain}"
        schema = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": name,
                "url": base,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        schema_literal = json.dumps(schema)
        layout = (
            'import type { Metadata } from "next";\n'
            'import type { ReactNode } from "react";\n'
            f'export const metadata: Metadata = {{ metadataBase: new URL("{base}"), '
            f'title: "{name}", description: "Independent, evidence-backed information about {name}", '
            'alternates: { canonical: "/" }, robots: { index: true, follow: true }, '
            f'openGraph: {{ title: "{name}", url: "/", type: "website" }}, '
            'twitter: { card: "summary_large_image" } };\n'
            f'export default function Layout({{ children }}: {{ children: ReactNode }}) {{ '
            f'return <html lang="{project.language}"><body>{{children}}</body></html> }}'
        )
        home = (
            'import Link from "next/link";\n'
            f'export default function Home(){{return <main><header><h1>{name}</h1>'
            '<p>Evidence-backed resources, guides and analysis.</p></header>'
            '<nav><Link href="/articles">Articles</Link> · '
            '<Link href="/about">About</Link> · <Link href="/contact">Contact</Link></nav>'
            '<section><h2>Latest insights</h2><p>Research-backed content will appear here as the autonomous content pipeline publishes it.</p></section>'
            f'<script type="application/ld+json" dangerouslySetInnerHTML={{{{__html:{schema_literal}}}}} /></main>}}'
        )
        return {
            "package.json": json.dumps(
                {
                    "scripts": {
                        "build": "next build",
                        "dev": "next dev",
                        "start": "next start",
                    },
                    "dependencies": {
                        "next": "16.3.1",
                        "react": "19.1.1",
                        "react-dom": "19.1.1",
                    },
                }
            ),
            "tsconfig.json": json.dumps(
                {
                    "compilerOptions": {
                        "target": "ES2020",
                        "lib": ["dom", "es2020"],
                        "strict": True,
                        "jsx": "preserve",
                        "module": "esnext",
                        "moduleResolution": "bundler",
                        "noEmit": True,
                    },
                    "include": ["**/*.ts", "**/*.tsx"],
                }
            ),
            "app/layout.tsx": layout,
            "app/page.tsx": home,
            "app/articles/page.tsx": (
                'export default function Articles(){return <main><h1>Articles</h1>'
                '<p>Research-backed articles and practical guides.</p></main>}'
            ),
            "app/about/page.tsx": (
                'export default function About(){return <main><h1>About</h1>'
                f'<p>{name} publishes independently researched information and transparent sources.</p></main>}'
            ),
            "app/contact/page.tsx": (
                'export default function Contact(){return <main><h1>Contact</h1>'
                '<p>Use the published contact channel for questions or corrections.</p></main>}'
            ),
            "app/robots.ts": (
                'import type { MetadataRoute } from "next"; '
                'export default function robots(): MetadataRoute.Robots { '
                f'return {{ rules: {{ userAgent: "*", allow: "/" }}, sitemap: "{base}/sitemap.xml" }}; }}'
            ),
            "app/sitemap.ts": (
                'import type { MetadataRoute } from "next"; '
                'export default function sitemap(): MetadataRoute.Sitemap { '
                f'return ["/","/articles","/about","/contact"].map(url => ({{ url: "{base}" + url, lastModified: new Date() }})); }}'
            ),
        }

    def provision(self, project, credentials=None):
        settings_obj = settings()
        result = {"status": "planned", "steps": []}
        if not settings_obj.PROVISIONING_ENABLED:
            return result

        credentials = credentials or {}
        github = GitHub(
            credentials.get("github_oauth") or credentials.get("github") or {}
        )
        repo_name = (
            project.repo.split("/", 1)[-1]
            if project.repo
            else project.domain.replace(".", "-")
        )
        if settings_obj.ALLOW_REPO_CREATION and github.token and github.owner:
            repo = github.create_repo(
                repo_name,
                f"Autonomous website for {project.domain}",
            )
            result["github"] = repo
            result["steps"].append("github_repo")
            if repo.get("full_name"):
                branch = f"autonomous-{project.id}-initial"
                repository = github.client().get_repo(repo["full_name"])
                github.branch(branch, repository)
                result["github_files"] = github.files(
                    branch,
                    self.website(project),
                    "Initial autonomous website",
                    repository,
                )
                if result["github_files"].get("status") == "committed":
                    result["pull_request"] = github.pr(branch, repository)

        vercel_credentials = (
            credentials.get("vercel_oauth") or credentials.get("vercel") or {}
        )
        vercel = Vercel(vercel_credentials)
        if (
            settings_obj.ALLOW_VERCEL_PROVISIONING
            and vercel.token
            and result.get("github", {}).get("full_name")
        ):
            vercel_project = vercel.create_project(
                repo_name,
                result["github"]["full_name"],
            )
            result["vercel"] = vercel_project
            result["steps"].append("vercel_project")
            if settings_obj.ALLOW_DOMAIN_BINDING and vercel_project.get("name"):
                try:
                    result["domain"] = vercel.add_domain(
                        vercel_project["name"],
                        project.domain,
                    )
                    result["steps"].append("domain")
                except Exception as exc:
                    result["domain"] = {
                        "status": "pending",
                        "error": str(exc),
                    }
        return result

    def cycle(
        self,
        project,
        oauth=None,
        site=None,
        progress=None,
        agents=None,
        credentials=None,
    ):
        def stage(name):
            if progress:
                progress(name)

        stage("researching")
        gsc = GSC(oauth=oauth, site=site)
        ga4 = GA4(oauth=oauth)
        evidence = {
            "gsc": gsc.query(["query", "page"]),
            "ga4": ga4.report(),
        }
        opportunities = self.opportunities(evidence["gsc"])

        stage("planning")
        brain = self.graph.invoke(
            {
                "project_id": project.id,
                "objective": project.goal,
                "evidence": evidence,
                "opportunities": opportunities,
            }
        )
        available = {agent.get("agent") for agent in (agents or [])}
        developer_enabled = "developer" in available or not agents
        tasks = [
            AutonomousTask(
                "Prioritize search opportunities",
                AgentRole.SEO,
                "rank queries and pages by growth potential",
                priority=90,
                evidence={"count": len(opportunities)},
            ),
            AutonomousTask(
                "Implement highest-value changes",
                AgentRole.DEVELOPER,
                "apply bounded SEO/content/site changes",
                priority=80,
                depends_on=["Prioritize search opportunities"],
            ),
            AutonomousTask(
                "Measure impact",
                AgentRole.ANALYST,
                "compare post-change performance with baseline",
                priority=70,
                depends_on=["Implement highest-value changes"],
            ),
        ]
        confidence = min(0.95, 0.35 + min(len(opportunities), 20) / 40)
        decision = DecisionSchema(
            action="execute_selected_seo_and_development_tasks",
            target=str(project.domain),
            reason="Prioritize evidence-backed opportunities from current search and analytics data.",
            evidence=opportunities[:10],
            expected_impact=min(1, len(opportunities) / 20),
            confidence=confidence,
            risk="medium" if developer_enabled else "high",
            reversible=True,
            approval_required=not developer_enabled,
        )
        brain["autonomy"] = {
            "agents": agents or [],
            "decision": decision.model_dump(),
            "tasks": [
                {
                    "title": task.title,
                    "agent": task.agent.value,
                    "objective": task.objective,
                    "priority": task.priority,
                    "depends_on": task.depends_on,
                    "evidence": task.evidence,
                }
                for task in tasks
            ],
            "tools": [
                tool.name
                for tool in self.tools.list_allowed(
                    [
                        permission
                        for agent in (agents or [])
                        for permission in (agent.get("permissions") or [])
                    ]
                )
            ],
        }

        stage("building")
        files = self.website(project)
        root = Path(settings().WORKSPACE_ROOT) / str(project.id)
        root.mkdir(parents=True, exist_ok=True)
        root_resolved = root.resolve()
        for name, content in files.items():
            destination = (root / name).resolve()
            if root_resolved != destination and root_resolved not in destination.parents:
                raise RuntimeError("path_escape")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        stage("testing")
        qa = run_qa_sync(str(root))
        brain["release"] = {
            "status": "dry_run",
            "files": list(files),
            "tests": qa.model_dump(),
        }
        if not project.dry_run and not settings().AUTONOMY_DRY_RUN:
            if not qa.passed:
                brain["release"]["status"] = "blocked_by_qa"
                stage("blocked")
                return brain
            stage("provisioning")
            brain["provisioning"] = self.provision(project, credentials)
            if brain["provisioning"].get("github_files", {}).get("status") == "committed":
                brain["release"] = {
                    "status": "committed",
                    "repository": brain["provisioning"].get("github", {}).get(
                        "full_name"
                    ),
                    "pull_request": brain["provisioning"].get("pull_request"),
                    "tests": qa.model_dump(),
                }
        stage("complete")
        return brain
