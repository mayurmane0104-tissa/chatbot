"""Initial schema — all 14 tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.dialects.postgresql import ENUM

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # fuzzy text search
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

# CREATE TYPE userrole AS ENUM ('super_admin', 'admin', 'agent', 'user');
    # Enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE conversationstatus AS ENUM ('active', 'closed', 'escalated');
            CREATE TYPE messagerole AS ENUM ('user', 'assistant', 'system');
            CREATE TYPE documentstatus AS ENUM ('pending', 'processing', 'indexed', 'failed');
            CREATE TYPE feedbacktype AS ENUM ('thumbs_up', 'thumbs_down');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    userrole_enum = ENUM(
        'super_admin', 'admin', 'agent', 'user',
        name='userrole',
        create_type=False,
    )

    conversationstatus_enum = ENUM(
        'active', 'closed', 'escalated',
        name='conversationstatus',
        create_type=False
    )

    messagerole_enum = ENUM(
        'user', 'assistant', 'system',
        name='messagerole',
        create_type=False
    )

    documentstatus_enum = ENUM(
        'pending', 'processing', 'indexed', 'failed',
        name='documentstatus',
        create_type=False
    )

    feedbacktype_enum = ENUM(
        'thumbs_up', 'thumbs_down',
        name='feedbacktype',
        create_type=False
    )

    userrole_enum.create(op.get_bind(), checkfirst=True)

    # 1. workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("domain", sa.String(255)),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("settings", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", userrole_enum, server_default="user"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_verified", sa.Boolean, server_default="false"),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "email", name="uq_workspace_user_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])

    # 3. refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, server_default="false"),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # 4. api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(10)),
        sa.Column("scopes", ARRAY(sa.String), server_default="{}"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # 5. widget_configs
    op.create_table(
        "widget_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), server_default="Default"),
        sa.Column("primary_color", sa.String(7), server_default="#2563EB"),
        sa.Column("secondary_color", sa.String(7), server_default="#1E40AF"),
        sa.Column("bot_name", sa.String(100), server_default="TissaTech Assistant"),
        sa.Column("greeting_message", sa.Text, server_default="Hi! How can I help you today?"),
        sa.Column("placeholder_text", sa.String(200), server_default="Type your message..."),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("position", sa.String(20), server_default="bottom-right"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("allowed_domains", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 6. sessions (anonymous widget)
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_token", sa.String(255), unique=True, nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_token", "sessions", ["session_token"])

    # 7. conversations
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("bedrock_session_id", sa.String(255)),
        sa.Column("title", sa.String(500)),
        sa.Column("status", conversationstatus_enum, server_default="active"),
        sa.Column("channel", sa.String(50), server_default="web"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])

    # 8. messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", messagerole_enum, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("model_id", sa.String(100)),
        sa.Column("tool_calls", JSONB),
        sa.Column("citations", JSONB),
        sa.Column("is_flagged", sa.Boolean, server_default="false"),
        sa.Column("flag_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # 9. message_feedback
    op.create_table(
        "message_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("feedback_type", feedbacktype_enum, nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 10. documents
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("file_name", sa.String(500)),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("s3_key", sa.String(500)),
        sa.Column("status", documentstatus_enum, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])

    # 11. document_chunks (with pgvector)
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", pg.ARRAY(sa.Float)),  # will be cast to vector(1536) after
        sa.Column("token_count", sa.Integer),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_doc_chunks_document_id", "document_chunks", ["document_id"])

    # Cast embedding column to vector type after pgvector extension loaded
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    # IVFFlat index for ANN search
    op.execute("CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    # 12. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True)),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(100)),
        sa.Column("status_code", sa.Integer),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # 13. rate_limit_records
    op.create_table(
        "rate_limit_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("request_count", sa.Integer, server_default="1"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rate_limit_identifier", "rate_limit_records", ["identifier", "endpoint"])

    # 14. system_configs
    op.create_table(
        "system_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("is_encrypted", sa.Boolean, server_default="false"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "key", name="uq_system_config_workspace_key"),
    )
    op.create_index("ix_system_configs_key", "system_configs", ["key"])

    # Seed default workspace
    op.execute("""
        INSERT INTO workspaces (id, name, slug, domain, plan)
        VALUES (uuid_generate_v4(), 'TissaTech', 'tissatech', 'tissatech.com', 'enterprise')
    """)


def downgrade() -> None:
    for table in [
        "system_configs", "rate_limit_records", "audit_logs",
        "document_chunks", "documents", "message_feedback",
        "messages", "conversations", "sessions", "widget_configs",
        "api_keys", "refresh_tokens", "users", "workspaces",
    ]:
        op.drop_table(table)

    op.execute("""
        DROP TYPE IF EXISTS userrole, conversationstatus, messagerole, documentstatus, feedbacktype CASCADE
    """)
