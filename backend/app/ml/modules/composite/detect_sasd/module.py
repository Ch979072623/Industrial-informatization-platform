"""
Detect_SASD（论文中的检测头）

结构（3 进 3 出，每个尺度独立处理）：
1. 每层独立: Conv_GN(ch_i → hidc, 3×3)
2. 共享: Sequential(Conv_GN(hidc→hidc, 3×3, g=hidc), Conv_GN(hidc→hidc, 1×1))
3. 共享 reg head: Conv2d(hidc → 4*reg_max, 1)
4. 共享 cls head: Conv2d(hidc → nc, 1)
5. 每层独立: Scale(1.0)   # 可学习标量，只乘 reg 分支
6. 每层输出: cat([scale[i](cv2(x_i)), cv3(x_i)], dim=1)

关键点：
- norm 用 GroupNorm(16, c)，不是 BatchNorm
- 没有 obj（objectness）分支
- 推理态的 DFL 解码 + anchor 生成暂未实现（Phase 5 细化），当前仅训练态 forward

对外参数：nc (default 80), hidc (default 256), ch (list[int]), reg_max (default 16)
"""
import torch
import torch.nn as nn

from app.ml.modules.composite.conv_gn.module import Conv_GN


class Scale(nn.Module):
    """可学习标量缩放"""
    def __init__(self, init_value=1.0):
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(init_value, dtype=torch.float32))

    def forward(self, x):
        return x * self.scale


class Detect_SASD(nn.Module):
    def __init__(self, nc=80, hidc=256, ch=None, reg_max=16):
        super().__init__()
        if ch is None:
            ch = [256, 512, 1024]
        self.nc = nc
        self.hidc = hidc
        self.ch = ch
        self.reg_max = reg_max
        self.no = nc + 4 * reg_max  # 每个位置输出通道数

        # 每层独立的 stem：ch_i → hidc
        self.stems = nn.ModuleList([Conv_GN(c, hidc, 3, 1) for c in ch])

        # 共享 DW + PW
        self.shared = nn.Sequential(
            Conv_GN(hidc, hidc, 3, 1, g=hidc),
            Conv_GN(hidc, hidc, 1, 1),
        )

        # 共享检测头
        self.cv2 = nn.Conv2d(hidc, 4 * reg_max, 1)  # reg
        self.cv3 = nn.Conv2d(hidc, nc, 1)           # cls

        # 每层独立的尺度因子
        self.scale = nn.ModuleList([Scale(1.0) for _ in range(len(ch))])

    def forward(self, x):
        """
        Args:
            x: tuple/list of 3 tensors [n3, n4, n5]
        Returns:
            tuple of 3 tensors, each shape (B, nc + 4*reg_max, H, W)
        """
        outputs = []
        for i, xi in enumerate(x):
            xi = self.stems[i](xi)
            xi = self.shared(xi)
            reg = self.scale[i](self.cv2(xi))
            cls = self.cv3(xi)
            out = torch.cat([reg, cls], dim=1)
            outputs.append(out)
        return tuple(outputs)
