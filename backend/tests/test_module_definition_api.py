"""
ModuleDefinition POST API 测试
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module_definition import ModuleDefinition


class TestCreateModule:
    """正常创建模块"""

    @pytest.mark.asyncio
    async def test_create_module_success(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="Conv2d",
                display_name="2D卷积",
                category="atomic",
                schema_json={
                    "input_ports": [{"name": "input"}],
                    "output_ports": [{"name": "output"}],
                },
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "MyTestBlock",
            "display_name": "测试模块",
            "category": "custom",
            "description": "一个测试模块",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [
                {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
                {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
            ],
            "params_schema": [],
        }
        response = await admin_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["type"] == "MyTestBlock"
        assert data["data"]["source"] == "custom"
        assert data["data"]["schema_json"]["is_composite"] is True

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, user_client: AsyncClient) -> None:
        payload = {
            "type": "MyBlock2",
            "display_name": "测试",
            "category": "custom",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [],
            "params_schema": [],
        }
        response = await user_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_conflict_builtin(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="PMSFA",
                display_name="PMSFA",
                category="backbone",
                schema_json={"is_composite": True},
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "PMSFA",
            "display_name": "伪造PMSFA",
            "category": "backbone",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [],
            "params_schema": [],
        }
        response = await admin_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["reason"] == "conflict_with_builtin"
        assert detail["suggested_name"] == "PMSFA_v2"

    @pytest.mark.asyncio
    async def test_override_custom(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="Conv2d",
                display_name="2D卷积",
                category="atomic",
                schema_json={
                    "input_ports": [{"name": "input"}],
                    "output_ports": [{"name": "output"}],
                },
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "MyBlock",
            "display_name": "第一次",
            "category": "custom",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [
                {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
                {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
            ],
            "params_schema": [],
        }
        r1 = await admin_client.post("/api/v1/models/modules", json=payload)
        assert r1.status_code == 201

        payload["display_name"] = "第二次"
        r2 = await admin_client.post("/api/v1/models/modules", json=payload)
        assert r2.status_code == 200
        assert r2.json()["data"]["display_name"] == "第二次"
        assert r2.json()["data"]["schema_json"]["display_name"] == "第二次"

    @pytest.mark.asyncio
    async def test_create_module_writes_top_level_is_composite(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="Conv2d",
                display_name="2D卷积",
                category="atomic",
                schema_json={
                    "input_ports": [{"name": "input"}],
                    "output_ports": [{"name": "output"}],
                },
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "CompositeBlock",
            "display_name": "复合块",
            "category": "custom",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [
                {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
                {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
            ],
            "params_schema": [],
        }
        response = await admin_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 201
        data = response.json()
        # 顶层 is_composite 必须为 True（不是 False / None）
        assert data["data"]["is_composite"] is True
        assert data["data"]["schema_json"]["is_composite"] is True

    @pytest.mark.asyncio
    async def test_override_keeps_top_level_is_composite(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="Conv2d",
                display_name="2D卷积",
                category="atomic",
                schema_json={
                    "input_ports": [{"name": "input"}],
                    "output_ports": [{"name": "output"}],
                },
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "OverrideBlock",
            "display_name": "第一版",
            "category": "custom",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [
                {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
                {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
            ],
            "params_schema": [],
        }
        r1 = await admin_client.post("/api/v1/models/modules", json=payload)
        assert r1.status_code == 201
        assert r1.json()["data"]["is_composite"] is True

        payload["display_name"] = "第二版"
        r2 = await admin_client.post("/api/v1/models/modules", json=payload)
        assert r2.status_code == 200
        data = r2.json()["data"]
        assert data["is_composite"] is True
        assert data["version"] == 2

    @pytest.mark.asyncio
    async def test_create_module_input_ports_dynamic_false(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ModuleDefinition(
                type="Conv2d",
                display_name="2D卷积",
                category="atomic",
                schema_json={
                    "input_ports": [{"name": "input"}],
                    "output_ports": [{"name": "output"}],
                },
                source="builtin",
                version=1,
            )
        )
        await db_session.commit()

        payload = {
            "type": "StaticPortsBlock",
            "display_name": "静态端口块",
            "category": "custom",
            "nodes": [
                {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
                 "data": {"parameters": {"name": "x"}}},
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
                {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
                 "data": {"parameters": {"name": "out"}}},
            ],
            "edges": [
                {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
                {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
            ],
            "params_schema": [],
        }
        response = await admin_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 201
        data = response.json()["data"]
        # input_ports_dynamic 应为 False（非动态端口）
        assert data["input_ports_dynamic"] is False
        assert data["schema_json"]["input_ports_dynamic"] is False

    @pytest.mark.asyncio
    async def test_canvas_conversion_error(self, admin_client: AsyncClient) -> None:
        """缺少 InputPort → 400"""
        payload = {
            "type": "BadBlock",
            "display_name": "坏模块",
            "category": "custom",
            "nodes": [
                {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
                 "data": {"moduleType": "Conv2d", "parameters": {}}},
            ],
            "edges": [],
            "params_schema": [],
        }
        response = await admin_client.post("/api/v1/models/modules", json=payload)
        assert response.status_code == 400
