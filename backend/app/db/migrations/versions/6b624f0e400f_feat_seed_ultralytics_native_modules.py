"""feat: seed ultralytics native modules

Revision ID: 6b624f0e400f
Revises: 0006
Create Date: 2026-05-08 20:42:43.848812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision: str = '6b624f0e400f'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ModuleDefinition 表引用（使用应用实际表名 moduledefinition）
module_definition = table(
    'moduledefinition',
    column('id', sa.String(36)),
    column('type', sa.String(100)),
    column('category', sa.String(50)),
    column('is_composite', sa.Boolean),
    column('display_name', sa.String(200)),
    column('schema_json', sa.JSON),
    column('source', sa.String(20)),
    column('version', sa.Integer),
    column('created_by', sa.String(36)),
    column('production_line_id', sa.String(36)),
    column('created_at', sa.DateTime(timezone=True)),
    column('updated_at', sa.DateTime(timezone=True)),
)


MODULES = [
    {
        "id": "13f252fb-c667-44b4-98e6-5f3f0ab896cf",
        "type": "Conv",
        "category": "atomic",
        "is_composite": False,
        "display_name": "标准卷积",
        "schema_json": {
            "type": "Conv",
            "category": "atomic",
            "display_name": "标准卷积",
            "is_composite": False,
            "params_schema": [
                {"name": "c2", "type": "int", "default": 64, "min": 1, "description": "输出通道数"},
                {"name": "k", "type": "int", "default": 1, "min": 1, "description": "卷积核大小"},
                {"name": "s", "type": "int", "default": 1, "min": 1, "description": "步长"},
                {"name": "p", "type": "int", "default": None, "description": "填充(None=自动)"},
                {"name": "g", "type": "int", "default": 1, "min": 1, "description": "分组卷积组数"},
                {"name": "d", "type": "int", "default": 1, "min": 1, "description": "空洞率"},
                {"name": "act", "type": "bool", "default": True, "description": "是否使用激活函数"},
            ],
            "input_ports": [{"name": "input", "type": "tensor"}],
            "output_ports": [{"name": "output", "type": "tensor"}],
        },
        "source": "builtin",
        "version": 1,
    },
    {
        "id": "3bf490cd-fa33-460f-b9a4-4663ec2defff",
        "type": "SPPF",
        "category": "atomic",
        "is_composite": False,
        "display_name": "空间金字塔池化快速版",
        "schema_json": {
            "type": "SPPF",
            "category": "atomic",
            "display_name": "空间金字塔池化快速版",
            "is_composite": False,
            "params_schema": [
                {"name": "c2", "type": "int", "default": 1024, "min": 1, "description": "输出通道数"},
                {"name": "k", "type": "int", "default": 5, "min": 1, "description": "池化核大小"},
            ],
            "input_ports": [{"name": "input", "type": "tensor"}],
            "output_ports": [{"name": "output", "type": "tensor"}],
        },
        "source": "builtin",
        "version": 1,
    },
    {
        "id": "50482a68-a9cc-4a6f-a21c-6e932b419b61",
        "type": "Detect",
        "category": "head",
        "is_composite": False,
        "display_name": "标准检测头",
        "schema_json": {
            "type": "Detect",
            "category": "head",
            "display_name": "标准检测头",
            "is_composite": False,
            "params_schema": [
                {"name": "nc", "type": "int", "default": 80, "min": 1, "description": "类别数"},
            ],
            "input_ports": [{"name": "x", "type": "tensor"}],
            "output_ports": [{"name": "out", "type": "tensor"}],
        },
        "source": "builtin",
        "version": 1,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for mod in MODULES:
        # 幂等：如已存在则跳过
        result = bind.execute(
            sa.text("SELECT 1 FROM moduledefinition WHERE type = :type"),
            {"type": mod["type"]},
        ).fetchone()
        if result:
            continue
        row = {**mod, "created_at": now, "updated_at": now}
        op.bulk_insert(module_definition, [row])


def downgrade() -> None:
    types = [mod["type"] for mod in MODULES]
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM moduledefinition WHERE type IN ({})".format(
                ", ".join([f":t{i}" for i in range(len(types))])
            )
        ),
        {f"t{i}": t for i, t in enumerate(types)},
    )
