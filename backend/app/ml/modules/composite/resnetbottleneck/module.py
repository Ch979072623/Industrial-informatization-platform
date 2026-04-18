"""
ResNetBottleneck（ResNet Bottleneck v1）

参考：He et al. "Deep Residual Learning for Image Recognition" (CVPR 2015)
https://arxiv.org/abs/1512.03385

结构：1×1 Conv（降维）→ BN → SiLU → 3×3 Conv → BN → SiLU → 1×1 Conv（升维）→ BN + shortcut

参数：
  in_channels: 输入通道
  out_channels: 输出通道（实际内部中间层通道 = out_channels // 4）
  stride: 步长（默认1）

expansion=4： Bottleneck 的输出通道是中间层的 4 倍。
"""
import torch
import torch.nn as nn


class ResNetBottleneck(nn.Module):
    def __init__(self, in_channels: int = 64, out_channels: int = 256, stride: int = 1):
        super().__init__()
        mid_channels = out_channels // 4

        self.conv1 = nn.Conv2d(in_channels, mid_channels, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(mid_channels)
        self.conv2 = nn.Conv2d(mid_channels, mid_channels, 3, stride, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(mid_channels)
        self.conv3 = nn.Conv2d(mid_channels, out_channels, 1, bias=False)
        self.bn3 = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU()

        if stride == 1 and in_channels == out_channels:
            self.shortcut = nn.Identity()
        else:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride, bias=False),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.act(self.bn1(self.conv1(x)))
        out = self.act(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out = out + self.shortcut(x)
        out = self.act(out)
        return out
