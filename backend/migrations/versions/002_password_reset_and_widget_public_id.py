"""Add password reset tokens and widget public ID

Revision ID: 002_pwd_reset_widgetid
Revises: 001_initial
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "002_pwd_reset_widgetid"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.add_column("widget_configs", sa.Column("widget_public_id", sa.String(length=80), nullable=True))
    op.execute(
        """
        UPDATE widget_configs
        SET widget_public_id = 'wid_' || substring(md5(random()::text || clock_timestamp()::text), 1, 24)
        WHERE widget_public_id IS NULL
        """
    )
    op.create_index(
        "ix_widget_configs_widget_public_id",
        "widget_configs",
        ["widget_public_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_widget_configs_widget_public_id", table_name="widget_configs")
    op.drop_column("widget_configs", "widget_public_id")

    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
