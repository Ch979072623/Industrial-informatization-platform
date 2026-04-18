"""
CBAM（Convolutional Block Attention Module）

参考：Woo et al. "CBAM: Convolutional Block Attention Module" (ECCV 2018)
https://arxiv.org/abs/1807.06521

结构：
1. Channel Attention：
   - GAP + GMP 并行 → 共享 MLP（Conv1×1 降维 → ReLU → Conv1×1 升维）
   - 两路输出相加 → Sigmoid → 与原输入逐元素相乘
2. Spatial Attention：
   - 沿通道维度分别求 mean 和 max，Concat 后 → 7×7 Conv → Sigmoid
   - 与上一步输出逐元素相乘

参数：
  in_channels: 输入通道
  reduction_ratio: MLP 通道压缩比（默认16）
  spatial_kernel: 空间注意力卷积核（默认7）
"""
import torch
import torch.nn as nn


class CBAM(nn.Module):
    def __init__(self, in_channels: int = 64, reduction_ratio: int = 16, spatial_kernel: int = 7):
        super().__init__()
        # Channel Attention
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(in_channels, in_channels // reduction_ratio, 1, bias=False),
            nn.ReLU(),
            nn.Conv2d(in_channels // reduction_ratio, in_channels, 1, bias=False),
        )
        self.sigmoid_ca = nn.Sigmoid()

        # Spatial Attention
        self.conv_spatial = nn.Conv2d(2, 1, spatial_kernel, padding=spatial_kernel // 2, bias=False)
        self.sigmoid_sa = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Channel Attention
        avg_out = self.mlp(self.avg_pool(x))
        max_out = self.mlp(self.max_pool(x))
        ca = self.sigmoid_ca(avg_out + max_out)
        x = x * ca

        # Spatial Attention
        avg_spatial = torch.mean(x, dim=1, keepdim=True)
        max_spatial = torch.max(x, dim=1, keepdim=True)[0]
        spatial_input = torch.cat([avg_spatial, max_spatial], dim=1)
        sa = self.sigmoid_sa(self.conv_spatial(spatial_input))
        x = x * sa
        return x
