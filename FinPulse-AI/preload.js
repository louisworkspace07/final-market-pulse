const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getCategories: () => ipcRenderer.invoke('get-categories'),
  fetchCategory: (id) => ipcRenderer.invoke('fetch-category', id),
  getConfig: () => ipcRenderer.invoke('get-config'),
  saveConfig: (cfg) => ipcRenderer.invoke('save-config', cfg),
  aiRun: (task, payload) => ipcRenderer.invoke('ai-run', { task, payload }),
  openDevTools: () => ipcRenderer.send('open-devtools'),
  aiwinShow: () => ipcRenderer.invoke('aiwin-show'),
  aiwinSend: (prompt) => ipcRenderer.invoke('aiwin-send', prompt),
  onAiwinStatus: (cb) => ipcRenderer.on('aiwin-status-update', (_e, s) => cb(s)),
  qtbridgeStart: () => ipcRenderer.invoke('qtbridge-start'),
  qtbridgeHealth: () => ipcRenderer.invoke('qtbridge-health'),
  qtbridgeAsk: (prompt) => ipcRenderer.invoke('qtbridge-ask', prompt)
});
