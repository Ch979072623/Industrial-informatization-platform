"""
复合模块等价性测试（论文模块 + 常见模块）

对 PMSFA、FocusFeature、Detect_SASD、ResBlock、ResNetBottleneck、
CBAM、SE、ECA、FPN 分别：
1. 实例化手写 module.py 中的类（参考实现）
2. 加载 schema.json，通过 schema_to_module 动态构图
3. 固定权重（所有 parameter/buffer fill 0.1）
4. 随机输入前向传播
5. 断言输出 shape 一致、数值差 < 1e-4（论文模块 < 1e-5）
"""
import json
from pathlib import Path

import pytest
import torch
import torch.nn as nn

from app.ml.modules.dynamic_builder import schema_to_module

from app.ml.modules.composite.pmsfa.module import PMSFA
from app.ml.modules.composite.focusfeature.module import FocusFeature
from app.ml.modules.composite.detect_sasd.module import Detect_SASD
from app.ml.modules.composite.resblock.module import ResBlock
from app.ml.modules.composite.resnetbottleneck.module import ResNetBottleneck
from app.ml.modules.composite.cbam.module import CBAM
from app.ml.modules.composite.se.module import SE
from app.ml.modules.composite.eca.module import ECA
from app.ml.modules.composite.fpn.module import FPN

MODULES_DIR = Path(__file__).parent.parent / "app" / "ml" / "modules" / "composite"


def load_schema(name: str):
    path = MODULES_DIR / name / "schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def set_uniform_weights(module: nn.Module, val: float = 0.1):
    """将模块的所有 parameter 和 buffer 设为固定值，确保可复现对比"""
    for p in module.parameters():
        p.data.fill_(val)
    for b in module.buffers():
        b.data.fill_(val)


class TestPMSFA:
    """PMSFA 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("pmsfa")
        params = {"inc": 64}

        ref = PMSFA(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape, f"shape mismatch: {y_ref.shape} vs {y_dyn.shape}"
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestFocusFeature:
    """FocusFeature（原 FDPN）等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("focusfeature")
        params = {
            "inc": [512, 256, 128],
            "kernel_sizes": [5, 7, 9, 11],
            "e": 0.5,
        }

        ref = FocusFeature(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        p5 = torch.randn(2, 512, 16, 16)
        p4 = torch.randn(2, 256, 32, 32)
        p3 = torch.randn(2, 128, 64, 64)

        with torch.no_grad():
            y_ref = ref(p5, p4, p3)
            y_dyn = dyn(p5, p4, p3)

        assert y_ref.shape == y_dyn.shape, f"shape mismatch: {y_ref.shape} vs {y_dyn.shape}"
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestDetectSASD:
    """Detect_SASD 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("detect_sasd")
        params = {
            "nc": 80,
            "hidc": 256,
            "ch": [256, 512, 1024],
            "reg_max": 16,
        }

        ref = Detect_SASD(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        n3 = torch.randn(2, 256, 64, 64)
        n4 = torch.randn(2, 512, 32, 32)
        n5 = torch.randn(2, 1024, 16, 16)

        with torch.no_grad():
            y_ref = ref([n3, n4, n5])   # 论文源码接受 list
            y_dyn = dyn(n3, n4, n5)     # 动态构图接受 unpacked

        assert len(y_ref) == len(y_dyn) == 3
        for i in range(3):
            assert y_ref[i].shape == y_dyn[i].shape, f"Detect_SASD output {i} shape mismatch"
            torch.testing.assert_close(y_ref[i], y_dyn[i], atol=1e-4, rtol=1e-4)


class TestResBlock:
    """ResBlock 等价性测试（projection + identity 双路径）"""

    def test_forward_projection(self):
        """stride=2 触发 projection shortcut，对应 schema.json（带 input_anchor + shortcut_conv）"""
        schema = load_schema("resblock")
        params = {"in_channels": 64, "out_channels": 128, "stride": 2}

        ref = ResBlock(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)

    def test_forward_identity(self):
        """stride=1 且 in_channels==out_channels 触发 identity shortcut，对应 schema_identity.json"""
        schema_path = MODULES_DIR / "resblock" / "schema_identity.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        params = {"in_channels": 64, "out_channels": 64, "stride": 1}

        ref = ResBlock(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestResNetBottleneck:
    """ResNetBottleneck 等价性测试（projection + identity 双路径）"""

    def test_forward_projection(self):
        """stride=2 触发 projection shortcut"""
        schema = load_schema("resnetbottleneck")
        params = {"in_channels": 64, "out_channels": 256, "stride": 2}

        ref = ResNetBottleneck(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)

    def test_forward_identity(self):
        """stride=1 且 in_channels==out_channels 触发 identity shortcut"""
        schema_path = MODULES_DIR / "resnetbottleneck" / "schema_identity.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        params = {"in_channels": 256, "out_channels": 256, "stride": 1}

        ref = ResNetBottleneck(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 256, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestCBAM:
    """CBAM 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("cbam")
        params = {"in_channels": 64, "reduction_ratio": 16, "spatial_kernel": 7}

        ref = CBAM(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestSE:
    """SE 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("se")
        params = {"in_channels": 64, "reduction_ratio": 16}

        ref = SE(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestECA:
    """ECA 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("eca")
        params = {"in_channels": 64, "gamma": 2.0, "b": 1.0}

        ref = ECA(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y_ref = ref(x)
            y_dyn = dyn(x)

        assert y_ref.shape == y_dyn.shape
        torch.testing.assert_close(y_ref, y_dyn, atol=1e-4, rtol=1e-4)


class TestConvGNDefaults:
    """Conv_GN 默认值注入测试（验证 schema 默认值为 None 时表达式仍可访问）"""

    def test_padding_default_none(self):
        """p 不传时，表达式 p if p is not None else k // 2 应走 else 分支"""
        schema = load_schema("conv_gn")
        params = {"c1": 64, "c2": 128, "k": 3, "s": 1}  # 不传 p

        dyn = schema_to_module(schema, params)
        conv = dyn.sub_modules["conv"]
        assert conv.padding == (1, 1)  # k // 2 = 3 // 2 = 1

    def test_padding_zero(self):
        """p=0 时，is not None 为 True，应走 if 分支"""
        schema = load_schema("conv_gn")
        params = {"c1": 64, "c2": 128, "k": 3, "s": 1, "p": 0}

        dyn = schema_to_module(schema, params)
        conv = dyn.sub_modules["conv"]
        assert conv.padding == (0, 0)

    def test_padding_two(self):
        """p=2 时，应走 if 分支"""
        schema = load_schema("conv_gn")
        params = {"c1": 64, "c2": 128, "k": 3, "s": 1, "p": 2}

        dyn = schema_to_module(schema, params)
        conv = dyn.sub_modules["conv"]
        assert conv.padding == (2, 2)


class TestFPN:
    """FPN 等价性测试"""

    def test_forward_shape_and_value(self):
        schema = load_schema("fpn")
        params = {"in_channels_list": [512, 256, 128], "out_channels": 256}

        ref = FPN(**params)
        dyn = schema_to_module(schema, params)

        set_uniform_weights(ref)
        set_uniform_weights(dyn)

        p5 = torch.randn(2, 512, 16, 16)
        p4 = torch.randn(2, 256, 32, 32)
        p3 = torch.randn(2, 128, 64, 64)

        with torch.no_grad():
            y_ref = ref(p5, p4, p3)
            y_dyn = dyn(p5, p4, p3)

        assert len(y_ref) == len(y_dyn) == 3
        for i in range(3):
            assert y_ref[i].shape == y_dyn[i].shape, f"FPN output {i} shape mismatch"
            torch.testing.assert_close(y_ref[i], y_dyn[i], atol=1e-4, rtol=1e-4)
