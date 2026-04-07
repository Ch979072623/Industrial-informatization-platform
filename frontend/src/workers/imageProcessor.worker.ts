/**
 * 图片处理 Web Worker
 * 
 * 用于处理图片解码和预处理，避免阻塞主线程 UI
 */

// Worker 消息类型
interface WorkerMessage {
  id: string;
  type: 'decode' | 'compress' | 'extractMetadata';
  payload: unknown;
}

interface DecodePayload {
  arrayBuffer: ArrayBuffer;
  mimeType: string;
}

interface CompressPayload {
  imageData: ImageData;
  maxSize: number;
  quality: number;
}

// 解码图片
async function decodeImage(data: DecodePayload): Promise<{
  width: number;
  height: number;
  imageData: ImageData;
}> {
  try {
    // 创建 Blob
    const blob = new Blob([data.arrayBuffer], { type: data.mimeType });
    const bitmap = await createImageBitmap(blob);
    
    // 创建 OffscreenCanvas
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      throw new Error('Failed to get canvas context');
    }
    
    ctx.drawImage(bitmap, 0, 0);
    const imageData = ctx.getImageData(0, 0, bitmap.width, bitmap.height);
    
    // 清理资源
    bitmap.close();
    
    return {
      width: bitmap.width,
      height: bitmap.height,
      imageData,
    };
  } catch (error) {
    throw new Error(`Image decode failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// 压缩图片
async function compressImage(data: CompressPayload): Promise<{
  imageData: ImageData;
  scale: number;
}> {
  const { imageData, maxSize } = data;
  const { width, height } = imageData;
  
  // 计算缩放比例
  const maxDimension = Math.max(width, height);
  let scale = 1;
  
  if (maxDimension > maxSize) {
    scale = maxSize / maxDimension;
  }
  
  // 如果不需要压缩，直接返回
  if (scale >= 1) {
    return { imageData, scale: 1 };
  }
  
  const newWidth = Math.round(width * scale);
  const newHeight = Math.round(height * scale);
  
  // 创建压缩后的 canvas
  const canvas = new OffscreenCanvas(newWidth, newHeight);
  const ctx = canvas.getContext('2d');
  
  if (!ctx) {
    throw new Error('Failed to get canvas context');
  }
  
  // 创建临时 canvas 来存放原图
  const tempCanvas = new OffscreenCanvas(width, height);
  const tempCtx = tempCanvas.getContext('2d');
  
  if (!tempCtx) {
    throw new Error('Failed to get temp canvas context');
  }
  
  tempCtx.putImageData(imageData, 0, 0);
  
  // 使用高质量缩放
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(tempCanvas, 0, 0, newWidth, newHeight);
  
  const compressedImageData = ctx.getImageData(0, 0, newWidth, newHeight);
  
  return {
    imageData: compressedImageData,
    scale,
  };
}

// 提取元数据
function extractMetadata(arrayBuffer: ArrayBuffer): {
  width?: number;
  height?: number;
  format?: string;
} {
  const bytes = new Uint8Array(arrayBuffer);
  const result: { width?: number; height?: number; format?: string } = {};
  
  // 检查 JPEG
  if (bytes[0] === 0xFF && bytes[1] === 0xD8) {
    result.format = 'JPEG';
    // 解析 JPEG 尺寸（简化版）
    for (let i = 2; i < bytes.length - 9; i++) {
      if (bytes[i] === 0xFF && (bytes[i + 1] === 0xC0 || bytes[i + 1] === 0xC2)) {
        result.height = (bytes[i + 5] << 8) | bytes[i + 6];
        result.width = (bytes[i + 7] << 8) | bytes[i + 8];
        break;
      }
    }
  }
  // 检查 PNG
  else if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4E && bytes[3] === 0x47) {
    result.format = 'PNG';
    // PNG 尺寸在 IHDR chunk
    result.width = (bytes[16] << 24) | (bytes[17] << 16) | (bytes[18] << 8) | bytes[19];
    result.height = (bytes[20] << 24) | (bytes[21] << 16) | (bytes[22] << 8) | bytes[23];
  }
  
  return result;
}

// 消息处理器
self.onmessage = async (event: MessageEvent<WorkerMessage>) => {
  const { id, type, payload } = event.data;
  
  try {
    let result: unknown;
    
    switch (type) {
      case 'decode':
        result = await decodeImage(payload as DecodePayload);
        break;
        
      case 'compress':
        result = await compressImage(payload as CompressPayload);
        break;
        
      case 'extractMetadata':
        result = extractMetadata(payload as ArrayBuffer);
        break;
        
      default:
        throw new Error(`Unknown message type: ${type}`);
    }
    
    self.postMessage({ id, success: true, result });
  } catch (error) {
    self.postMessage({
      id,
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

export {};
