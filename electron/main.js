const { app, BrowserWindow, ipcMain, dialog, clipboard } = require('electron');
const fs = require('fs');
const path = require('path');

const WIN_CONFIG = {
  width: 860,
  height: 700,
  minWidth: 600,
  minHeight: 500,
  title: 'MarkItDown 文档转换',
  autoHideMenuBar: true,
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    contextIsolation: true,
    nodeIntegration: false,
  },
};

let mainWindow = null;

function createWindow() {
  const iconExt = process.platform === 'win32' ? '.ico' : '.png';
  const platformIconPath = path.join(__dirname, `icon${iconExt}`);
  const fallbackIconPath = path.join(__dirname, 'icon.png');
  const resolvedIconPath = fs.existsSync(platformIconPath) ? platformIconPath
    : fs.existsSync(fallbackIconPath) ? fallbackIconPath
    : null;

  mainWindow = new BrowserWindow({
    ...WIN_CONFIG,
    ...(resolvedIconPath && { icon: resolvedIconPath }),
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerIPC() {
  ipcMain.handle('dialog:open-file', async () => {
    const { filePaths } = await dialog.showOpenDialog({
      filters: [
        {
          name: '支持的文件',
          extensions: ['pdf', 'docx', 'pptx', 'xlsx', 'jpg', 'jpeg', 'png', 'csv', 'txt', 'md'],
        },
      ],
      properties: ['openFile'],
    });
    return filePaths[0] || null;
  });

  // 只读文件字节，HTTP 上传由渲染进程的原生 fetch/FormData 完成
  ipcMain.handle('file:read', async (_, filePath) => {
    const resolvedPath = path.resolve(filePath);
    const buffer = fs.readFileSync(resolvedPath);
    // 返回 ArrayBuffer，IPC 会自动序列化
    return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  });

  ipcMain.handle('dialog:save-file', async (_, { defaultName, content }) => {
    const { filePath } = await dialog.showSaveDialog({
      defaultPath: defaultName.replace(/\.[^.]+$/, '.md'),
      filters: [{ name: 'Markdown', extensions: ['md'] }],
    });
    if (filePath) {
      fs.writeFileSync(filePath, content, 'utf-8');
      return filePath;
    }
    return null;
  });

  ipcMain.handle('clipboard:write', (_, text) => {
    clipboard.writeText(text);
  });
}

app.whenReady().then(() => {
  registerIPC();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
