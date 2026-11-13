const TARGET = process.env.BACKEND_URL || 'https://oxide-judicial-visitors-mortality.trycloudflare.com';

module.exports = async (req, res) => {
  const url = `${TARGET}${req.url}`;
  
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    const lk = key.toLowerCase();
    if (lk !== 'host' && lk !== 'connection' && lk !== 'content-length') {
      headers[key] = value;
    }
  }
  headers['ngrok-skip-browser-warning'] = 'true';
  headers['User-Agent'] = 'Mozilla/5.0 MarketPulseVercelProxy';

  const options = {
    method: req.method,
    headers: headers,
    redirect: 'follow',
  };

  // Nếu có request body (POST, PUT, PATCH...)
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const buffers = [];
    for await (const chunk of req) {
      buffers.push(chunk);
    }
    options.body = Buffer.concat(buffers);
  }

  try {
    const upstreamRes = await fetch(url, options);

    res.statusCode = upstreamRes.status;
    for (const [key, value] of upstreamRes.headers.entries()) {
      if (key.toLowerCase() !== 'content-encoding') {
        res.setHeader(key, value);
      }
    }

    if (upstreamRes.body) {
      const { Readable } = require('stream');
      Readable.fromWeb(upstreamRes.body).pipe(res);
    } else {
      res.end();
    }
  } catch (err) {
    console.error('[Proxy Fetch Error]', err);
    if (!res.headersSent) {
      res.statusCode = 502;
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 80vh; text-align: center; padding: 20px;">
          <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 32px; max-width: 480px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <div style="font-size: 40px; margin-bottom: 16px;">🔄</div>
            <h2 style="margin: 0 0 12px; color: #111827; font-size: 20px;">Hệ thống đang kết nối lại</h2>
            <p style="margin: 0 0 24px; color: #6b7280; font-size: 14px; line-height: 1.5;">Đang đồng bộ dữ liệu thị trường và mô hình tính toán từ máy chủ. Vui lòng bấm thử lại.</p>
            <button onclick="window.location.reload()" style="background: #2563eb; color: #ffffff; border: none; padding: 10px 24px; border-radius: 8px; font-weight: 500; cursor: pointer; font-size: 14px;">Tải lại trang</button>
          </div>
        </div>
      `);
    }
  }
};
