const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('markitdownAPI', {
  isElectron: true,
  defaultApiUrl: 'http://localhost:8778',

  openFile: () => ipcRenderer.invoke('dialog:open-file'),
  convertFile: (filePath, apiUrl) => ipcRenderer.invoke('convert:file', { filePath, apiUrl }),
  saveFile: (defaultName, content) => ipcRenderer.invoke('dialog:save-file', { defaultName, content }),
  copyToClipboard: (text) => ipcRenderer.invoke('clipboard:write', text),
});
