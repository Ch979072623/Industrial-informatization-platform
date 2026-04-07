"""
添加数据集统计表

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-06 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """创建数据集统计表"""
    op.create_table(
        'datasetstatistics',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('dataset_id', sa.String(36), nullable=False),
        sa.Column('total_images', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_annotations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('images_with_annotations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('images_without_annotations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_annotations_per_image', sa.Float(), nullable=False, server_default='0'),
        sa.Column('class_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('class_distribution', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('annotations_per_class', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('image_sizes', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('avg_image_width', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_image_height', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_bbox_width', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_bbox_height', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_bbox_aspect_ratio', sa.Float(), nullable=False, server_default='0'),
        sa.Column('small_bboxes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_bboxes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('large_bboxes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('split_distribution', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('last_scan_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scan_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('scan_error', sa.Text(), nullable=True),
        sa.Column('labels_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dataset_id'),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ondelete='CASCADE')
    )
    
    # 创建索引
    op.create_index(
        'idx_datasetstatistics_dataset_id',
        'datasetstatistics',
        ['dataset_id']
    )
    
    op.create_index(
        'idx_datasetstatistics_scan_status',
        'datasetstatistics',
        ['scan_status']
    )


def downgrade():
    """删除数据集统计表"""
    op.drop_index('idx_datasetstatistics_scan_status', table_name='datasetstatistics')
    op.drop_index('idx_datasetstatistics_dataset_id', table_name='datasetstatistics')
    op.drop_table('datasetstatistics')
