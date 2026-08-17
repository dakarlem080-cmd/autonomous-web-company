from datetime import date,timedelta
import json,httpx
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange,Dimension,Metric,RunReportRequest
from github import Github
from app.config import settings

class GSC:
    def __init__(self,oauth=None,site=None):
        s=settings();self.site=site or s.GSC_SITE_URL;self.service=None
        if oauth and oauth.get("access_token"):
            c=Credentials(token=oauth["access_token"],refresh_token=oauth.get("refresh_token"),token_uri="https://oauth2.googleapis.com/token",client_id=s.GOOGLE_CLIENT_ID,client_secret=s.GOOGLE_CLIENT_SECRET,scopes=["https://www.googleapis.com/auth/webmasters.readonly"]);self.service=build("searchconsole","v1",credentials=c,cache_discovery=False)
        elif s.GOOGLE_APPLICATION_CREDENTIALS and self.site:
            c=service_account.Credentials.from_service_account_file(s.GOOGLE_APPLICATION_CREDENTIALS,scopes=["https://www.googleapis.com/auth/webmasters.readonly"]);self.service=build("searchconsole","v1",credentials=c,cache_discovery=False)
    def query(self,dimensions,days=28):
        if not self.service or not self.site:return []
        e=date.today()-timedelta(days=2);st=e-timedelta(days=days);return self.service.searchanalytics().query(siteUrl=self.site,body={"startDate":st.isoformat(),"endDate":e.isoformat(),"dimensions":dimensions,"rowLimit":25000,"dataState":"final"}).execute().get("rows",[])
    def test(self):
        if not self.service:return {"connected":False,"reason":"oauth_not_configured"}
        if not self.site:return {"connected":False,"reason":"site_not_configured"}
        try:r=self.service.sites().get(siteUrl=self.site).execute();return {"connected":True,"site":self.site,"permission_level":r.get("permissionLevel")}
        except Exception as e:return {"connected":False,"site":self.site,"reason":str(e)[:300]}

class GA4:
    def __init__(self,oauth=None,property_id=None):
        s=settings();self.pid=property_id or s.GA4_PROPERTY_ID;self.client=None
        if oauth and oauth.get("access_token"):
            c=Credentials(token=oauth["access_token"],refresh_token=oauth.get("refresh_token"),token_uri="https://oauth2.googleapis.com/token",client_id=s.GOOGLE_CLIENT_ID,client_secret=s.GOOGLE_CLIENT_SECRET,scopes=["https://www.googleapis.com/auth/analytics.readonly"]);self.client=BetaAnalyticsDataClient(credentials=c)
        elif self.pid:self.client=BetaAnalyticsDataClient()
    def report(self,days=28):
        if not self.client or not self.pid:return []
        e=date.today();st=e-timedelta(days=days);q=RunReportRequest(property=f"properties/{self.pid}",date_ranges=[DateRange(start_date=st.isoformat(),end_date=e.isoformat())],dimensions=[Dimension(name="date")],metrics=[Metric(name="activeUsers"),Metric(name="sessions"),Metric(name="engagementRate")]);return self.client.run_report(q).rows
    def test(self):
        if not self.client:return {"connected":False,"reason":"oauth_not_configured"}
        if not self.pid:return {"connected":False,"reason":"property_not_configured"}
        try:rows=self.report(days=1);return {"connected":True,"property_id":str(self.pid),"has_data":bool(rows)}
        except Exception as e:return {"connected":False,"property_id":str(self.pid),"reason":str(e)[:300]}

class GitHub:
    def __init__(self,credentials=None):
        s=settings();credentials=credentials or {};self.token=credentials.get("access_token") or credentials.get("token") or s.GITHUB_TOKEN;self.owner=credentials.get("owner") or s.GITHUB_OWNER;self.repo=credentials.get("repo") or s.GITHUB_REPO
    def client(self):return Github(self.token) if self.token else None
    def repo_obj(self):return self.client().get_repo(f"{self.owner}/{self.repo}") if self.token and self.owner and self.repo else None
    def test(self):
        if not self.token:return {"connected":False,"reason":"token_not_configured"}
        try:user=self.client().get_user();return {"connected":True,"account":user.login,"repository":f"{self.owner}/{self.repo}" if self.owner and self.repo else None}
        except Exception as e:return {"connected":False,"reason":str(e)[:300]}
    def create_repo(self,name,description):
        g=self.client()
        if not g or not self.owner:return {"status":"not_configured"}
        owner=g.get_user(self.owner);r=owner.create_repo(name=name,description=description,private=True,auto_init=True);return {"status":"created","full_name":r.full_name,"url":r.html_url,"default_branch":r.default_branch}
    def branch(self,name,repo=None):
        r=repo or self.repo_obj()
        if not r:return {"status":"not_configured"}
        base=r.get_branch(settings().GITHUB_BASE_BRANCH)
        try:r.create_git_ref(ref=f"refs/heads/{name}",sha=base.commit.sha)
        except Exception as e:
            if "Reference already exists" not in str(e):raise
        return {"status":"ready","sha":base.commit.sha}
    def files(self,branch,files,message,repo=None):
        r=repo or self.repo_obj()
        if not r:return {"status":"not_configured"}
        if len(files)>settings().MAX_FILES_CHANGED:raise RuntimeError("change budget exceeded")
        commits=[]
        for path,content in files.items():
            try:old=r.get_contents(path,ref=branch);x=r.update_file(path,message,content,old.sha,branch=branch)
            except Exception:x=r.create_file(path,message,content,branch=branch)
            commits.append(x["commit"].sha)
        return {"status":"committed","shas":commits}
    def pr(self,branch,repo=None):
        r=repo or self.repo_obj()
        if not r:return {"status":"not_configured"}
        p=r.create_pull(title="Autonomous website update",body="Generated and tested by Autonomous Web Company.",head=branch,base=settings().GITHUB_BASE_BRANCH);return {"status":"created","number":p.number,"url":p.html_url}

class Vercel:
    def __init__(self,credentials=None):
        s=settings();credentials=credentials or {};self.token=credentials.get("access_token") or credentials.get("token") or s.VERCEL_TOKEN;self.team=credentials.get("team_id") or s.VERCEL_TEAM_ID
    def request(self,method,path,**kwargs):
        if not self.token:return {"status":"not_configured"}
        headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json"};params=kwargs.pop("params",{});params.update({"teamId":self.team} if self.team else {});r=httpx.request(method,f"https://api.vercel.com{path}",headers=headers,params=params,timeout=60,**kwargs);r.raise_for_status();return r.json() if r.content else {}
    def test(self,project=None):
        if not self.token:return {"connected":False,"reason":"token_not_configured"}
        try:user=self.request("GET","/v2/user");result={"connected":True,"account":user.get("user",{}).get("username") or user.get("user",{}).get("name")};
        except Exception as e:return {"connected":False,"reason":str(e)[:300]}
        if project:
            try:result["project"]=self.inspect(project)
            except Exception as e:result["project_error"]=str(e)[:300]
        return result
    def create_project(self,name,repo_full_name,root_directory=""):
        payload={"name":name,"framework":"nextjs","gitRepository":{"type":"github","repo":repo_full_name},"rootDirectory":root_directory or None};return {"status":"created",**self.request("POST","/v10/projects",json={k:v for k,v in payload.items() if v is not None})}
    def add_domain(self,project,domain):return self.request("POST",f"/v10/projects/{project}/domains",json={"name":domain})
    def deploy(self,project=None):return self.request("POST","/v13/deployments",json={"name":project or settings().VERCEL_PROJECT_ID,"target":"production"})
    def inspect(self,project):return self.request("GET",f"/v9/projects/{project}")
