from datetime import date,timedelta
import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange,Dimension,Metric,RunReportRequest
from github import Github
from app.config import settings
class GSC:
    def __init__(self):
        s=settings(); self.site=s.GSC_SITE_URL; self.service=None
        if s.GOOGLE_APPLICATION_CREDENTIALS and self.site:
            c=service_account.Credentials.from_service_account_file(s.GOOGLE_APPLICATION_CREDENTIALS,scopes=["https://www.googleapis.com/auth/webmasters.readonly"]); self.service=build("searchconsole","v1",credentials=c)
    def query(self,dimensions,days=28):
        if not self.service:return []
        e=date.today()-timedelta(days=2); st=e-timedelta(days=days)
        return self.service.searchanalytics().query(siteUrl=self.site,body={"startDate":st.isoformat(),"endDate":e.isoformat(),"dimensions":dimensions,"rowLimit":25000,"dataState":"final"}).execute().get("rows",[])
class GA4:
    def __init__(self):self.pid=settings().GA4_PROPERTY_ID; self.client=BetaAnalyticsDataClient() if self.pid else None
    def report(self):
        if not self.client:return []
        e=date.today(); st=e-timedelta(days=28)
        q=RunReportRequest(property=f"properties/{self.pid}",date_ranges=[DateRange(start_date=st.isoformat(),end_date=e.isoformat())],dimensions=[Dimension(name="date")],metrics=[Metric(name="activeUsers"),Metric(name="sessions"),Metric(name="engagementRate")]); return self.client.run_report(q).rows
class GitHub:
    def __init__(self):
        s=settings(); self.token=s.GITHUB_TOKEN; self.owner=s.GITHUB_OWNER; self.repo=s.GITHUB_REPO
    def repo_obj(self):return Github(self.token).get_repo(f"{self.owner}/{self.repo}") if self.token and self.owner and self.repo else None
    def branch(self,name):
        r=self.repo_obj()
        if not r:return {"status":"not_configured"}
        base=r.get_branch(settings().GITHUB_BASE_BRANCH)
        try:r.create_git_ref(ref=f"refs/heads/{name}",sha=base.commit.sha)
        except Exception as e:
            if "Reference already exists" not in str(e):raise
        return {"status":"ready","sha":base.commit.sha}
    def files(self,branch,files,message):
        r=self.repo_obj()
        if not r:return {"status":"not_configured"}
        if len(files)>settings().MAX_FILES_CHANGED:raise RuntimeError("change budget exceeded")
        shas=[]
        for path,content in files.items():
            try:old=r.get_contents(path,ref=branch); x=r.update_file(path,message,content,old.sha,branch=branch)
            except Exception:x=r.create_file(path,message,content,branch=branch)
            shas.append(x["commit"].sha)
        return {"status":"committed","shas":shas}
    def pr(self,branch):
        r=self.repo_obj()
        if not r:return {"status":"not_configured"}
        p=r.create_pull(title="Autonomous website update",body="Generated and tested by Autonomous Web Company.",head=branch,base=settings().GITHUB_BASE_BRANCH);return {"status":"created","number":p.number,"url":p.html_url}
class Vercel:
    def deploy(self):
        s=settings()
        if not s.VERCEL_TOKEN:return {"status":"not_configured"}
        payload={"name":s.VERCEL_PROJECT_ID,"target":"production"}
        if s.VERCEL_TEAM_ID:payload["teamId"]=s.VERCEL_TEAM_ID
        r=httpx.post("https://api.vercel.com/v13/deployments",headers={"Authorization":f"Bearer {s.VERCEL_TOKEN}"},json=payload,timeout=60);r.raise_for_status();return r.json()
