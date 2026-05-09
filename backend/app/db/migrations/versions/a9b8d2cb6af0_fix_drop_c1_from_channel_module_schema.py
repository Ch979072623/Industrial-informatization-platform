"""fix: drop c1 from channel module schema

Revision ID: a9b8d2cb6af0
Revises: 6b624f0e400f
Create Date: 2026-05-09 07:52:56.473236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import json


# revision identifiers, used by Alembic.
revision: str = 'a9b8d2cb6af0'
down_revision: Union[str, Sequence[str], None] = '6b624f0e400f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


moduledefinition = table(
    'moduledefinition',
    column('type', sa.String(100)),
    column('schema_json', sa.JSON),
)

# 需要删除的字段定义（用于 downgrade 恢复）
# key: 模块名
# value: {"fields": [...], "insert_positions": [...]}
# 字段按原始 schema 中的顺序插入回对应位置
_SCHEMA_FIXES = {
    "Bottleneck": {
        "fields": [
            {
                "name": "c1",
                "type": "int",
                "default": 64,
                "min": 1,
                "description": "输入通道",
            },
        ],
        "positions": [0],
    },
    "C2f": {
        "fields": [
            {
                "name": "c1",
                "type": "int",
                "default": 128,
                "min": 1,
                "description": "输入通道",
            },
            {
                "name": "n",
                "type": "int",
                "default": 2,
                "min": 1,
                "description": "Bottleneck重复次数（schema固定展开n=2）",
            },
        ],
        "positions": [0, 1],
    },
}


def upgrade() -> None:
    """从 channel 模块 schema 中删除平台推导字段（c1 / n）。

    说明:
      - c1: parse_model 对 Conv/C2f/Bottleneck 等白名单模块会自动从 ch[f] 推导并
        prepend 到 args，因此 schema 中不应包含 c1。
      - n: parse_model 对 C2f/C3 等模块会将 YAML 的 repeats 字段 insert(2, n) 到 args，
        因此 schema 中也不应包含 n。
    """
    bind = op.get_bind()
    for mod_type, fix in _SCHEMA_FIXES.items():
        row = bind.execute(
            sa.text("SELECT schema_json FROM moduledefinition WHERE type = :type"),
            {"type": mod_type},
        ).fetchone()
        if not row:
            continue
        schema = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        params = schema.get("params_schema", [])
        drop_names = {f["name"] for f in fix["fields"]}
        new_params = [p for p in params if p.get("name") not in drop_names]
        if len(new_params) == len(params):
            continue  # 无变化
        schema["params_schema"] = new_params
        bind.execute(
            sa.text(
                "UPDATE moduledefinition SET schema_json = :schema WHERE type = :type"
            ),
            {"schema": json.dumps(schema, ensure_ascii=False), "type": mod_type},
        )


def downgrade() -> None:
    """恢复 channel 模块 schema 中被删除的字段。"""
    bind = op.get_bind()
    for mod_type, fix in _SCHEMA_FIXES.items():
        row = bind.execute(
            sa.text("SELECT schema_json FROM moduledefinition WHERE type = :type"),
            {"type": mod_type},
        ).fetchone()
        if not row:
            continue
        schema = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        params = schema.get("params_schema", [])
        existing_names = {p.get("name") for p in params}
        for field, pos in zip(fix["fields"], fix["positions"]):
            if field["name"] in existing_names:
                continue
            # 插回原始位置（考虑前面已恢复的字段对后续索引的影响）
            insert_pos = min(pos, len(params))
            params.insert(insert_pos, field)
        schema["params_schema"] = params
        bind.execute(
            sa.text(
                "UPDATE moduledefinition SET schema_json = :schema WHERE type = :type"
            ),
            {"schema": json.dumps(schema, ensure_ascii=False), "type": mod_type},
        )
