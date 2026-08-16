from openai import OpenAI
from app.config import settings
class AI:
    def __init__(self):
        s=settings(); self.client=OpenAI(api_key=s.OPENAI_API_KEY) if s.OPENAI_API_KEY else None; self.model=s.DEFAULT_MODEL
    def ask(self,instructions,data):
        if not self.client: return "AI not configured; remain evidence-only."
        return self.client.responses.create(model=self.model,instructions=instructions,input=str(data)).output_text
