/**
 * 数据增强状态管理
 * 
 * 使用 Zustand 管理增强流水线和任务状态
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { augmentationApi } from '@/services/api';
import type {
  AugmentationState,
  AugmentationOperation,
  AugmentationOperationDefinition,
  AugmentationTemplate,
  CreateTemplateRequest,
  UpdateTemplateRequest,
  AugmentationJob,
  CreateJobRequest,
  JobListQuery,
  PreviewRequest,
  UploadScriptRequest,
} from '@/types/augmentation';

// 生成唯一 ID
let idCounter = 0;
const generateId = () => `op_${Date.now()}_${++idCounter}`;

// 创建默认操作
const createDefaultOperation = (
  definition: AugmentationOperationDefinition,
  order: number
): AugmentationOperation => {
  const operation: AugmentationOperation = {
    id: generateId(),
    operation_type: definition.operation_type,
    name: definition.name,
    description: definition.description,
    probability: 1.0,
    enabled: true,
    order,
  };

  // 根据操作类型设置默认参数
  definition.parameters.forEach((param) => {
    if (param.name !== 'probability') {
      operation[param.name] = param.default;
    }
  });

  return operation;
};

export const useAugmentationStore = create<AugmentationState>()(
  immer((set, get) => ({
    // ============ 初始状态 ============
    operations: [],
    categories: [],
    operationsLoading: false,
    operationsError: null,

    pipeline: [],
    selectedOperationId: null,

    templates: [],
    templatesLoading: false,
    templatesError: null,

    jobs: [],
    currentJob: null,
    jobsLoading: false,
    jobsError: null,

    preview: null,
    previewLoading: false,
    previewError: null,

    customScripts: [],
    scriptsLoading: false,
    scriptsError: null,

    // ============ 操作定义 Actions ============
    fetchOperations: async () => {
      set((state) => {
        state.operationsLoading = true;
        state.operationsError = null;
      });

      try {
        const response = await augmentationApi.getOperations();
        if (response.data.success) {
          set((state) => {
            state.operations = response.data.data.operations;
            state.categories = response.data.data.categories;
            state.operationsLoading = false;
          });
        } else {
          throw new Error(response.data.message);
        }
      } catch (error) {
        set((state) => {
          state.operationsError = error instanceof Error ? error.message : '获取操作列表失败';
          state.operationsLoading = false;
        });
      }
    },

    // ============ 流水线 Actions ============
    addToPipeline: (definition) => {
      set((state) => {
        const newOperation = createDefaultOperation(definition, state.pipeline.length);
        state.pipeline.push(newOperation);
      });
    },

    updatePipelineItem: (index, operation) => {
      set((state) => {
        if (index >= 0 && index < state.pipeline.length) {
          state.pipeline[index] = operation;
        }
      });
    },

    removeFromPipeline: (index) => {
      set((state) => {
        state.pipeline.splice(index, 1);
        // 更新剩余项的顺序
        state.pipeline.forEach((op, i) => {
          op.order = i;
        });
      });
    },

    movePipelineItem: (fromIndex, toIndex) => {
      set((state) => {
        if (fromIndex < 0 || fromIndex >= state.pipeline.length) return;
        if (toIndex < 0 || toIndex >= state.pipeline.length) return;

        const [movedItem] = state.pipeline.splice(fromIndex, 1);
        state.pipeline.splice(toIndex, 0, movedItem);

        // 更新顺序
        state.pipeline.forEach((op, i) => {
          op.order = i;
        });
      });
    },

    clearPipeline: () => {
      set((state) => {
        state.pipeline = [];
      });
    },

    setPipeline: (newPipeline) => {
      set((state) => {
        state.pipeline = [...newPipeline];
      });
    },

    loadTemplateToPipeline: (template) => {
      set((state) => {
        state.pipeline = template.pipeline_config.map((op, index) => ({
          ...op,
          id: op.id || generateId(),
          order: index,
        }));
      });
    },

    setSelectedOperationId: (id) => {
      set((state) => {
        state.selectedOperationId = id;
      });
    },

    // ============ 模板 Actions ============
    fetchTemplates: async () => {
      set((state) => {
        state.templatesLoading = true;
        state.templatesError = null;
      });

      try {
        const response = await augmentationApi.getTemplates();
        if (response.data.success) {
          set((state) => {
            state.templates = response.data.data.items;
            state.templatesLoading = false;
          });
        } else {
          throw new Error(response.data.message);
        }
      } catch (error) {
        set((state) => {
          state.templatesError = error instanceof Error ? error.message : '获取模板列表失败';
          state.templatesLoading = false;
        });
      }
    },

    createTemplate: async (data) => {
      const response = await augmentationApi.createTemplate(data);
      if (response.data.success) {
        set((state) => {
          state.templates.unshift(response.data.data);
        });
        return response.data.data;
      }
      throw new Error(response.data.message);
    },

    updateTemplate: async (id, data) => {
      const response = await augmentationApi.updateTemplate(id, data);
      if (response.data.success) {
        set((state) => {
          const index = state.templates.findIndex((t) => t.id === id);
          if (index !== -1) {
            state.templates[index] = response.data.data;
          }
        });
      } else {
        throw new Error(response.data.message);
      }
    },

    deleteTemplate: async (id) => {
      const response = await augmentationApi.deleteTemplate(id);
      if (response.data.success) {
        set((state) => {
          state.templates = state.templates.filter((t) => t.id !== id);
        });
      } else {
        throw new Error(response.data.message);
      }
    },

    // ============ 任务 Actions ============
    fetchJobs: async (query) => {
      set((state) => {
        state.jobsLoading = true;
        state.jobsError = null;
      });

      try {
        const response = await augmentationApi.getJobs(query);
        if (response.data.success) {
          set((state) => {
            state.jobs = response.data.data.items;
            state.jobsLoading = false;
          });
        } else {
          throw new Error(response.data.message);
        }
      } catch (error) {
        set((state) => {
          state.jobsError = error instanceof Error ? error.message : '获取任务列表失败';
          state.jobsLoading = false;
        });
      }
    },

    createJob: async (data) => {
      const response = await augmentationApi.createJob(data);
      if (response.data.success) {
        set((state) => {
          state.jobs.unshift(response.data.data);
          state.currentJob = response.data.data;
        });
        return response.data.data;
      }
      throw new Error(response.data.message);
    },

    controlJob: async (jobId, action) => {
      const response = await augmentationApi.controlJob(jobId, { action });
      if (response.data.success) {
        set((state) => {
          const job = state.jobs.find((j) => j.id === jobId);
          if (job) {
            job.status = response.data.data.new_status;
          }
          if (state.currentJob?.id === jobId) {
            state.currentJob.status = response.data.data.new_status;
          }
        });
      } else {
        throw new Error(response.data.message);
      }
    },

    fetchJobProgress: async (jobId) => {
      const response = await augmentationApi.getJobProgress(jobId);
      if (response.data.success) {
        set((state) => {
          const job = state.jobs.find((j) => j.id === jobId);
          if (job) {
            job.progress = response.data.data.progress;
            job.processed_count = response.data.data.processed_count;
            job.total_count = response.data.data.total_count;
            job.generated_count = response.data.data.generated_count;
            job.status = response.data.data.status;
          }
          if (state.currentJob?.id === jobId) {
            state.currentJob.progress = response.data.data.progress;
            state.currentJob.processed_count = response.data.data.processed_count;
            state.currentJob.total_count = response.data.data.total_count;
            state.currentJob.generated_count = response.data.data.generated_count;
            state.currentJob.status = response.data.data.status;
          }
        });
        return response.data.data;
      }
      throw new Error(response.data.message);
    },

    // ============ 预览 Actions ============
    generatePreview: async (data) => {
      set((state) => {
        state.previewLoading = true;
        state.previewError = null;
      });

      try {
        const response = await augmentationApi.createPreview(data);
        if (response.data.success) {
          set((state) => {
            state.preview = response.data.data;
            state.previewLoading = false;
          });
        } else {
          throw new Error(response.data.message);
        }
      } catch (error) {
        set((state) => {
          state.previewError = error instanceof Error ? error.message : '生成预览失败';
          state.previewLoading = false;
        });
      }
    },

    // ============ 自定义脚本 Actions ============
    fetchCustomScripts: async () => {
      set((state) => {
        state.scriptsLoading = true;
        state.scriptsError = null;
      });

      try {
        const response = await augmentationApi.getCustomScripts();
        if (response.data.success) {
          set((state) => {
            state.customScripts = response.data.data.items;
            state.scriptsLoading = false;
          });
        } else {
          throw new Error(response.data.message);
        }
      } catch (error) {
        set((state) => {
          state.scriptsError = error instanceof Error ? error.message : '获取脚本列表失败';
          state.scriptsLoading = false;
        });
      }
    },

    uploadScript: async (data) => {
      const response = await augmentationApi.uploadScript(data);
      if (response.data.success) {
        set((state) => {
          state.customScripts.unshift(response.data.data);
        });
      } else {
        throw new Error(response.data.message);
      }
    },

    deleteScript: async (id) => {
      const response = await augmentationApi.deleteScript(id);
      if (response.data.success) {
        set((state) => {
          state.customScripts = state.customScripts.filter((s) => s.id !== id);
        });
      } else {
        throw new Error(response.data.message);
      }
    },
  }))
);

export default useAugmentationStore;
