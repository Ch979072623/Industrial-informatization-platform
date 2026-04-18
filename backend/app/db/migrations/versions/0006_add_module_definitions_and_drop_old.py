"""
添加 module_definitions 表并废弃旧表

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-18 08:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # 创建新表 module_definitions
    if not table_exists('module_definition'):
        op.create_table(
            'module_definition',
            sa.Column('type', sa.String(length=100), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('is_composite', sa.Boolean(), nullable=False),
            sa.Column('display_name', sa.String(length=200), nullable=False),
            sa.Column('schema_json', sa.JSON(), nullable=False),
            sa.Column('source', sa.String(length=20), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('created_by', sa.String(length=36), nullable=True),
            sa.Column('production_line_id', sa.String(length=36), nullable=True),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['production_line_id'], ['productionline.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('type')
        )
        op.create_index(op.f('ix_module_definition_category'), 'module_definition', ['category'], unique=False)
        op.create_index(op.f('ix_module_definition_id'), 'module_definition', ['id'], unique=False)
        op.create_index(op.f('ix_module_definition_type'), 'module_definition', ['type'], unique=True)

    # 废弃旧表（如果存在）
    if table_exists('modelbuilderconfig'):
        op.drop_index(op.f('ix_modelbuilderconfig_id'), table_name='modelbuilderconfig')
        op.drop_table('modelbuilderconfig')

    if table_exists('mlmodule'):
        op.drop_index(op.f('ix_mlmodule_name'), table_name='mlmodule')
        op.drop_index(op.f('ix_mlmodule_id'), table_name='mlmodule')
        op.drop_index(op.f('ix_mlmodule_category'), table_name='mlmodule')
        op.drop_table('mlmodule')


def downgrade() -> None:
    # 删除新表
    if table_exists('module_definition'):
        op.drop_index(op.f('ix_module_definition_type'), table_name='module_definition')
        op.drop_index(op.f('ix_module_definition_id'), table_name='module_definition')
        op.drop_index(op.f('ix_module_definition_category'), table_name='module_definition')
        op.drop_table('module_definition')

    # 重建旧表（简化版，用于回滚）
    if not table_exists('mlmodule'):
        op.create_table(
            'mlmodule',
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('display_name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('parameters_schema', sa.JSON(), nullable=False),
            sa.Column('default_parameters', sa.JSON(), nullable=False),
            sa.Column('code_template', sa.Text(), nullable=True),
            sa.Column('input_ports', sa.JSON(), nullable=False),
            sa.Column('output_ports', sa.JSON(), nullable=False),
            sa.Column('icon', sa.String(length=50), nullable=True),
            sa.Column('is_builtin', sa.Boolean(), nullable=False),
            sa.Column('is_custom', sa.Boolean(), nullable=False),
            sa.Column('created_by', sa.String(length=36), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_mlmodule_category'), 'mlmodule', ['category'], unique=False)
        op.create_index(op.f('ix_mlmodule_id'), 'mlmodule', ['id'], unique=False)
        op.create_index(op.f('ix_mlmodule_name'), 'mlmodule', ['name'], unique=True)

    if not table_exists('modelbuilderconfig'):
        op.create_table(
            'modelbuilderconfig',
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('architecture_json', sa.JSON(), nullable=False),
            sa.Column('code_snapshot', sa.Text(), nullable=True),
            sa.Column('input_shape', sa.JSON(), nullable=True),
            sa.Column('num_classes', sa.Integer(), nullable=True),
            sa.Column('base_model', sa.String(length=100), nullable=True),
            sa.Column('production_line_id', sa.String(length=36), nullable=True),
            sa.Column('created_by', sa.String(length=36), nullable=False),
            sa.Column('is_public', sa.Boolean(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['production_line_id'], ['productionline.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_modelbuilderconfig_id'), 'modelbuilderconfig', ['id'], unique=False)
