from langgraph.graph import END, START, StateGraph

from app.agents import Analyst, CEO, Content, Developer, QA, Research, SEO


def collect(state):
    return {"status": "observed"}


def research(state):
    return {"research": Research().run(state)}


def decide(state):
    return {"strategy": CEO().run(state)}


def seo(state):
    return {"seo": SEO().run(state)}


def content(state):
    return {"content": Content().run(state)}


def develop(state):
    return {"development": Developer().run(state)}


def qa(state):
    return {"qa": QA().run(state)}


def analyze(state):
    return {"analysis": Analyst().run(state), "status": "cycle_complete"}


def build():
    graph = StateGraph(dict)
    for name, function in [
        ("collect", collect),
        ("research", research),
        ("decide", decide),
        ("seo", seo),
        ("content", content),
        ("develop", develop),
        ("qa", qa),
        ("analyze", analyze),
    ]:
        graph.add_node(name, function)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "research")
    graph.add_edge("research", "decide")
    graph.add_edge("decide", "seo")
    graph.add_edge("seo", "content")
    graph.add_edge("content", "develop")
    graph.add_edge("develop", "qa")
    graph.add_edge("qa", "analyze")
    graph.add_edge("analyze", END)
    return graph.compile()
