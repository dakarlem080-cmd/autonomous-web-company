from app.ai import AI

class CEO:
    def __init__(self):self.ai=AI()
    def run(self,state):
        opportunities=state.get("opportunities",[]);top=opportunities[:10]
        if self.ai.client:return self.ai.ask("Act as CEO. Use only supplied evidence. Return a concise strategy with ranked actions, impact, confidence, risk and reversibility. Never invent metrics or expose secrets.",{"objective":state.get("objective"),"top_opportunities":top,"evidence":state.get("evidence",{})})
        return {"priority":"evidence_collection","reason":"AI model unavailable; do not fabricate decisions","opportunities":len(opportunities)}

class Research:
    def run(self,state):
        evidence=state.get("evidence",{});return {"sources":[],"observed_data":{"gsc_rows":len(evidence.get("gsc",[])),"ga4_rows":len(evidence.get("ga4",[]))},"status":"completed"}

class SEO:
    def run(self,state):
        rows=state.get("evidence",{}).get("gsc",[]);opportunities=[]
        for r in rows:
            imp=float(r.get("impressions",0));ctr=float(r.get("ctr",0));pos=float(r.get("position",100));keys=r.get("keys",[])
            if imp>=100 and (ctr<.03 or 5<=pos<=20):opportunities.append({"query":keys[0] if keys else "","page":keys[1] if len(keys)>1 else "","impressions":imp,"ctr":ctr,"position":pos,"reason":"high_visibility_low_ctr_or_mid_rank"})
        return {"opportunities":opportunities[:50],"status":"completed"}

class Content:
    def run(self,state):
        ops=state.get("seo",{}).get("opportunities",[]);return {"briefs":[{"topic":x.get("query"),"page":x.get("page"),"sources":[]} for x in ops[:10]],"fact_check_required":True,"status":"ready_for_review"}

class Developer:
    def run(self,state):return {"change_budget":{"max_files":40,"max_added_lines":2000,"max_deleted_lines":1000,"allowed_paths":["app/"],"forbidden_paths":[".env","secrets","credentials"]},"status":"plan_only"}

class QA:
    def run(self,state):
        release=state.get("release",{});tests=release.get("tests",{})
        return {"executed":bool(tests.get("executed_checks")),"passed":bool(tests.get("passed")),"checks":tests.get("checks",{}),"errors":tests.get("errors",[]),"status":"completed"}

class Analyst:
    def run(self,state):
        e=state.get("evidence",{});return {"metrics":{"gsc_rows":len(e.get("gsc",[])),"ga4_rows":len(e.get("ga4",[]))},"baseline_persisted":True,"status":"completed"}
