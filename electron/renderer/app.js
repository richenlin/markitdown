const STORAGE_KEY = 'markitdown_api_url';

const $ = (id) => document.getElementById(id);

const dropZone = $('dropZone');
const fileInput = $('fileInput');
const resultDivider = $('resultDivider');
const resultSection = $('resultSection');
const resultFilename = $('resultFilename');
const resultElapsed = $('resultElapsed');
const resultContent = $('resultContent');
const loadingBar = $('loadingBar');
const errorMessage = $('errorMessage');
const errorText = $('errorText');
const actionBar = $('actionBar');
const actionInfo = $('actionInfo');
const copyBtn = $('copyBtn');
const saveBtn = $('saveBtn');
const settingsBtn = $('settingsBtn');
const settingsModal = $('settingsModal');
const settingsClose = $('settingsClose');
const settingsSave = $('settingsSave');
const apiUrlInput = $('apiUrlInput');

let currentMarkdown = '';
let currentFilename = '';

function getSavedApiUrl() {
  return localStorage.getItem(STORAGE_KEY)
    || (window.markitdownAPI ? window.markitdownAPI.defaultApiUrl : 'http://localhost:8778');
}

function isElectron() {
  return window.markitdownAPI && window.markitdownAPI.isElectron;
}

function hideAll() {
  resultDivider.style.display = 'none';
  resultSection.style.display = 'none';
  loadingBar.style.display = 'none';
  errorMessage.style.display = 'none';
  actionBar.style.display = 'none';
}

function setStatus(status, detail) {
  switch (status) {
    case 'uploading':
      hideAll();
      loadingBar.style.display = '';
      dropZone.style.pointerEvents = 'none';
      dropZone.style.opacity = '0.6';
      break;

    case 'done':
      hideAll();
      resultDivider.style.display = '';
      resultSection.style.display = '';
      actionBar.style.display = '';
      loadingBar.style.display = 'none';
      dropZone.style.pointerEvents = '';
      dropZone.style.opacity = '';
      copyBtn.disabled = false;
      saveBtn.disabled = false;
      break;

    case 'error':
      hideAll();
      errorMessage.style.display = '';
      errorText.textContent = detail || '未知错误';
      dropZone.style.pointerEvents = '';
      dropZone.style.opacity = '';
      break;

    default:
      hideAll();
      dropZone.style.pointerEvents = '';
      dropZone.style.opacity = '';
  }
}

function showResult(markdown, filename, elapsed) {
  currentMarkdown = markdown;
  currentFilename = filename;
  resultFilename.textContent = filename;
  resultElapsed.textContent = `${elapsed}s`;
  resultContent.textContent = markdown;
  actionInfo.textContent = `转换耗时: ${elapsed}s`;
}

function showToast(message, type) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 2000);
}

async function convertFile(filePath) {
  const apiUrl = getSavedApiUrl();

  setStatus('uploading');
  const startTime = Date.now();

  try {
    if (isElectron()) {
      const result = await window.markitdownAPI.convertFile(filePath, apiUrl);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      showResult(result.markdown, result.filename, elapsed);
      setStatus('done');
    } else {
      const resp = await fetch(`${apiUrl}/convert`, {
        method: 'POST',
        body: createBrowserFormData(filePath),
      });
      if (!resp.ok) throw new Error(`API Error ${resp.status}`);
      const result = await resp.json();
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      showResult(result.markdown, result.filename, elapsed);
      setStatus('done');
    }
  } catch (err) {
    setStatus('error', err.message);
  }
}

function createBrowserFormData(file) {
  const form = new FormData();
  form.append('file', file);
  return form;
}

async function handleFile(fileOrPath) {
  if (typeof fileOrPath === 'string') {
    await convertFile(fileOrPath);
  } else if (fileOrPath instanceof File) {
    if (isElectron()) {
      await convertFile(fileOrPath.path);
    } else {
      await convertFileBrowser(fileOrPath);
    }
  }
}

async function convertFileBrowser(file) {
  const apiUrl = getSavedApiUrl();
  setStatus('uploading');
  const startTime = Date.now();

  try {
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`${apiUrl}/convert`, { method: 'POST', body: form });
    if (!resp.ok) throw new Error(`API Error ${resp.status}`);
    const result = await resp.json();
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    showResult(result.markdown, result.filename, elapsed);
    setStatus('done');
  } catch (err) {
    setStatus('error', err.message);
  }
}

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

dropZone.addEventListener('click', async () => {
  if (isElectron()) {
    const filePath = await window.markitdownAPI.openFile();
    if (filePath) await convertFile(filePath);
  } else {
    fileInput.click();
  }
});

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) handleFile(file);
  fileInput.value = '';
});

copyBtn.addEventListener('click', async () => {
  if (!currentMarkdown) return;
  try {
    if (isElectron()) {
      await window.markitdownAPI.copyToClipboard(currentMarkdown);
    } else {
      await navigator.clipboard.writeText(currentMarkdown);
    }
    showToast('已复制到剪贴板', 'success');
  } catch {
    showToast('复制失败', 'error');
  }
});

saveBtn.addEventListener('click', async () => {
  if (!currentMarkdown) return;
  try {
    if (isElectron()) {
      const savedPath = await window.markitdownAPI.saveFile(currentFilename, currentMarkdown);
      if (savedPath) {
        showToast(`已保存: ${savedPath}`, 'success');
      }
    } else {
      const blob = new Blob([currentMarkdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = (currentFilename || 'output').replace(/\.[^.]+$/, '.md');
      a.click();
      URL.revokeObjectURL(url);
      showToast('文件已下载', 'success');
    }
  } catch {
    showToast('保存失败', 'error');
  }
});

settingsBtn.addEventListener('click', () => {
  apiUrlInput.value = getSavedApiUrl();
  settingsModal.style.display = '';
});

settingsClose.addEventListener('click', () => {
  settingsModal.style.display = 'none';
});

settingsModal.addEventListener('click', (e) => {
  if (e.target === settingsModal) {
    settingsModal.style.display = 'none';
  }
});

settingsSave.addEventListener('click', () => {
  const url = apiUrlInput.value.trim();
  if (url) {
    localStorage.setItem(STORAGE_KEY, url);
    settingsModal.style.display = 'none';
    showToast('设置已保存', 'success');
  }
});
