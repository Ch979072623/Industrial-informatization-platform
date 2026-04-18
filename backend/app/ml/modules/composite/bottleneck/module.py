"""
Bottleneck（标准残差瓶颈）

结构：Conv(k=3) → Conv(k=3) + shortcut
参数：c1, c2, shortcut, g, e
"""
import torch
import torch.nn as nn


class Bottleneck(nn.Module):
    def __init__(self, c1, c2, shortcut=True, g=1, e=1.0):
        super().__init__()
        c_ = int(c2 * e)
        self.cv1 = nn.Conv2d(c1, c_, 3, 1, 3 // 2, groups=g, bias=False)
        self.cv2 = nn.Conv2d(c_, c2, 3, 1, 3 // 2, groups=g, bias=False)
        self.add = shortcut and c1 == c2

    def forward(self, x):
        return x + self.cv2(self.cv1(x)) if self.add else self.cv2(self.cv1(x))
