"""
ResBlock（ResNet BasicBlock）

参考：He et al. "Deep Residual Learning for Image Recognition" (CVPR 2015)
https://arxiv.org/abs/1512.03385

注意：本项目统一使用 SiLU 作为激活函数（替代原始论文的 ReLU）。
结构：Conv3×3 → BN → SiLU → Conv3×3 → BN + shortcut

参数：
  in_channels: 输入通道
  out_channels: 输出通道
  stride: 步长（默认1）

shortcut 说明：
标准 ResNet 在 stride=1 且 in_channels==out_channels 时用 Identity shortcut；
否则用 1×1 Conv projection。本实现为了与 schema 可视化统一，
固定使用 1×1 Conv projection shortcut（结果数值等价于 Identity 当权重为 identity 时）。
"""
import torch
import torch.nn as nn


class ResBlock(nn.Module):
    def __init__(self, in_channels: int = 64, out_channels: int = 64, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU()
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

        if stride == 1 and in_channels == out_channels:
            self.shortcut = nn.Identity()
        else:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride, bias=False),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.act(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + self.shortcut(x)
        out = self.act(out)
        return out
