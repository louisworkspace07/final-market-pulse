// Tiêm vào guest webview (qua will-attach-webview, contextIsolation=false).
// Mục tiêu: che dấu vết Electron để Google không chặn đăng nhập
// ("This browser or app may not be secure").
(function () {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  } catch (_) {}

  // navigator.userAgentData (Client Hints JS) — nguồn lộ "Electron" rõ nhất.
  try {
    const brands = [
      { brand: 'Chromium', version: '124' },
      { brand: 'Google Chrome', version: '124' },
      { brand: 'Not.A/Brand', version: '99' }
    ];
    const fakeUAData = {
      brands,
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: () => Promise.resolve({
        architecture: 'x86', bitness: '64', model: '',
        platform: 'Windows', platformVersion: '15.0.0',
        uaFullVersion: '124.0.6367.119', fullVersionList: brands
      }),
      toJSON: () => ({ brands, mobile: false, platform: 'Windows' })
    };
    Object.defineProperty(navigator, 'userAgentData', { get: () => fakeUAData });
  } catch (_) {}

  // Một vài site dò navigator.plugins rỗng -> giả vài plugin.
  try {
    if (!navigator.plugins || navigator.plugins.length === 0) {
      Object.defineProperty(navigator, 'plugins', {
        get: () => [{ name: 'Chrome PDF Plugin' }, { name: 'Chrome PDF Viewer' }, { name: 'Native Client' }]
      });
    }
  } catch (_) {}
})();
