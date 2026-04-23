const { app, BrowserWindow, ipcMain, dialog, clipboard } = require('electron');
const fs = require('fs');
const path = require('path');
const FormData = require('form-data');
const fetch = require('node-fetch');

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

  ipcMain.handle('convert:file', async (_, { filePath, apiUrl }) => {
    const resolvedPath = path.resolve(filePath);
    const form = new FormData();
    form.append('file', fs.createReadStream(resolvedPath));
    const res = await fetch(`${apiUrl}/convert`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API Error ${res.status}: ${text}`);
    }
    return await res.json();
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
