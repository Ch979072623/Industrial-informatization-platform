"""
添加数据增强模块

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision: str = '0003'
down_revision: Union[str, None] = '0002'  # 依赖于 0002
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    # 创建增强模板表
    op.create_table(
        'augmentationtemplate',
        sa.Column('name', sa.String(100), nullable=False, comment='模板名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='模板描述'),
        sa.Column('pipeline_config', sa.JSON(), nullable=False, default=list, comment='流水线配置'),
        sa.Column('is_preset', sa.Boolean(), nullable=False, default=False, comment='是否为系统预设'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, comment='创建者ID'),
        sa.Column('id', sa.String(36), primary_key=True, comment='主键ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    
    # 创建增强任务表
    op.create_table(
        'augmentationjob',
        sa.Column('name', sa.String(100), nullable=False, comment='任务名称'),
        sa.Column('source_dataset_id', sa.String(36), sa.ForeignKey('dataset.id', ondelete='CASCADE'), nullable=False, comment='源数据集ID'),
        sa.Column('target_dataset_id', sa.String(36), sa.ForeignKey('dataset.id', ondelete='SET NULL'), nullable=True, comment='目标数据集ID'),
        sa.Column('pipeline_config', sa.JSON(), nullable=False, default=list, comment='流水线配置'),
        sa.Column('augmentation_factor', sa.Integer(), nullable=False, default=2, comment='增强倍数'),
        sa.Column('status', sa.String(20), nullable=False, default='pending', comment='任务状态'),
        sa.Column('progress', sa.Float(), nullable=False, default=0.0, comment='进度百分比'),
        sa.Column('processed_count', sa.Integer(), nullable=False, default=0, comment='已处理数量'),
        sa.Column('total_count', sa.Integer(), nullable=False, default=0, comment='总数量'),
        sa.Column('generated_count', sa.Integer(), nullable=False, default=0, comment='生成数量'),
        sa.Column('celery_task_id', sa.String(100), nullable=True, comment='Celery任务ID'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('execution_logs', sa.JSON(), nullable=False, default=list, comment='执行日志'),
        sa.Column('timing_stats', sa.JSON(), nullable=True, comment='时间统计'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, comment='创建者ID'),
        sa.Column('id', sa.String(36), primary_key=True, comment='主键ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    
    # 创建自定义脚本表
    op.create_table(
        'customaugmentationscript',
        sa.Column('name', sa.String(100), nullable=False, comment='脚本名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='脚本描述'),
        sa.Column('script_path', sa.String(500), nullable=False, comment='脚本文件路径'),
        sa.Column('script_hash', sa.String(64), nullable=False, comment='脚本内容哈希'),
        sa.Column('file_size', sa.Integer(), nullable=False, comment='文件大小（字节）'),
        sa.Column('is_valid', sa.Boolean(), nullable=False, default=False, comment='是否通过验证'),
        sa.Column('validation_error', sa.Text(), nullable=True, comment='验证错误信息'),
        sa.Column('interface_type', sa.String(20), nullable=False, default='standard', comment='接口类型'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, comment='创建者ID'),
        sa.Column('id', sa.String(36), primary_key=True, comment='主键ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    
    # 创建预览缓存表
    op.create_table(
        'augmentationpreview',
        sa.Column('source_image_id', sa.String(36), sa.ForeignKey('datasetimage.id', ondelete='CASCADE'), nullable=False, comment='源图像ID'),
        sa.Column('config_hash', sa.String(64), nullable=False, comment='配置哈希值'),
        sa.Column('preview_image_path', sa.String(500), nullable=False, comment='预览图像路径'),
        sa.Column('preview_annotations', sa.JSON(), nullable=True, comment='预览标注数据'),
        sa.Column('expires_at', sa.String(30), nullable=True, comment='过期时间'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, comment='创建者ID'),
        sa.Column('id', sa.String(36), primary_key=True, comment='主键ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), comment='更新时间'),
    )
    
    # 创建索引
    op.create_index('idx_augmentation_job_status', 'augmentationjob', ['status'])
    op.create_index('idx_augmentation_job_source_dataset', 'augmentationjob', ['source_dataset_id'])
    op.create_index('idx_augmentation_job_created_by', 'augmentationjob', ['created_by'])
    op.create_index('idx_augmentation_template_created_by', 'augmentationtemplate', ['created_by'])
    op.create_index('idx_custom_script_created_by', 'customaugmentationscript', ['created_by'])
    op.create_index('idx_augmentation_preview_hash', 'augmentationpreview', ['config_hash'])


def downgrade() -> None:
    """降级数据库"""
    # 删除表（按依赖关系倒序）
    op.drop_table('augmentationpreview')
    op.drop_table('customaugmentationscript')
    op.drop_table('augmentationjob')
    op.drop_table('augmentationtemplate')
