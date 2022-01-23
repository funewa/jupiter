"""Add smart lists table

Revision ID: b499a7eca9e2
Revises: 5e59c55be9c5
Create Date: 2022-01-14 19:22:04.219514

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b499a7eca9e2'
down_revision = '5e59c55be9c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'smart_list',
        sa.Column('ref_id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('archived', sa.Boolean, nullable=False),
        sa.Column('created_time', sa.DateTime, nullable=False),
        sa.Column('last_modified_time', sa.DateTime, nullable=False),
        sa.Column('archived_time', sa.DateTime, nullable=True),
        sa.Column('workspace_ref_id', sa.Integer, sa.ForeignKey('workspace.ref_id'), index=True, nullable=False),
        sa.Column('the_key', sa.String(32), nullable=False),
        sa.Column('name', sa.String(100), nullable=False))
    op.create_table(
        'smart_list_event',
        sa.Column('owner_ref_id', sa.Integer, sa.ForeignKey('smart_list.ref_id'), primary_key=True),
        sa.Column('timestamp', sa.DateTime, primary_key=True),
        sa.Column('session_index', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(32), primary_key=True),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('owner_version', sa.Integer, nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('data', sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_table('smart_list_event')
    op.drop_table('smart_list')