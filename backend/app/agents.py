from app.ai import AI
class CEO:
    def __init__(self):self.ai=AI()
    def run(self,state): return self.ai.ask("You are CEO of an autonomous web company. Maximize sustainable traffic and value. Use evidence only. Rank impact/confidence/effort/risk. Choose reversible actions. Never invent data or expose secrets.",state)
class Research:
    def run(self,state):return {"focus":["queries","pages","content gaps","technical SEO","competitor signals"]}
class SEO:
    def run(self,state):return {"focus":["CTR","impressions","position","indexation","canonical","internal links","schema"]}
class Content:
    def run(self,state):return {"policy":"evidence-backed briefs and content; never fabricate facts"}
class Developer:
    def run(self,state):return {"policy":"isolated workspace, bounded diff, tests required"}
class QA:
    def run(self,state):return {"checks":["build","HTTP","metadata","canonical","robots","sitemap","JSON-LD","links"]}
class Analyst:
    def run(self,state):return {"metrics":["sessions","users","impressions","clicks","CTR","position"],"learning":True}
