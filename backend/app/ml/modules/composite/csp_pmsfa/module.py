"""
CSP_PMSFA = C2f with PMSFA replacing Bottleneck

结构同 C2f，但内部 Bottleneck 列表替换为 PMSFA 列表。
对外参数：c1, c2, n, shortcut, g, e
"""
import torch
import torch.nn as nn

from app.ml.modules.composite.pmsfa.module import PMSFA


class CSP_PMSFA(nn.Module):
    def __init__(self, c1, c2, n=1, shortcut=False, g=1, e=0.5):
        super().__init__()
        self.c = int(c2 * e)
        self.cv1 = nn.Conv2d(c1, 2 * self.c, 1, 1, bias=False)
        self.cv2 = nn.Conv2d((2 + n) * self.c, c2, 1, bias=False)
        self.m = nn.ModuleList(PMSFA(self.c) for _ in range(n))

    def forward(self, x):
        y = list(self.cv1(x).chunk(2, dim=1))
        y.extend(m(y[-1]) for m in self.m)
        return self.cv2(torch.cat(y, dim=1))
