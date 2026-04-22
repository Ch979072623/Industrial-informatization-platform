/**
 * 新建画布弹窗
 *
 * 选择画布模式：Module / Architecture
 */
import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Network, Layers } from 'lucide-react';
import type { CanvasMode } from '@/types/mlModule';

interface NewCanvasDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (mode: CanvasMode) => void;
}

export function NewCanvasDialog({ open, onOpenChange, onConfirm }: NewCanvasDialogProps) {
  const [selectedMode, setSelectedMode] = useState<CanvasMode>('architecture');

  const handleConfirm = () => {
    onConfirm(selectedMode);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>新建画布</DialogTitle>
          <DialogDescription>选择要创建的画布类型</DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <RadioGroup
            value={selectedMode}
            onValueChange={(v: string) => setSelectedMode(v as CanvasMode)}
            className="grid grid-cols-1 gap-4"
          >
            {/* Module 模式 */}
            <div className="flex items-start space-x-3 rounded-lg border p-4 cursor-pointer hover:bg-accent transition-colors">
              <RadioGroupItem value="module" id="mode-module" className="mt-1" />
              <div className="flex-1">
                <Label htmlFor="mode-module" className="flex items-center gap-2 cursor-pointer">
                  <Network className="h-4 w-4 text-primary" />
                  <span className="font-medium">模块模式（Module）</span>
                </Label>
                <p className="text-xs text-muted-foreground mt-1 pl-6">
                  定义一个可复用的子网络模块（将写入模块库）
                </p>
              </div>
            </div>

            {/* Architecture 模式 */}
            <div className="flex items-start space-x-3 rounded-lg border p-4 cursor-pointer hover:bg-accent transition-colors">
              <RadioGroupItem value="architecture" id="mode-architecture" className="mt-1" />
              <div className="flex-1">
                <Label htmlFor="mode-architecture" className="flex items-center gap-2 cursor-pointer">
                  <Layers className="h-4 w-4 text-primary" />
                  <span className="font-medium">架构模式（Architecture）</span>
                </Label>
                <p className="text-xs text-muted-foreground mt-1 pl-6">
                  定义一个完整的 YOLO 模型架构
                </p>
              </div>
            </div>
          </RadioGroup>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleConfirm}>确认创建</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default NewCanvasDialog;
