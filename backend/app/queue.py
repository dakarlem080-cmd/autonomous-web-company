import json
import uuid
from redis.asyncio import Redis
from app.config import settings

QUEUE_KEY="awc:jobs"
DLQ_KEY="awc:jobs:dead"

def client()->Redis:
    if not settings().REDIS_URL:raise RuntimeError("REDIS_URL is required for queued jobs")
    return Redis.from_url(settings().REDIS_URL,decode_responses=True)

async def enqueue(kind:str,payload:dict,max_attempts:int=3)->str:
    job_id=str(uuid.uuid4());job={"id":job_id,"kind":kind,"payload":payload,"attempts":0,"max_attempts":max_attempts};r=client();await r.rpush(QUEUE_KEY,json.dumps(job));await r.aclose();return job_id

async def reserve(timeout:int=5):
    r=client();item=await r.blpop(QUEUE_KEY,timeout=timeout);await r.aclose();return json.loads(item[1]) if item else None

async def dead_letter(job:dict,error:str):
    job["error"]=error[:4000];r=client();await r.rpush(DLQ_KEY,json.dumps(job));await r.aclose()
