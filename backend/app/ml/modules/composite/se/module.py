"""
SE（Squeeze-and-Excitation）

参考：Hu et al. "Squeeze-and-Excitation Networks" (CVPR 2018)
https://arxiv.org/abs/1709.01507

结构：GAP → FC(1×1 Conv 降维) → ReLU → FC(1×1 Conv 升维) → Sigmoid → scale

参数：
  in_channels: 输入通道
  reduction_ratio: 压缩比（默认16）
"""
import torch
import torch.nn as nn


class SE(nn.Module):
    def __init__(self, in_channels: int = 64, reduction_ratio: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(in_channels, in_channels // reduction_ratio, 1, bias=False)
        self.relu = nn.ReLU()
        self.fc2 = nn.Conv2d(in_channels // reduction_ratio, in_channels, 1, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.avg_pool(x)
        y = self.fc1(y)
        y = self.relu(y)
        y = self.fc2(y)
        y = self.sigmoid(y)
        return x * y
