"""
FPN（Feature Pyramid Network）

参考：Lin et al. "Feature Pyramid Networks for Object Detection" (CVPR 2017)
https://arxiv.org/abs/1612.03144

经典 top-down 单路径 FPN：
- 横向连接用 1×1 Conv 统一通道
- 自顶向下用 nearest upsample
- 输出前经 3×3 Conv 平滑

参数：
  in_channels_list: 三个尺度的输入通道 [C5, C4, C3]
  out_channels: 统一后的输出通道

输入/输出顺序：和 FocusFeature 保持一致，从低分辨率到高分辨率（P5, P4, P3）。
"""
import torch
import torch.nn as nn


class FPN(nn.Module):
    def __init__(self, in_channels_list, out_channels: int = 256):
        super().__init__()
        if len(in_channels_list) != 3:
            raise ValueError("in_channels_list 必须为 3 个元素")

        # 横向连接：1×1 Conv 统一通道
        self.lateral_convs = nn.ModuleList([
            nn.Conv2d(c, out_channels, 1, bias=False) for c in in_channels_list
        ])

        # 输出平滑：3×3 Conv
        self.fpn_convs = nn.ModuleList([
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False)
            for _ in range(3)
        ])

        self.upsample = nn.Upsample(scale_factor=2, mode="nearest")

    def forward(self, p5, p4, p3):
        # p5, p4, p3 从低到高分辨率
        n5 = self.lateral_convs[0](p5)
        n4 = self.lateral_convs[1](p4) + self.upsample(n5)
        n3 = self.lateral_convs[2](p3) + self.upsample(n4)

        n3 = self.fpn_convs[0](n3)
        n4 = self.fpn_convs[1](n4)
        n5 = self.fpn_convs[2](n5)

        return n3, n4, n5
