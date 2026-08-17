from openai import OpenAI

from app.config import settings


class AI:
    def __init__(self):
        s = settings()
        self.client = OpenAI(api_key=s.OPENAI_API_KEY) if s.OPENAI_API_KEY else None
        self.model = s.DEFAULT_MODEL
        self.last_usage = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_cents": 0,
        }

    def ask(self, instructions, data):
        self.last_usage = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_cents": 0,
        }
        if not self.client:
            return "AI not configured; remain evidence-only."

        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=str(data),
        )
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        s = settings()
        cost = (
            tokens_in * s.AI_INPUT_COST_PER_1M
            + tokens_out * s.AI_OUTPUT_COST_PER_1M
        ) / 1_000_000 * 100
        self.last_usage = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_cents": round(cost),
        }
        return response.output_text
