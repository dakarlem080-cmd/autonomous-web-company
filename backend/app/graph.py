from langgraph.graph import StateGraph,START,END
from app.agents import CEO,Research,SEO,Content,Developer,QA,Analyst
def collect(s):return {"status":"observed"}
def research(s):return {"research":Research().run(s)}
def decide(s):return {"strategy":CEO().run(s)}
def seo(s):return {"seo":SEO().run(s)}
def content(s):return {"content":Content().run(s)}
def develop(s):return {"development":Developer().run(s)}
def qa(s):return {"qa":QA().run(s)}
def analyze(s):return {"analysis":Analyst().run(s),"status":"cycle_complete"}
def build():
 g=StateGraph(dict)
 for n,f in [("collect",collect),("research",research),("decide",decide),("seo",seo),("content",content),("develop",develop),("qa",qa),("analyze",analyze)]:g.add_node(n,f)
 g.add_edge(START,"collect");g.add_edge("collect","research");g.add_edge("research","decide");g.add_edge("decide","seo");g.add_edge("seo","content");g.add_edge("content","develop");g.add_edge("develop","qa");g.add_edge("qa","analyze");g.add_edge("analyze",END)
 return g.compile()
