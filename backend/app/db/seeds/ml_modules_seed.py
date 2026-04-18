"""
机器学习模块种子数据

初始化内置神经网络模块，包括：
1. 基础层：Conv2d, BatchNorm2d, ReLU, MaxPool2d, etc.
2. 骨干网络：PMSFA（论文中的自定义模块）
3. 颈部网络：FDPN（论文中的自定义模块）
4. 检测头：SASD（论文中的自定义模块）
5. YOLO11 标准模块：C2f, SPPF, etc.

使用方法:
    from app.db.seeds.ml_modules_seed import seed_builtin_modules
    await seed_builtin_modules(db_session)
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ml_module import MLModule

logger = logging.getLogger(__name__)


# ==================== 内置模块定义 ====================

BUILTIN_MODULES: List[Dict[str, Any]] = [
    # ========== 基础层 (Basic Layers) ==========
    {
        "name": "Conv2d",
        "display_name": "2D卷积层",
        "category": "basic",
        "type": "layer",
        "description": "标准的2D卷积层，用于提取空间特征",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 1,
                    "maximum": 2048,
                    "default": 64
                },
                "kernel_size": {
                    "type": "integer",
                    "title": "卷积核大小",
                    "enum": [1, 3, 5, 7],
                    "default": 3
                },
                "stride": {
                    "type": "integer",
                    "title": "步长",
                    "enum": [1, 2],
                    "default": 1
                },
                "padding": {
                    "type": "integer",
                    "title": "填充",
                    "minimum": 0,
                    "maximum": 10,
                    "default": 1
                },
                "bias": {
                    "type": "boolean",
                    "title": "使用偏置",
                    "default": False
                }
            },
            "required": ["out_channels", "kernel_size"]
        },
        "default_parameters": {
            "out_channels": 64,
            "kernel_size": 3,
            "stride": 1,
            "padding": 1,
            "bias": False
        },
        "code_template": "nn.Conv2d(in_channels={in_channels}, out_channels={out_channels}, kernel_size={kernel_size}, stride={stride}, padding={padding}, bias={bias})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,out_channels,H/stride,W/stride]"}],
        "icon": "square",
        "sort_order": 1
    },
    {
        "name": "BatchNorm2d",
        "display_name": "批量归一化",
        "category": "basic",
        "type": "layer",
        "description": "2D批量归一化层，加速训练收敛",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "num_features": {
                    "type": "integer",
                    "title": "特征数量",
                    "minimum": 1,
                    "default": 64
                },
                "eps": {
                    "type": "number",
                    "title": "epsilon",
                    "default": 1e-5
                },
                "momentum": {
                    "type": "number",
                    "title": "动量",
                    "default": 0.1
                }
            },
            "required": ["num_features"]
        },
        "default_parameters": {
            "num_features": 64,
            "eps": 1e-5,
            "momentum": 0.1
        },
        "code_template": "nn.BatchNorm2d(num_features={num_features}, eps={eps}, momentum={momentum})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,C,H,W]"}],
        "icon": "layers",
        "sort_order": 2
    },
    {
        "name": "ReLU",
        "display_name": "ReLU激活",
        "category": "basic",
        "type": "layer",
        "description": "ReLU激活函数，引入非线性",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "inplace": {
                    "type": "boolean",
                    "title": "原地操作",
                    "default": True
                }
            }
        },
        "default_parameters": {
            "inplace": True
        },
        "code_template": "nn.ReLU(inplace={inplace})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "auto"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "auto"}],
        "icon": "zap",
        "sort_order": 3
    },
    {
        "name": "MaxPool2d",
        "display_name": "最大池化",
        "category": "basic",
        "type": "layer",
        "description": "2D最大池化层，降低空间维度",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "kernel_size": {
                    "type": "integer",
                    "title": "池化核大小",
                    "enum": [2, 3],
                    "default": 2
                },
                "stride": {
                    "type": "integer",
                    "title": "步长",
                    "enum": [1, 2],
                    "default": 2
                }
            },
            "required": ["kernel_size"]
        },
        "default_parameters": {
            "kernel_size": 2,
            "stride": 2
        },
        "code_template": "nn.MaxPool2d(kernel_size={kernel_size}, stride={stride})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,C,H/kernel_size,W/kernel_size]"}],
        "icon": "shrink",
        "sort_order": 4
    },
    {
        "name": "AdaptiveAvgPool2d",
        "display_name": "自适应平均池化",
        "category": "basic",
        "type": "layer",
        "description": "自适应平均池化到指定输出尺寸",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "output_size": {
                    "type": "integer",
                    "title": "输出尺寸",
                    "enum": [1, 7, 14],
                    "default": 1
                }
            },
            "required": ["output_size"]
        },
        "default_parameters": {
            "output_size": 1
        },
        "code_template": "nn.AdaptiveAvgPool2d(output_size={output_size})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,C,output_size,output_size]"}],
        "icon": "minimize",
        "sort_order": 5
    },
    
    # ========== 骨干网络 (Backbone) ==========
    {
        "name": "PMSFA",
        "display_name": "并行多尺度特征聚合",
        "category": "backbone",
        "type": "block",
        "description": "论文中的PMSFA模块：渐进式通道划分 + 并行深度可分离卷积，实现高效多尺度特征提取",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "channels": {
                    "type": "integer",
                    "title": "通道数",
                    "minimum": 16,
                    "maximum": 2048,
                    "default": 256
                },
                "num_scales": {
                    "type": "integer",
                    "title": "尺度数量",
                    "minimum": 2,
                    "maximum": 4,
                    "default": 3
                },
                "reduction_ratio": {
                    "type": "number",
                    "title": "通道缩减比例",
                    "minimum": 0.1,
                    "maximum": 1.0,
                    "default": 0.25
                },
                "use_se": {
                    "type": "boolean",
                    "title": "使用SE注意力",
                    "default": True
                }
            },
            "required": ["channels"]
        },
        "default_parameters": {
            "channels": 256,
            "num_scales": 3,
            "reduction_ratio": 0.25,
            "use_se": True
        },
        "code_template": "PMSFA(channels={channels}, num_scales={num_scales}, reduction_ratio={reduction_ratio}, use_se={use_se})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,C,H,W]"}],
        "icon": "git-merge",
        "sort_order": 1
    },
    {
        "name": "C2f",
        "display_name": "C2f模块",
        "category": "backbone",
        "type": "block",
        "description": "YOLO11的C2f模块：跨阶段部分瓶颈结构，结合CSP和ELAN的优点",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 16,
                    "maximum": 2048,
                    "default": 256
                },
                "n": {
                    "type": "integer",
                    "title": "Bottleneck重复次数",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 3
                },
                "shortcut": {
                    "type": "boolean",
                    "title": "使用快捷连接",
                    "default": True
                },
                "e": {
                    "type": "number",
                    "title": "通道扩展系数",
                    "minimum": 0.25,
                    "maximum": 1.0,
                    "default": 0.5
                }
            },
            "required": ["out_channels"]
        },
        "default_parameters": {
            "out_channels": 256,
            "n": 3,
            "shortcut": True,
            "e": 0.5
        },
        "code_template": "C2f(c1={in_channels}, c2={out_channels}, n={n}, shortcut={shortcut}, e={e})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,out_channels,H,W]"}],
        "icon": "box",
        "sort_order": 2
    },
    {
        "name": "SPPF",
        "display_name": "快速空间金字塔池化",
        "category": "backbone",
        "type": "block",
        "description": "SPPF模块：串行执行多个MaxPool，比SPP更快且效果相当",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 16,
                    "maximum": 2048,
                    "default": 256
                },
                "kernel_size": {
                    "type": "integer",
                    "title": "池化核大小",
                    "enum": [3, 5],
                    "default": 5
                }
            },
            "required": ["out_channels"]
        },
        "default_parameters": {
            "out_channels": 256,
            "kernel_size": 5
        },
        "code_template": "SPPF(c1={in_channels}, c2={out_channels}, k={kernel_size})",
        "input_ports": [{"name": "input", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,out_channels,H,W]"}],
        "icon": "layers",
        "sort_order": 3
    },
    
    # ========== 颈部网络 (Neck) ==========
    {
        "name": "FDPN",
        "display_name": "特征动态金字塔网络",
        "category": "neck",
        "type": "block",
        "description": "论文中的FDPN模块：语义与细节的双向融合，高层特征注入位置敏感信息，底层特征引入语义增强",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "in_channels": {
                    "type": "array",
                    "title": "输入通道数列表",
                    "items": {"type": "integer"},
                    "default": [256, 512, 1024]
                },
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 64,
                    "maximum": 1024,
                    "default": 256
                },
                "fusion_type": {
                    "type": "string",
                    "title": "融合类型",
                    "enum": ["bidirectional", "top_down", "bottom_up"],
                    "default": "bidirectional"
                }
            },
            "required": ["out_channels"]
        },
        "default_parameters": {
            "in_channels": [256, 512, 1024],
            "out_channels": 256,
            "fusion_type": "bidirectional"
        },
        "code_template": "FDPN(in_channels={in_channels}, out_channels={out_channels}, fusion_type={fusion_type})",
        "input_ports": [
            {"name": "p3", "type": "tensor", "shape": "[B,C1,H/8,W/8]"},
            {"name": "p4", "type": "tensor", "shape": "[B,C2,H/16,W/16]"},
            {"name": "p5", "type": "tensor", "shape": "[B,C3,H/32,W/32]"}
        ],
        "output_ports": [
            {"name": "n3", "type": "tensor", "shape": "[B,out_channels,H/8,W/8]"},
            {"name": "n4", "type": "tensor", "shape": "[B,out_channels,H/16,W/16]"},
            {"name": "n5", "type": "tensor", "shape": "[B,out_channels,H/32,W/32]"}
        ],
        "icon": "git-branch",
        "sort_order": 1
    },
    {
        "name": "FPN",
        "display_name": "特征金字塔网络",
        "category": "neck",
        "type": "block",
        "description": "标准FPN：自顶向下的特征金字塔融合",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "in_channels": {
                    "type": "array",
                    "title": "输入通道数列表",
                    "items": {"type": "integer"},
                    "default": [256, 512, 1024]
                },
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 64,
                    "maximum": 1024,
                    "default": 256
                }
            },
            "required": ["out_channels"]
        },
        "default_parameters": {
            "in_channels": [256, 512, 1024],
            "out_channels": 256
        },
        "code_template": "FPN(in_channels={in_channels}, out_channels={out_channels})",
        "input_ports": [
            {"name": "c3", "type": "tensor", "shape": "[B,C1,H/8,W/8]"},
            {"name": "c4", "type": "tensor", "shape": "[B,C2,H/16,W/16]"},
            {"name": "c5", "type": "tensor", "shape": "[B,C3,H/32,W/32]"}
        ],
        "output_ports": [
            {"name": "p3", "type": "tensor", "shape": "[B,out_channels,H/8,W/8]"},
            {"name": "p4", "type": "tensor", "shape": "[B,out_channels,H/16,W/16]"},
            {"name": "p5", "type": "tensor", "shape": "[B,out_channels,H/32,W/32]"}
        ],
        "icon": "pyramid",
        "sort_order": 2
    },
    {
        "name": "PANet",
        "display_name": "PANet结构",
        "category": "neck",
        "type": "block",
        "description": "PANet：在FPN基础上增加自底向上的路径增强",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "in_channels": {
                    "type": "array",
                    "title": "输入通道数列表",
                    "items": {"type": "integer"},
                    "default": [256, 512, 1024]
                },
                "out_channels": {
                    "type": "integer",
                    "title": "输出通道数",
                    "minimum": 64,
                    "maximum": 1024,
                    "default": 256
                }
            },
            "required": ["out_channels"]
        },
        "default_parameters": {
            "in_channels": [256, 512, 1024],
            "out_channels": 256
        },
        "code_template": "PANet(in_channels={in_channels}, out_channels={out_channels})",
        "input_ports": [
            {"name": "c3", "type": "tensor", "shape": "[B,C1,H/8,W/8]"},
            {"name": "c4", "type": "tensor", "shape": "[B,C2,H/16,W/16]"},
            {"name": "c5", "type": "tensor", "shape": "[B,C3,H/32,W/32]"}
        ],
        "output_ports": [
            {"name": "n3", "type": "tensor", "shape": "[B,out_channels,H/8,W/8]"},
            {"name": "n4", "type": "tensor", "shape": "[B,out_channels,H/16,W/16]"},
            {"name": "n5", "type": "tensor", "shape": "[B,out_channels,H/32,W/32]"}
        ],
        "icon": "network",
        "sort_order": 3
    },
    
    # ========== 检测头 (Head) ==========
    {
        "name": "SASD",
        "display_name": "尺度感知解耦检测头",
        "category": "head",
        "type": "block",
        "description": "论文中的SASD模块：轻量级并行分支分别处理分类和定位任务，并基于特征统计动态调整权重",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "in_channels": {
                    "type": "integer",
                    "title": "输入通道数",
                    "minimum": 64,
                    "maximum": 1024,
                    "default": 256
                },
                "num_classes": {
                    "type": "integer",
                    "title": "类别数量",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 80
                },
                "num_layers": {
                    "type": "integer",
                    "title": "卷积层数",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2
                }
            },
            "required": ["in_channels", "num_classes"]
        },
        "default_parameters": {
            "in_channels": 256,
            "num_classes": 80,
            "num_layers": 2
        },
        "code_template": "SASD(in_channels={in_channels}, num_classes={num_classes}, num_layers={num_layers})",
        "input_ports": [{"name": "features", "type": "tensor", "shape": "[B,C,H,W]"}],
        "output_ports": [
            {"name": "cls_output", "type": "tensor", "shape": "[B,num_classes,H,W]"},
            {"name": "reg_output", "type": "tensor", "shape": "[B,4,H,W]"}
        ],
        "icon": "target",
        "sort_order": 1
    },
    {
        "name": "Detect",
        "display_name": "YOLO检测头",
        "category": "head",
        "type": "block",
        "description": "标准YOLO检测头：解耦分类和回归分支",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "nc": {
                    "type": "integer",
                    "title": "类别数量",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 80
                },
                "anchors": {
                    "type": "integer",
                    "title": "每位置的anchor数量",
                    "minimum": 1,
                    "maximum": 9,
                    "default": 3
                }
            },
            "required": ["nc"]
        },
        "default_parameters": {
            "nc": 80,
            "anchors": 3
        },
        "code_template": "Detect(nc={nc}, anchors={anchors})",
        "input_ports": [
            {"name": "p3", "type": "tensor", "shape": "[B,C,H/8,W/8]"},
            {"name": "p4", "type": "tensor", "shape": "[B,C,H/16,W/16]"},
            {"name": "p5", "type": "tensor", "shape": "[B,C,H/32,W/32]"}
        ],
        "output_ports": [{"name": "output", "type": "tensor", "shape": "[B,anchors*(5+nc),num_anchors]"}],
        "icon": "crosshair",
        "sort_order": 2
    },
]


async def seed_builtin_modules(db: AsyncSession) -> None:
    """
    初始化内置神经网络模块
    
    Args:
        db: 数据库会话
    """
    logger.info("开始初始化内置神经网络模块...")
    
    added_count = 0
    skipped_count = 0
    
    for module_data in BUILTIN_MODULES:
        # 检查模块是否已存在
        result = await db.execute(
            select(MLModule).where(MLModule.name == module_data["name"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.debug(f"模块 '{module_data['name']}' 已存在，跳过")
            skipped_count += 1
            continue
        
        # 创建新模块
        module = MLModule(
            name=module_data["name"],
            display_name=module_data["display_name"],
            category=module_data["category"],
            type=module_data["type"],
            description=module_data.get("description"),
            parameters_schema=module_data["parameters_schema"],
            default_parameters=module_data["default_parameters"],
            code_template=module_data.get("code_template"),
            input_ports=module_data["input_ports"],
            output_ports=module_data["output_ports"],
            icon=module_data.get("icon"),
            is_builtin=True,
            is_custom=False,
            created_by=None,  # 内置模块无创建者
            sort_order=module_data.get("sort_order", 0),
            is_active=True
        )
        
        db.add(module)
        added_count += 1
        logger.debug(f"添加模块: {module_data['name']}")
    
    await db.commit()
    logger.info(f"内置模块初始化完成: 新增 {added_count} 个, 跳过 {skipped_count} 个")


async def reset_builtin_modules(db: AsyncSession) -> None:
    """
    重置所有内置模块（仅用于开发/测试）
    
    删除所有内置模块并重新创建
    
    Args:
        db: 数据库会话
    """
    logger.warning("重置内置模块...")
    
    # 删除所有内置模块
    from sqlalchemy import delete
    await db.execute(delete(MLModule).where(MLModule.is_builtin == True))
    await db.commit()
    
    # 重新创建
    await seed_builtin_modules(db)
    logger.info("内置模块重置完成")
