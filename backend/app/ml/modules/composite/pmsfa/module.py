"""
PMSFA（Parallel Multi-Scale Feature Aggregation）

论文源码实现：串行递进 chunk，不是并行 split。

结构：
  x → Conv(inc→inc, 3×3) → chunk2 → (h1, h2)
  h1 → Conv(inc/2→inc/2, 5×5, g=inc/2) → chunk2 → (h3, h4)
  h3 → Conv(inc/4→inc/4, 7×7, g=inc/4) → h5
  out = cat([h5, h4, h2], dim=1)   # inc/4 + inc/4 + inc/2 = inc
  out = Conv(inc→inc, 1×1)(out) + x   # 残差

约束：inc % 4 == 0
对外参数：inc（输入=输出通道）
"""
import torch
import torch.nn as nn


class PMSFA(nn.Module):
    def __init__(self, inc: int = 64):
        super().__init__()
        if inc % 4 != 0:
            raise ValueError(f"PMSFA requires inc % 4 == 0, got {inc}")
        self.inc = inc

        self.conv_3x3 = nn.Conv2d(inc, inc, 3, 1, 3 // 2, bias=False)
        self.conv_5x5 = nn.Conv2d(inc // 2, inc // 2, 5, 1, 5 // 2, groups=inc // 2, bias=False)
        self.conv_7x7 = nn.Conv2d(inc // 4, inc // 4, 7, 1, 7 // 2, groups=inc // 4, bias=False)
        self.conv_1x1 = nn.Conv2d(inc, inc, 1, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.conv_3x3(x)
        h1, h2 = h.chunk(2, dim=1)
        h3, h4 = self.conv_5x5(h1).chunk(2, dim=1)
        h5 = self.conv_7x7(h3)
        out = torch.cat([h5, h4, h2], dim=1)
        out = self.conv_1x1(out)
        return out + x
