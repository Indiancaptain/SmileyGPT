"""composite indexes for conversation/message query patterns

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replace single-column indexes with composite ones that actually
    # match how these tables are queried: conversations are always
    # fetched "for this user, ordered by updated_at", and messages are
    # always fetched "for this conversation, ordered by created_at". A
    # composite index's leading column still serves plain equality
    # lookups on that column alone, so nothing is lost.
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])

    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
