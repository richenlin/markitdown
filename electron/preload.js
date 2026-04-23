const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('markitdownAPI', {
  isElectron: true,
  defaultApiUrl: 'http://localhost:8778',

  openFile: () => ipcRenderer.invoke('dialog:open-file'),

  // 读取文件字节 → 返回 ArrayBuffer（渲染进程用原生 fetch 上传，无需 npm 包）
  readFileAsBuffer: (filePath) => ipcRenderer.invoke('file:read', filePath),

  saveFile: (defaultName, content) => ipcRenderer.invoke('dialog:save-file', { defaultName, content }),
  copyToClipboard: (text) => ipcRenderer.invoke('clipboard:write', text),
});
