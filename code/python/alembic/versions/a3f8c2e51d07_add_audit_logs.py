"""add_audit_logs

Audit log table for tracking user actions (Phase 3B).

Revision ID: a3f8c2e51d07
Revises: c1c6deac2013
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'a3f8c2e51d07'
down_revision: Union[str, Sequence[str], None] = 'c1c6deac2013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    try:
        conn = op.get_bind()
        return inspect(conn).has_table(table_name)
    except Exception:
        return False


def upgrade() -> None:
    if not _table_exists('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=True),     # NULL for system actions
            sa.Column('org_id', sa.String(36), nullable=True),
            sa.Column('action', sa.String(100), nullable=False),    # e.g. 'auth.login'
            sa.Column('target_type', sa.String(50), nullable=True), # e.g. 'session', 'member'
            sa.Column('target_id', sa.String(36), nullable=True),
            sa.Column('details', sa.Text, nullable=True),           # JSON string
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('created_at', sa.Float, nullable=False),      # epoch seconds
        )
        op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
        op.create_index('idx_audit_org_id', 'audit_logs', ['org_id'])
        op.create_index('idx_audit_action', 'audit_logs', ['action'])
        op.create_index('idx_audit_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_audit_created_at', 'audit_logs')
    op.drop_index('idx_audit_action', 'audit_logs')
    op.drop_index('idx_audit_org_id', 'audit_logs')
    op.drop_index('idx_audit_user_id', 'audit_logs')
    op.drop_table('audit_logs')
