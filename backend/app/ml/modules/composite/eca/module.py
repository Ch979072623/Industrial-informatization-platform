"""
ECA（Efficient Channel Attention）

参考：Wang et al. "ECA-Net: Efficient Channel Attention" (CVPR 2020)
https://arxiv.org/abs/1910.03151

结构：GAP → 1D Conv（自适应 kernel size）→ Sigmoid → scale

自适应 kernel size 公式：
  k = |log2(C) / γ + b / γ|_odd
  其中 γ=2, b=1（默认值），|·|_odd 表示取最接近的奇数。

参数：
  in_channels: 输入通道
  gamma: 控制 kernel size 自适应的系数（默认2）
  b: 偏置项（默认1）
"""
import math
import torch
import torch.nn as nn


class ECA(nn.Module):
    def __init__(self, in_channels: int = 64, gamma: float = 2.0, b: float = 1.0):
        super().__init__()
        kernel_size = int(abs((math.log(in_channels, 2) + b) / gamma))
        kernel_size = kernel_size if kernel_size % 2 else kernel_size + 1

        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv = nn.Conv1d(1, 1, kernel_size, padding=(kernel_size - 1) // 2, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.avg_pool(x)  # (B, C, 1, 1)
        y = y.squeeze(-1).transpose(-1, -2)  # (B, 1, C)
        y = self.conv(y)  # (B, 1, C)
        y = y.transpose(-1, -2).unsqueeze(-1)  # (B, C, 1, 1)
        y = self.sigmoid(y)
        return x * y
