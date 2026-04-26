import { useState, useMemo, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Download, X, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

export interface CodegenResult {
  type: string;
  path?: string;
  error?: string;
  code?: string;
}

export interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  yamlContent: string;
  codegenResults: CodegenResult[];
  error?: string;
  loading?: boolean;
  /** 测试用：强制指定默认激活的 tab */
  defaultActiveTab?: string;
}

interface TabItem {
  id: string;
  label: string;
  language: string;
  content: string;
  filename: string;
  hasError?: boolean;
  errorMessage?: string;
}

function triggerDownload(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ExportDialog({
  open,
  onClose,
  yamlContent,
  codegenResults,
  error,
  loading,
  defaultActiveTab,
}: ExportDialogProps) {
  const tabs: TabItem[] = useMemo(() => {
    const result: TabItem[] = [
      {
        id: 'yaml',
        label: 'model.yaml',
        language: 'yaml',
        content: yamlContent,
        filename: 'model.yaml',
      },
    ];

    for (const cr of codegenResults) {
      result.push({
        id: cr.type,
        label: `${cr.type}.py`,
        language: 'python',
        content: cr.code || '',
        filename: `${cr.type}.py`,
        hasError: !!cr.error,
        errorMessage: cr.error,
      });
    }

    return result;
  }, [yamlContent, codegenResults]);

  const [activeTab, setActiveTab] = useState(defaultActiveTab ?? tabs[0]?.id ?? 'yaml');

  // Reset active tab when dialog opens
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (isOpen) {
        setActiveTab(defaultActiveTab ?? tabs[0]?.id ?? 'yaml');
      } else {
        onClose();
      }
    },
    [onClose, tabs, defaultActiveTab]
  );

  const activeTabItem = tabs.find((t) => t.id === activeTab);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[900px] h-[80vh] flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-2">
          <div className="flex items-center justify-between">
            <DialogTitle>导出模型配置</DialogTitle>
            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>

        {loading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">正在生成导出文件...</p>
          </div>
        )}

        {!loading && error && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6">
            <AlertCircle className="h-10 w-10 text-destructive" />
            <div className="text-center">
              <p className="text-base font-medium text-destructive">导出失败</p>
              <p className="text-sm text-muted-foreground mt-1">{error}</p>
            </div>
          </div>
        )}

        {!loading && !error && tabs.length > 0 && (
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex-1 flex flex-col min-h-0 px-6 pb-6"
          >
            <div className="flex items-center justify-between mb-2">
              <TabsList>
                {tabs.map((tab) => (
                  <TabsTrigger key={tab.id} value={tab.id}>
                    {tab.label}
                    {tab.hasError && (
                      <span className="ml-1 text-destructive">*</span>
                    )}
                  </TabsTrigger>
                ))}
              </TabsList>
              {activeTabItem && !activeTabItem.hasError && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    triggerDownload(activeTabItem.content, activeTabItem.filename)
                  }
                  disabled={loading}
                >
                  <Download className="h-4 w-4 mr-1" />
                  下载
                </Button>
              )}
            </div>

            {tabs.map((tab) => (
              <TabsContent
                key={tab.id}
                value={tab.id}
                className="flex-1 min-h-0 data-[state=inactive]:hidden"
              >
                {tab.hasError ? (
                  <div className="h-full flex flex-col items-center justify-center gap-3 border rounded-md bg-destructive/5">
                    <AlertCircle className="h-8 w-8 text-destructive" />
                    <p className="text-sm text-destructive font-medium">
                      代码生成失败
                    </p>
                    <p className="text-sm text-muted-foreground max-w-md text-center px-4">
                      {tab.errorMessage}
                    </p>
                  </div>
                ) : (
                  <div className="h-full border rounded-md overflow-hidden">
                    <Editor
                      height="100%"
                      language={tab.language}
                      value={tab.content}
                      options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                      }}
                      theme="vs-light"
                    />
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
