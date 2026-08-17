from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_security_runtime"
down_revision = None
branch_labels = None
depends_on = None


def has_table(name):
    return inspect(op.get_bind()).has_table(name)


def has_column(table, column):
    return column in {
        column_info["name"]
        for column_info in inspect(op.get_bind()).get_columns(table)
    }


def upgrade():
    bind = op.get_bind()
    if not has_table("projects"):
        raise RuntimeError(
            "projects table is missing; initialize the legacy schema with its "
            "own Alembic migration before applying 0001_security_runtime"
        )

    if not has_table("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("email", sa.String(320), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(512), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not has_table("memberships"):
        op.create_table(
            "memberships",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "organization_id",
                sa.Integer,
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(30), nullable=False, server_default="Member"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "user_id", "organization_id", name="uq_membership_user_org"
            ),
        )
    if not has_table("session_tokens"):
        op.create_table(
            "session_tokens",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not has_column("projects", "organization_id"):
        op.add_column(
            "projects",
            sa.Column(
                "organization_id",
                sa.Integer,
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
    if has_table("secrets"):
        try:
            bind.execute(
                sa.text(
                    "DELETE FROM secrets a USING secrets b "
                    "WHERE a.id > b.id AND a.project_id=b.project_id "
                    "AND a.provider=b.provider"
                )
            )
            op.create_unique_constraint(
                "uq_secret_project_provider",
                "secrets",
                ["project_id", "provider"],
            )
        except Exception:
            # Existing deployments may already contain the constraint.
            pass
    if has_table("employees") and not has_column("employees", "budget_cents"):
        op.add_column(
            "employees",
            sa.Column("budget_cents", sa.Integer, nullable=False, server_default="0"),
        )
    if not has_table("tasks"):
        op.create_table(
            "tasks",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "run_id",
                sa.Integer,
                sa.ForeignKey("runs.id", ondelete="SET NULL"),
            ),
            sa.Column("agent", sa.String(80), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("priority", sa.Integer, nullable=False, server_default="50"),
        )
    if not has_table("tool_calls"):
        op.create_table(
            "tool_calls",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "run_id",
                sa.Integer,
                sa.ForeignKey("runs.id", ondelete="SET NULL"),
            ),
            sa.Column("agent", sa.String(80), nullable=False),
            sa.Column("tool", sa.String(120), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("result", sa.JSON, nullable=False),
            sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        )
    if not has_table("cost_usage"):
        op.create_table(
            "cost_usage",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "run_id",
                sa.Integer,
                sa.ForeignKey("runs.id", ondelete="SET NULL"),
            ),
            sa.Column("agent", sa.String(80), nullable=False),
            sa.Column("model", sa.String(160), nullable=False),
            sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
            sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cost_cents", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if has_table("audit_logs"):
        if not has_column("audit_logs", "user_id"):
            op.add_column(
                "audit_logs",
                sa.Column(
                    "user_id",
                    sa.Integer,
                    sa.ForeignKey("users.id", ondelete="SET NULL"),
                ),
            )
        if not has_column("audit_logs", "created_at"):
            op.add_column(
                "audit_logs",
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )


def downgrade():
    for table in (
        "cost_usage",
        "tool_calls",
        "tasks",
        "session_tokens",
        "memberships",
        "users",
        "organizations",
    ):
        if has_table(table):
            op.drop_table(table)
    if has_table("projects") and has_column("projects", "organization_id"):
        op.drop_column("projects", "organization_id")
