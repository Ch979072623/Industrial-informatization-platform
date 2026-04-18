"""
C2f（YOLOv8 跨阶段部分瓶颈）

结构：Conv1×1 → Chunk2 → [part0, part1, b0_out, b1_out, ...] → Concat → Conv1×1
参数：c1, c2, n, shortcut, g, e
"""
import torch
import torch.nn as nn

from app.ml.modules.composite.bottleneck.module import Bottleneck


class C2f(nn.Module):
    def __init__(self, c1, c2, n=1, shortcut=False, g=1, e=0.5):
        super().__init__()
        self.c = int(c2 * e)
        self.cv1 = nn.Conv2d(c1, 2 * self.c, 1, 1, bias=False)
        self.cv2 = nn.Conv2d((2 + n) * self.c, c2, 1, bias=False)
        self.m = nn.ModuleList(
            Bottleneck(self.c, self.c, shortcut, g, e=1.0) for _ in range(n)
        )

    def forward(self, x):
        y = list(self.cv1(x).chunk(2, dim=1))
        y.extend(m(y[-1]) for m in self.m)
        return self.cv2(torch.cat(y, dim=1))
