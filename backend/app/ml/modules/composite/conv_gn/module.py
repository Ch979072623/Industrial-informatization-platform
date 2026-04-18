"""
Conv_GN

Conv + GroupNorm + SiLU
论文 Detect_SASD 中使用的基本构建块。
参数：c1, c2, k, s, p, g
"""
import torch.nn as nn


class Conv_GN(nn.Module):
    def __init__(self, c1, c2, k=1, s=1, p=None, g=1):
        super().__init__()
        if p is None:
            p = k // 2
        self.conv = nn.Conv2d(c1, c2, k, s, p, groups=g, bias=False)
        self.gn = nn.GroupNorm(16, c2)
        self.act = nn.SiLU()

    def forward(self, x):
        return self.act(self.gn(self.conv(x)))
