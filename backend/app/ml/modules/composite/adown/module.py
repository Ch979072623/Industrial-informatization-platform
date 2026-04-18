"""
ADown

论文中的下采样模块：
  AvgPool2d(2, stride=1) → chunk2 →
    分支0: Conv3×3 stride2
    分支1: MaxPool2d(2, stride=2) → Conv1×1
  → cat

注意：AvgPool stride=1 先做一次尺寸调整，再分两路下采样。
实际使用时要求输入尺寸兼容（通常YOLO backbone中自动满足）。
"""
import torch
import torch.nn as nn


class ADown(nn.Module):
    def __init__(self, c1, c2):
        super().__init__()
        self.c = c2 // 2
        self.avgpool = nn.AvgPool2d(2, stride=1)
        self.cv1 = nn.Conv2d(c1 // 2, self.c, 3, 2, 1, bias=False)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.cv2 = nn.Conv2d(c1 // 2, self.c, 1, 1, 0, bias=False)

    def forward(self, x):
        x = self.avgpool(x)
        x1, x2 = x.chunk(2, dim=1)
        x1 = self.cv1(x1)
        x2 = self.maxpool(x2)
        x2 = self.cv2(x2)
        return torch.cat([x1, x2], dim=1)
