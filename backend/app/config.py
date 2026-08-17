from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
 model_config=SettingsConfigDict(env_file=".env",extra="ignore")
 DATABASE_URL:str
 REDIS_URL:str=""
 OPENAI_API_KEY:str=""
 DEFAULT_MODEL:str="gpt-5.6"
 ENCRYPTION_KEY:str=""
 GOOGLE_APPLICATION_CREDENTIALS:str=""
 GSC_SITE_URL:str=""
 GA4_PROPERTY_ID:str=""
 GOOGLE_CLIENT_ID:str=""
 GOOGLE_CLIENT_SECRET:str=""
 GOOGLE_OAUTH_REDIRECT_URI:str=""
 GOOGLE_OAUTH_STATE_SECRET:str=""
 GOOGLE_ADS_DEVELOPER_TOKEN:str=""
 GOOGLE_ADS_LOGIN_CUSTOMER_ID:str=""
 GOOGLE_ADS_CUSTOMER_ID:str=""
 DASHBOARD_URL:str="https://autonomous-web-company.vercel.app"
 GITHUB_TOKEN:str=""
 GITHUB_OWNER:str=""
 GITHUB_REPO:str=""
 GITHUB_BASE_BRANCH:str="main"
 VERCEL_TOKEN:str=""
 VERCEL_PROJECT_ID:str=""
 VERCEL_TEAM_ID:str=""
 AUTONOMY_DRY_RUN:bool=True
 MAX_FILES_CHANGED:int=40
 SCHEDULER_HOURS:int=24
 WORKSPACE_ROOT:str="./workspaces"
 PROVISIONING_ENABLED:bool=True
 ALLOW_REPO_CREATION:bool=True
 ALLOW_VERCEL_PROVISIONING:bool=True
 ALLOW_DOMAIN_BINDING:bool=True
 AUTONOMY_MAX_PROJECTS_PER_RUN:int=5
@lru_cache
def settings():return Settings()
