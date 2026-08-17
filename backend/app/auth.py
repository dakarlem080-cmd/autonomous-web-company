from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Organization, Membership, SessionToken
from app.security import hash_token, new_session_token

ROLES = {"Owner", "Admin", "Member", "Viewer"}
ROLE_LEVEL = {"Viewer": 10, "Member": 20, "Admin": 30, "Owner": 40}

def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(email) > 320: raise ValueError("invalid_email")
    return email

def slugify(value: str) -> str:
    import re
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:100] or "organization"

async def create_user(s: AsyncSession, email: str, password: str, name: str) -> tuple[User, Organization]:
    from argon2 import PasswordHasher
    email = normalize_email(email)
    if len(password) < 12: raise ValueError("password_min_length_12")
    if await s.scalar(select(User).where(User.email == email)): raise ValueError("email_already_registered")
    user = User(email=email, name=name.strip()[:200], password_hash=PasswordHasher().hash(password))
    s.add(user); await s.flush()
    org = Organization(name=(name.strip() or email.split("@")[0])[:200], slug=slugify(f"{name}-{user.id}"))
    s.add(org); await s.flush()
    s.add(Membership(user_id=user.id, organization_id=org.id, role="Owner"))
    return user, org

async def authenticate(s: AsyncSession, email: str, password: str) -> User | None:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHash
    user = await s.scalar(select(User).where(User.email == normalize_email(email), User.active == True))
    if not user: return None
    try: PasswordHasher().verify(user.password_hash, password)
    except (VerifyMismatchError, InvalidHash): return None
    return user

async def issue_session(s: AsyncSession, user_id: int, ttl_hours: int) -> str:
    token = new_session_token()
    s.add(SessionToken(user_id=user_id, token_hash=hash_token(token), expires_at=datetime.now(timezone.utc)+timedelta(hours=ttl_hours)))
    return token

async def get_identity(s: AsyncSession, token: str | None):
    if not token: return None
    row = await s.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(token), SessionToken.revoked_at.is_(None)))
    if not row or row.expires_at <= datetime.now(timezone.utc): return None
    user = await s.scalar(select(User).where(User.id == row.user_id, User.active == True))
    if not user: return None
    memberships = (await s.execute(select(Membership).where(Membership.user_id == user.id))).scalars().all()
    return user, memberships

async def has_project_access(s: AsyncSession, user_id: int, project_id: int, minimum: str = "Viewer") -> bool:
    from app.models import Project
    project = await s.scalar(select(Project).where(Project.id == project_id))
    if not project: return False
    membership = await s.scalar(select(Membership).where(Membership.user_id == user_id, Membership.organization_id == project.organization_id))
    return bool(membership and ROLE_LEVEL.get(membership.role, 0) >= ROLE_LEVEL[minimum])
