"""
FocusFeature（论文原名，对应此前误称为 FDPN 的模块）

结构：3 进 1 出
输入顺序: [P5, P4, P3]

P5 → Upsample(×2) → Conv1×1(inc[0]→hidc)
P4 → Conv1×1(inc[1]→hidc)   # 若 e==1 则为 Identity
P3 → ADown(inc[2]→hidc)

x = cat([P5, P4, P3], dim=1)   # 通道 = hidc * 3
feature = sum([x] + [dw_k(x) for dw_k in dw_convs])   # kernel_sizes 默认 (5,7,9,11)
feature = pw_conv(feature)
return x + feature

对外参数：
  inc (list of 3 int)
  kernel_sizes (tuple, default (5,7,9,11))
  e (float, default 0.5)   → hidc = int(inc[1] * e)
"""
import torch
import torch.nn as nn

from app.ml.modules.composite.adown.module import ADown


class FocusFeature(nn.Module):
    def __init__(self, inc, kernel_sizes=(5, 7, 9, 11), e=0.5):
        super().__init__()
        self.inc = inc
        self.kernel_sizes = kernel_sizes
        self.e = e

        hidc = int(inc[1] * e)
        self.hidc = hidc
        cat_channels = hidc * 3

        # P5 branch
        self.p5_up = nn.Upsample(scale_factor=2, mode="nearest")
        self.p5_conv = nn.Conv2d(inc[0], hidc, 1, bias=False)

        # P4 branch
        if e == 1:
            self.p4_conv = nn.Identity()
        else:
            self.p4_conv = nn.Conv2d(inc[1], hidc, 1, bias=False)

        # P3 branch
        self.p3_down = ADown(inc[2], hidc)

        # DW convs on concatenated features
        self.dw_convs = nn.ModuleList([
            nn.Conv2d(cat_channels, cat_channels, k, padding=k // 2, groups=cat_channels, bias=False)
            for k in kernel_sizes
        ])

        # Pointwise conv
        self.pw_conv = nn.Conv2d(cat_channels, cat_channels, 1, bias=False)

    def forward(self, p5, p4, p3):
        # 空间/通道对齐
        p5 = self.p5_up(p5)
        p5 = self.p5_conv(p5)

        p4 = self.p4_conv(p4)

        p3 = self.p3_down(p3)

        # 拼接
        x = torch.cat([p5, p4, p3], dim=1)

        # DW 分支并行求和
        feature = x + sum(dw(x) for dw in self.dw_convs)

        # Pointwise
        feature = self.pw_conv(feature)

        # 残差
        return x + feature
