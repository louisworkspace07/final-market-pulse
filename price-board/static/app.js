// Base path detection: when embedded inside Gateway or Vercel under /embed_banggia/,
// prefix requests with /embed_banggia; otherwise use relative root for standalone.
const BASE_PATH = window.location.pathname.includes('/embed_banggia') ? '/embed_banggia' : '';
const API_URL = `${BASE_PATH}/api/stocks`;

// Lưu trữ dữ liệu của lần fetch trước để so sánh (tạo animation)
let previousData = {};
let currentSymbolsList = [];

// LỖI ĐÃ SỬA: nhãn "Cập nhật lúc: <giờ>" in thẳng timestamp cache mà không
// cảnh báo độ cũ — đo thật cache AI S/R chỉ phủ vài mã, có bản ghi cũ tới gần
// 1 tháng, người xem không biết đang nhìn phân tích cũ vì nhãn không nói gì
// khác "Cập nhật lúc" bất kể mới hay cũ. `timestamp` server trả dạng
// "DD/MM/YYYY HH:MM:SS" (xem gemini_worker.py).
function aiAgeLabel(timestamp) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})$/.exec(timestamp || "");
    if (!m) return { text: `Cập nhật lúc: ${timestamp || "?"}`, bg: "#333", color: "#aaa" };
    const [, d, mo, y, h, mi, s] = m;
    const then = new Date(+y, +mo - 1, +d, +h, +mi, +s);
    const days = Math.floor((Date.now() - then.getTime()) / 86400000);
    if (days >= 1) {
        return {
            text: `⚠ Phân tích cũ ${days} ngày (lúc ${timestamp}) — giá đã đổi, kháng cự/hỗ trợ có thể không còn đúng`,
            bg: "#4a2a12", color: "#ffb15c",
        };
    }
    return { text: `Cập nhật lúc: ${timestamp}`, bg: "#333", color: "#aaa" };
}

function applyAiTimestamp(el, timestamp) {
    const { text, bg, color } = aiAgeLabel(timestamp);
    el.innerText = text;
    el.style.background = bg;
    el.style.color = color;
    el.style.display = "inline-block";
}

function formatNumber(num) {
    if (num === 0 || num === "0.00" || !num) return "";
    return Number(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatVol(num) {
    if (num === 0 || !num) return "";
    return Number(num).toLocaleString('en-US');
}

function getColorClass(price, ref, ceil, floor) {
    if (!price || price === 0) return '';
    if (price >= ceil) return 'text-ceil';
    if (price <= floor) return 'text-floor';
    if (price > ref) return 'text-up';
    if (price < ref) return 'text-down';
    return 'text-ref';
}

function parseAIResponse(dataStr) {
    let aiData = {};
    let parsedSuccessfully = false;
    if (!dataStr) return { success: false, data: {} };
    
    let cleanText = dataStr.trim();
    cleanText = cleanText.replace(/^```(?:json)?/i, '').replace(/```$/g, '').trim();
    
    try {
        aiData = JSON.parse(cleanText);
        parsedSuccessfully = true;
    } catch(e) {
        // Fallback cho JSON bị cắt cụt/lỗi
        const extractField = (field) => {
            const regex = new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)`);
            const match = dataStr.match(regex);
            let val = match ? match[1] : '';
            return val.replace(/\\"/g, '"').replace(/\\\\/g, '\\').trim();
        };
        aiData.trend = extractField('trend');
        aiData.support_resistance = extractField('support_resistance');
        aiData.supply_demand = extractField('supply_demand');
        aiData.conclusion = extractField('conclusion');
        aiData.strategy = extractField('strategy');
        
        // Nếu lấy được dữ liệu bằng regex thì coi như parse thành công
        if (aiData.trend || aiData.strategy || aiData.support_resistance) {
            parsedSuccessfully = true;
        }
    }
    return { success: parsedSuccessfully, data: aiData };
}

let selectedStocks = new Set(); // Default empty

let currentCategory = 'none'; // 'none' = CHUA chon nhom -> khong render gi (cho nguoi dung chon). Sau: all/vn30/hose/hnx/upcom
let currentIndustry = 'all'; // all, 'Ngân hàng', ...
let industriesMap = {};

const VN30_SYMBOLS = ['ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG','MBB','MSN','MWG','PLX','POW','SAB','SHB','SSB','SSI','STB','TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE'];

let indexCategories = {};

// Load danh sách chứng khoán theo chỉ số (chống cache để luôn cập nhật mới nhất)
fetch('/static/categories.json?v=' + new Date().getTime())
    .then(r => r.json())
    .then(data => {
        indexCategories = data;
    })
    .catch(e => console.log('No index categories loaded'));

// Load CP ngành vào dropdown menu
fetch('/static/industries.json')
    .then(r => r.json())
    .then(data => {
        industriesMap = data;
        let dropdown = document.getElementById('industry-dropdown');
        if (dropdown) {
            dropdown.innerHTML = '';
            Object.keys(data).forEach(ind => {
                let a = document.createElement('a');
                a.href = "javascript:void(0)";
                a.innerText = ind;
                a.onclick = function() { changeIndustry(ind, this.closest('.tab-item')); };
                dropdown.appendChild(a);
            });
        }
    })
    .catch(e => console.error("Could not load industries", e));
function updateSelectedCountDisplay() {
    let countEl = document.getElementById('selected-count-display');
    if (countEl) {
        countEl.innerText = `Đang chọn: ${selectedStocks.size} mã`;
    }
}

function toggleSelectAll(checkbox) {
    let checkboxes = document.querySelectorAll('.stock-checkbox');
    if (checkbox.checked) {
        checkboxes.forEach(cb => {
            let tr = cb.closest('tr');
            if (tr && tr.style.display !== 'none') {
                cb.checked = true;
                selectedStocks.add(cb.value);
            }
        });
    } else {
        checkboxes.forEach(cb => {
            let tr = cb.closest('tr');
            if (tr && tr.style.display !== 'none') {
                cb.checked = false;
                selectedStocks.delete(cb.value);
            }
        });
    }
    syncTargetsToServer();
    updateSelectedCountDisplay();
}

function updateSelectedStocks(checkbox) {
    if (checkbox.checked) {
        selectedStocks.add(checkbox.value);
    } else {
        selectedStocks.delete(checkbox.value);
        document.getElementById('selectAllCheckbox').checked = false;
    }
    syncTargetsToServer();
    updateSelectedCountDisplay();
}

async function syncTargetsToServer() {
    let targets = Array.from(selectedStocks);
    try {
        await fetch(`${BASE_PATH}/api/gemini/set_targets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ targets: targets })
        });
    } catch(e) { console.error("Lỗi khi sync targets", e); }
}

async function toggleAutoScan() {
    try {
        const btnToggleAuto = document.getElementById('btn-toggle-auto');
        if (btnToggleAuto.innerText.includes("Tắt")) {
            btnToggleAuto.innerText = "Đang chờ tắt...";
            btnToggleAuto.style.background = "#f39c12"; // Cam
            btnToggleAuto.disabled = true;
        } else {
            btnToggleAuto.innerText = "Đang chờ bật...";
            btnToggleAuto.style.background = "#f39c12"; // Cam
            btnToggleAuto.disabled = true;
        }

        await syncTargetsToServer(); // Dong bo danh sach truoc khi bat auto
        const res = await fetch(`${BASE_PATH}/api/gemini/toggle_auto_scan`, { method: 'POST' });
        const data = await res.json();
        
        btnToggleAuto.disabled = false;
        if (data.status === 'success') {
            if (data.paused) {
                btnToggleAuto.innerText = "Bật Auto";
                btnToggleAuto.style.background = "#2ecc71"; // Xanh
            } else {
                btnToggleAuto.innerText = "Tắt Auto";
                btnToggleAuto.style.background = "#e74c3c"; // Đỏ
            }
        }
    } catch(e) { 
        console.error(e); 
        const btnToggleAuto = document.getElementById('btn-toggle-auto');
        if(btnToggleAuto) btnToggleAuto.disabled = false;
    }
}

function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('vi-VN') + ' | ' + now.toLocaleDateString('vi-VN');
}
setInterval(updateClock, 1000);
updateClock();

function createRow(stock) {
    const tr = document.createElement('tr');
    tr.id = `stock-${stock.symbol}`;
    tr.className = 'stock-row';
    
    // Determine main color class
    const mainColor = getColorClass(stock.matchPrice, stock.ref, stock.ceil, stock.floor);
    const r = stock.raw || [];
    
    const safeRaw = (idx) => r[idx] || '';

    const isChecked = selectedStocks.has(stock.symbol) ? 'checked' : '';

    tr.innerHTML = `
        <td class="col-checkbox"><input type="checkbox" class="stock-checkbox" value="${stock.symbol}" onchange="updateSelectedStocks(this)" ${isChecked}></td>
        <td id="tk-${stock.symbol}" class="col-ticker ${mainColor}" onclick="openModal('${stock.symbol}')" style="cursor: pointer;">${safeRaw(0)}</td>
        <td class="col-base text-ref">${safeRaw(1)}</td>
        <td class="col-base text-ceil">${safeRaw(2)}</td>
        <td class="col-base text-floor">${safeRaw(3)}</td>
        <td class="col-vol" id="vol-${stock.symbol}">${safeRaw(4)}</td>
        
        <!-- Bên Mua -->
        <td id="bp3-${stock.symbol}" class="${getColorClass(stock.buyP3, stock.ref, stock.ceil, stock.floor)}">${safeRaw(5)}</td>
        <td id="bv3-${stock.symbol}" class="col-vol">${safeRaw(6)}</td>
        <td id="bp2-${stock.symbol}" class="${getColorClass(stock.buyP2, stock.ref, stock.ceil, stock.floor)}">${safeRaw(7)}</td>
        <td id="bv2-${stock.symbol}" class="col-vol">${safeRaw(8)}</td>
        <td id="bp1-${stock.symbol}" class="${getColorClass(stock.buyP1, stock.ref, stock.ceil, stock.floor)}">${safeRaw(9)}</td>
        <td id="bv1-${stock.symbol}" class="col-vol">${safeRaw(10)}</td>
        
        <!-- Khớp Lệnh -->
        <td id="mp-${stock.symbol}" class="${mainColor} font-bold">${safeRaw(11)}</td>
        <td id="mv-${stock.symbol}" class="col-vol">${safeRaw(12)}</td>
        <td id="mc-${stock.symbol}" class="${mainColor}">${safeRaw(13)}</td>
        
        <!-- Bên Bán -->
        <td id="sp1-${stock.symbol}" class="${getColorClass(stock.sellP1, stock.ref, stock.ceil, stock.floor)}">${safeRaw(14)}</td>
        <td id="sv1-${stock.symbol}" class="col-vol">${safeRaw(15)}</td>
        <td id="sp2-${stock.symbol}" class="${getColorClass(stock.sellP2, stock.ref, stock.ceil, stock.floor)}">${safeRaw(16)}</td>
        <td id="sv2-${stock.symbol}" class="col-vol">${safeRaw(17)}</td>
        <td id="sp3-${stock.symbol}" class="${getColorClass(stock.sellP3, stock.ref, stock.ceil, stock.floor)}">${safeRaw(18)}</td>
        <td id="sv3-${stock.symbol}" class="col-vol">${safeRaw(19)}</td>
        
        <!-- Giá: Cao, TB, Thấp -->
        <td id="h-${stock.symbol}" class="${getColorClass(stock.high, stock.ref, stock.ceil, stock.floor)}">${safeRaw(20)}</td>
        <td id="avg-${stock.symbol}" class="${getColorClass(stock.avg, stock.ref, stock.ceil, stock.floor)}">${safeRaw(21)}</td>
        <td id="l-${stock.symbol}" class="${getColorClass(stock.low, stock.ref, stock.ceil, stock.floor)}">${safeRaw(22)}</td>
        
        <!-- Dư: Mua, Bán -->
        <td id="db-${stock.symbol}" class="col-vol">${safeRaw(23)}</td>
        <td id="ds-${stock.symbol}" class="col-vol">${safeRaw(24)}</td>
        
        <!-- ĐTNN: Mua, Bán -->
        <td id="fb-${stock.symbol}" class="col-vol">${safeRaw(25)}</td>
        <td id="fs-${stock.symbol}" class="col-vol">${safeRaw(26)}</td>
    `;
    // Áp dụng bộ lọc
    tr.style.display = isVisible(stock) ? '' : 'none';
    return tr;
}

let boardSearch = "";   // P5: lọc nhanh theo mã (rỗng = không lọc)
function isVisible(stock) {
    // CHUA chon nhom -> khong hien gi (man hinh chon nhom se hien thay the).
    if (currentCategory === 'none' && currentIndustry === 'all') return false;
    if (boardSearch && !String(stock.symbol).toUpperCase().includes(boardSearch)) return false;
    if (currentCategory === 'all' && currentIndustry === 'all') {
        // Nếu không có bộ lọc ngành hay sàn nào được bật (tất cả)
        // và nếu đang bật auto-filter thì chỉ lọc theo auto-filter
        // else return true
    } else if (currentCategory in indexCategories) {
        // Nếu chọn một chỉ số phụ đã được cào dữ liệu (kể cả rỗng)
        if (!indexCategories[currentCategory].includes(stock.symbol)) return false;
    } else {
        // Fallback logic
        if (currentCategory === 'vn30' && !VN30_SYMBOLS.includes(stock.symbol)) return false;
        
        if (currentCategory === 'hose' && stock.exchange !== 'hose') return false;
        if (currentCategory === 'hnx' && stock.exchange !== 'hnx') return false;
        if (currentCategory === 'upcom' && stock.exchange !== 'upcom') return false;
        
        // Nếu chọn mục chưa có data (tạm map về sàn tương ứng)
        const hoseCategories = ['vn100', 'vnallshare', 'vnsmallcap', 'vnxallshare', 'etf', 'hose_lo_le', 'hose_thoa_thuan'];
        const hnxCategories = ['hnx30', 'bond', 'hnx_thoa_thuan'];
        const upcomCategories = ['upcom_thoa_thuan'];
        
        if (hoseCategories.includes(currentCategory) && stock.exchange !== 'hose') return false;
        if (hnxCategories.includes(currentCategory) && stock.exchange !== 'hnx') return false;
        if (upcomCategories.includes(currentCategory) && stock.exchange !== 'upcom') return false;
    }

    if (currentIndustry !== 'all') {
        const indSymbols = industriesMap[currentIndustry] || [];
        if (!indSymbols.includes(stock.symbol)) return false;
    }
    return true;
}

/* P5: ô tìm mã — lọc bảng tức thời, tôn trọng cả bộ lọc ngành/sàn (isVisible). */
function applyBoardSearch(q) {
    boardSearch = String(q || "").trim().toUpperCase();
    document.querySelectorAll('#board-body tr[id^="stock-"]').forEach(tr => {
        const sym = tr.id.replace("stock-", "");
        const stock = previousData[sym] || { symbol: sym };
        tr.style.display = isVisible(stock) ? "" : "none";
    });
}

/* HIỆU NĂNG: cache DOM ref theo id. Giờ giao dịch có tới ~42.000 lượt
   getElementById/giây (27 ô × 1.549 mã) chạy đồng bộ trong callback fetch →
   nghẽn main thread → treo. Các dòng KHÔNG bị xoá/tạo lại nên ref bền vĩnh viễn;
   chỉ tra getElementById 1 lần/id rồi dùng lại. */
const elCache = new Map();
function getEl(id) {
    let e = elCache.get(id);
    if (e && e.isConnected) return e;
    e = document.getElementById(id);
    if (e) elCache.set(id, e);
    return e;
}

function triggerFlash(elementId, type) {
    const el = getEl(elementId);
    if (!el) return;
    
    // Reset animation
    el.classList.remove('flash-up', 'flash-down');
    void el.offsetWidth; // trigger reflow
    
    if (type === 'up') {
        el.classList.add('flash-up');
    } else if (type === 'down') {
        el.classList.add('flash-down');
    }
}

function updateCell(id, newStr, oldStr, newVal, oldVal) {
    if (newStr !== oldStr) {
        const el = getEl(id);
        if (el) {
            el.innerText = newStr || '';
            if (newVal > oldVal) {
                triggerFlash(id, 'up');
            } else if (newVal < oldVal) {
                triggerFlash(id, 'down');
            }
        }
    }
}

async function fetchMarketData() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json();
        
        const tbody = document.getElementById('board-body');

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="27" style="text-align:center; padding: 20px; color:#aaa;">Đang kết nối nguồn giá vnstock... (~10-15s lần đầu)</td></tr>';
            return;
        }

        updateBreadth(data);   // độ rộng thị trường (header) — mỗi tick

        // CHUA chon nhom -> luu du lieu (de chon xong render ngay + tim ma) roi
        // hien MAN HINH CHON NHOM thay vi do 1428 dong.
        if (currentCategory === 'none' && currentIndustry === 'all') {
            data.forEach(s => { previousData[s.symbol] = s; });
            if (!document.getElementById('choose-prompt')) renderChoosePrompt(tbody);
            return;
        }
        // Da chon nhom -> xoa man hinh chon / dong loading neu con.
        if (document.getElementById('choose-prompt') || tbody.innerHTML.includes("Đang kết nối")) {
            tbody.innerHTML = "";
        }
        
        if (data.length > 0) {
            currentSymbolsList = data.map(stock => stock.symbol);
        }
        
        data.forEach(stock => {
            const sym = stock.symbol;
            
            // Nếu chưa có row, tạo mới — NHƯNG chỉ tạo cho mã ĐANG HIỆN (thuộc
            // nhóm đã chọn). Tránh dựng 1428 DOM row khi chưa chọn / khi lọc nhóm.
            let tr = document.getElementById(`stock-${sym}`);
            if (!tr) {
                if (!isVisible(stock)) { previousData[sym] = stock; return; }
                tbody.appendChild(createRow(stock));
            } else {
                // HIỆU NĂNG: dòng ĐANG ẨN (bị lọc ngành/sàn/tìm mã) thì KHÔNG diff
                // 27 ô — bỏ qua luôn. KHÔNG cập nhật previousData để khi hiện lại,
                // diff phát hiện thay đổi và refresh đầy đủ.
                if (!isVisible(stock)) {
                    if (tr.style.display !== 'none') tr.style.display = 'none';
                    return;
                }
                if (tr.style.display === 'none') tr.style.display = '';
                // Update các ô thay đổi và tạo hiệu ứng nhấp nháy
                const prev = previousData[sym] || {};
                const r = stock.raw || [];
                const pr = prev.raw || [];
                const safeRaw = (idx) => r[idx] || '';
                const safePrevRaw = (idx) => pr[idx] || '';
                
                // Khớp lệnh
                if (stock.matchPrice !== prev.matchPrice || safeRaw(11) !== safePrevRaw(11)) {
                    const mpEl = getEl(`mp-${sym}`);
                    const mcEl = getEl(`mc-${sym}`);
                    const tickerEl = getEl(`tk-${sym}`);
                    
                    const newColor = getColorClass(stock.matchPrice, stock.ref, stock.ceil, stock.floor);
                    
                    mpEl.innerText = safeRaw(11);
                    mpEl.className = `${newColor} font-bold`;
                    
                    mcEl.innerText = safeRaw(13);
                    mcEl.className = newColor;
                    
                    tickerEl.className = `sticky-col col-ticker ${newColor}`;
                    
                    const flashType = stock.matchPrice > prev.matchPrice ? 'up' : (stock.matchPrice < prev.matchPrice ? 'down' : '');
                    if (flashType) {
                        triggerFlash(`mp-${sym}`, flashType);
                        triggerFlash(`mc-${sym}`, flashType);
                    }
                }
                
                updateCell(`mv-${sym}`, safeRaw(12), safePrevRaw(12), stock.matchVol, prev.matchVol);
                updateCell(`vol-${sym}`, safeRaw(4), safePrevRaw(4), stock.totalVol, prev.totalVol);
                
                // Bên Mua
                updateCell(`bp1-${sym}`, safeRaw(9), safePrevRaw(9), stock.buyP1, prev.buyP1);
                updateCell(`bv1-${sym}`, safeRaw(10), safePrevRaw(10), stock.buyV1, prev.buyV1);
                updateCell(`bp2-${sym}`, safeRaw(7), safePrevRaw(7), stock.buyP2, prev.buyP2);
                updateCell(`bv2-${sym}`, safeRaw(8), safePrevRaw(8), stock.buyV2, prev.buyV2);
                updateCell(`bp3-${sym}`, safeRaw(5), safePrevRaw(5), stock.buyP3, prev.buyP3);
                updateCell(`bv3-${sym}`, safeRaw(6), safePrevRaw(6), stock.buyV3, prev.buyV3);
                
                // Bên Bán
                updateCell(`sp1-${sym}`, safeRaw(14), safePrevRaw(14), stock.sellP1, prev.sellP1);
                updateCell(`sv1-${sym}`, safeRaw(15), safePrevRaw(15), stock.sellV1, prev.sellV1);
                updateCell(`sp2-${sym}`, safeRaw(16), safePrevRaw(16), stock.sellP2, prev.sellP2);
                updateCell(`sv2-${sym}`, safeRaw(17), safePrevRaw(17), stock.sellV2, prev.sellV2);
                updateCell(`sp3-${sym}`, safeRaw(18), safePrevRaw(18), stock.sellP3, prev.sellP3);
                updateCell(`sv3-${sym}`, safeRaw(19), safePrevRaw(19), stock.sellV3, prev.sellV3);
                
                // Giá
                updateCell(`h-${sym}`, safeRaw(20), safePrevRaw(20), stock.high, prev.high);
                updateCell(`avg-${sym}`, safeRaw(21), safePrevRaw(21), stock.avg, prev.avg);
                updateCell(`l-${sym}`, safeRaw(22), safePrevRaw(22), stock.low, prev.low);
                
                // Dư
                updateCell(`db-${sym}`, safeRaw(23), safePrevRaw(23), stock.remainBuy, prev.remainBuy);
                updateCell(`ds-${sym}`, safeRaw(24), safePrevRaw(24), stock.remainSell, prev.remainSell);
                
                // ĐTNN
                updateCell(`fb-${sym}`, safeRaw(25), safePrevRaw(25), stock.foreignBuy, prev.foreignBuy);
                updateCell(`fs-${sym}`, safeRaw(26), safePrevRaw(26), stock.foreignSell, prev.foreignSell);
            }
            
            // Lưu lại state
            previousData[sym] = stock;
        });
        
    } catch (error) {
        console.error("Lỗi khi gọi API:", error);
    }
}

/* Độ RỘNG thị trường: tăng/giảm/đứng/trần/sàn — tính từ toàn bộ dữ liệu bảng.
   Rẻ (1 vòng so sánh), cho biết "sức khỏe" phiên bằng 1 liếc mắt. */
let _lastBreadth = "";
function updateBreadth(data) {
    let up = 0, down = 0, flat = 0, ceil = 0, floor = 0;
    for (const s of data) {
        const mp = s.matchPrice, ref = s.ref;
        if (!mp || !ref) { continue; }
        if (s.ceil && mp >= s.ceil) ceil++;
        else if (s.floor && mp <= s.floor) floor++;
        if (mp > ref) up++; else if (mp < ref) down++; else flat++;
    }
    const key = `${up}-${down}-${flat}-${ceil}-${floor}`;
    if (key === _lastBreadth) return;      // không đổi -> không đụng DOM
    _lastBreadth = key;
    const el = document.getElementById('market-breadth');
    if (!el) return;
    const tot = up + down + flat || 1;
    el.innerHTML =
        `<span class="bd up">▲ ${up.toLocaleString('vi-VN')}</span>` +
        `<span class="bd flat">＝ ${flat.toLocaleString('vi-VN')}</span>` +
        `<span class="bd down">▼ ${down.toLocaleString('vi-VN')}</span>` +
        (ceil ? `<span class="bd ceil" title="kịch trần">⇧ ${ceil}</span>` : "") +
        (floor ? `<span class="bd floor" title="kịch sàn">⇩ ${floor}</span>` : "") +
        `<span class="bd-bar"><i class="up" style="width:${up/tot*100}%"></i>` +
        `<i class="flat" style="width:${flat/tot*100}%"></i>` +
        `<i class="down" style="width:${down/tot*100}%"></i></span>`;
}

/* Màn hình CHỌN NHÓM — hiện khi chưa chọn, để KHÔNG dựng 1428 dòng lúc vào app. */
function renderChoosePrompt(tbody) {
    const all = Object.values(previousData);
    const total = all.length;
    // tóm tắt thị trường ngay trên màn chờ — biến màn chọn thành màn có giá trị
    let up = 0, down = 0;
    for (const s of all) {
        if (!s.matchPrice || !s.ref) continue;   // bỏ mã chưa khớp (giá 0, ngoài giờ)
        if (s.matchPrice > s.ref) up++; else if (s.matchPrice < s.ref) down++;
    }
    // đếm mã theo sàn (hiện lên nút cho "chỉnh chu")
    let nHose = 0, nHnx = 0, nUp = 0;
    for (const s of all) {
        if (s.exchange === 'hose') nHose++;
        else if (s.exchange === 'hnx') nHnx++;
        else if (s.exchange === 'upcom') nUp++;
    }
    const tradeTot = up + down || 1;
    const summary = total
        ? `<span class="cs-up">▲ ${up.toLocaleString('vi-VN')} tăng</span>
           <span class="cs-dot">·</span>
           <span class="cs-down">▼ ${down.toLocaleString('vi-VN')} giảm</span>
           <span class="cs-mini"><i style="width:${up/tradeTot*100}%"></i><b style="width:${down/tradeTot*100}%"></b></span>`
        : "";
    const btn = (cat, name, sub, cls) =>
        `<button class="cp-btn ${cls||''}" onclick="pickGroup('${cat}')">
           <span class="cp-b-name">${name}</span><span class="cp-b-sub">${sub}</span></button>`;
    tbody.innerHTML = `<tr><td colspan="28" style="padding:0">
      <div id="choose-prompt" class="choose-prompt">
        <div class="cp-aurora"></div>
        <div class="cp-glow"></div>
        <svg class="cp-mark" width="72" height="72" viewBox="0 0 24 24" fill="none">
          <rect x="2"  y="13" width="4" height="8"  rx="1.2" fill="#0ecb81"/>
          <rect x="8"  y="7"  width="4" height="14" rx="1.2" fill="#2196f3"/>
          <rect x="14" y="3"  width="4" height="18" rx="1.2" fill="#9b7bff"/>
          <rect x="20" y="10" width="2.5" height="11" rx="1.2" fill="#f0b90b"/>
          <path d="M2 12 L10 8 L15 11 L22 4" stroke="#eef3fa" stroke-width="1" opacity=".5" fill="none"/>
        </svg>
        <div class="cp-title">Bảng giá chứng khoán realtime</div>
        <div class="cp-summary">${summary}</div>
        <div class="cp-sub">Chọn một nhóm để bắt đầu — bảng nhảy <b>1 giây/lần</b>, mượt và nhẹ. Hoặc gõ mã ở ô tìm phía trên.</div>
        <div class="cp-btns">
          ${btn('vn30','VN30','30 mã lớn nhất','primary')}
          ${btn('hose','HOSE', nHose ? nHose.toLocaleString('vi-VN')+' mã' : 'Sàn TP.HCM')}
          ${btn('hnx','HNX', nHnx ? nHnx.toLocaleString('vi-VN')+' mã' : 'Sàn Hà Nội')}
          ${btn('upcom','UPCOM', nUp ? nUp.toLocaleString('vi-VN')+' mã' : 'Sàn UPCOM')}
          ${btn('all','Tất cả', '~'+total.toLocaleString('vi-VN')+' mã · nặng','ghost')}
        </div>
      </div></td></tr>`;
}
/* Chọn nhóm từ màn hình chọn: đặt category + xóa prompt, tick sau tự render. */
function pickGroup(cat) {
    document.getElementById('board-body').innerHTML = "";
    // Highlight tab tuong ung neu la tab cap 1 (all/hose/hnx/upcom).
    const tab = [...document.querySelectorAll('.tabs-menu .tab-item')].find(t =>
        (t.textContent || '').trim().toUpperCase().startsWith(cat.toUpperCase()));
    changeCategory(cat, tab || null);
    fetchMarketData();   // render ngay, khong cho tick sau
}

// Gọi API mỗi 1 giây để lấy realtime data
setInterval(fetchMarketData, 1000);
fetchMarketData(); // Gọi lần đầu ngay lập tức

// --- Modal Logic ---
const modal = document.getElementById('stockModal');
const closeModalBtn = document.getElementById('closeModal');

closeModalBtn.onclick = function() {
    modal.classList.remove('show');
}

// === AI Feature === //
const btnAiAnalyze = document.getElementById('btnAiAnalyze');
const aiAnalysisResult = document.getElementById('aiAnalysisResult');
const aiContent = document.getElementById('aiContent');
const closeAiPanel = document.getElementById('closeAiPanel');

closeAiPanel.onclick = function() {
    aiAnalysisResult.style.display = 'none';
}

function parseMarkdown(mdText) {
    let html = mdText;
    html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
    html = html.replace(/^\* (.*$)/gim, '<ul><li>$1</li></ul>');
    html = html.replace(/<\/ul>\n<ul>/gim, '');
    html = html.replace(/\n/gim, '<br>');
    return html;
}

btnAiAnalyze.onclick = async function() {
    if (!activeModalSymbol) return;
    
    // Prepare UI
    aiAnalysisResult.style.display = 'block';
    aiContent.innerHTML = '<span style="color:#a777e3;">Đang kết nối tới Gemini Web Chat qua CDP... Chờ khoảng 10-15 giây...</span>';
    btnAiAnalyze.disabled = true;
    
    const stockData = previousData[activeModalSymbol] || {};
    
    const payload = {
        symbol: activeModalSymbol,
        force: true,
        matchPrice: stockData.matchPrice || 0,
        totalVol: stockData.totalVol || 0,
        history: currentHistoryData,
        vbp: currentVbpData,
        depth: {
            buyP1: (stockData.buy || [])[0]?.price || 0,
            buyV1: (stockData.buy || [])[0]?.volume || 0,
            sellP1: (stockData.sell || [])[0]?.price || 0,
            sellV1: (stockData.sell || [])[0]?.volume || 0
        }
    };
    
    try {
        const response = await fetch(`${BASE_PATH}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const resData = await response.json();
        if (resData.status === 'success') {
            const aiTimestamp = document.getElementById('aiTimestamp');
            if (resData.timestamp) {
                applyAiTimestamp(aiTimestamp, resData.timestamp);
            }

            const parsedResult = parseAIResponse(resData.data);
            if (parsedResult.success) {
                const aiData = parsedResult.data;
                aiContent.innerHTML = `
                    <div class="ai-json-report">
                        <div class="ai-section">
                            <div class="ai-sec-title">📈 Xu hướng giá (30 ngày)</div>
                            <div class="ai-sec-desc">${aiData.trend || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">🎯 Hỗ trợ & Kháng cự</div>
                            <div class="ai-sec-desc">${aiData.support_resistance || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">⚖️ Cung - Cầu hiện tại</div>
                            <div class="ai-sec-desc">${aiData.supply_demand || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">💡 Kết luận tổng quan</div>
                            <div class="ai-sec-desc">${aiData.conclusion || 'N/A'}</div>
                        </div>
                        <div class="ai-section highlight">
                            <div class="ai-sec-title">⚡ Chiến lược Hành động</div>
                            <div class="ai-sec-desc">${aiData.strategy || 'N/A'}</div>
                        </div>
                    </div>
                `;
                
                // Cập nhật biểu đồ với Hỗ trợ/Kháng cự mới
                if (aiData.chart_lines && Array.isArray(aiData.chart_lines) && aiData.chart_lines.length > 0) {
                    renderChart(activeModalSymbol, aiData.chart_lines);
                }
            } else {
                aiContent.innerHTML = parseMarkdown(resData.data || 'Không có kết quả');
            }
        } else {
            if (resData.message === "LOGIN_REQUIRED") {
                aiContent.innerHTML = `
                    <div style="text-align:center; padding: 20px;">
                        <span style="color:#ffcc00; display:block; margin-bottom:10px;">Bạn chưa đăng nhập Gemini. Hãy đăng nhập trước khi phân tích!</span>
                        <button id="btnDoLogin" style="background: #a777e3; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold;">Mở trình duyệt đăng nhập</button>
                    </div>
                `;
                document.getElementById('btnDoLogin').onclick = async function() {
                    aiContent.innerHTML = '<span style="color:#a777e3;">Đang mở trình duyệt Google Chrome... Vui lòng đăng nhập trên cửa sổ vừa bật lên (Có thể chờ tới 5 phút)!</span>';
                    try {
                        const loginRes = await fetch(`${BASE_PATH}/api/login_gemini`, { method: 'POST' });
                        const loginData = await loginRes.json();
                        if (loginData.status === 'success') {
                            aiContent.innerHTML = '<span style="color:#00e676; font-weight: bold;">Đăng nhập thành công! Hãy bấm "Phân tích AI" lại để nhận báo cáo.</span>';
                        } else {
                            aiContent.innerHTML = `<span style="color:var(--color-down);">Lỗi đăng nhập: ${loginData.message}</span>`;
                        }
                    } catch (e) {
                        aiContent.innerHTML = `<span style="color:var(--color-down);">Lỗi mạng: ${e.message}</span>`;
                    }
                };
            } else {
                aiContent.innerHTML = `<span style="color:var(--color-down);">Lỗi: ${resData.message}</span>`;
            }
        }
    } catch (err) {
        aiContent.innerHTML = `<span style="color:var(--color-down);">Lỗi mạng: ${err.message}</span>`;
    } finally {
        btnAiAnalyze.disabled = false;
    }
}


window.onclick = function(event) {
    if (event.target == modal) {
        modal.classList.remove('show');
    }
}

let activeModalSymbol = null;

function formatVol(num) {
    if (num === 0 || !num) return "";
    return (num / 1000).toFixed(2).replace('.', ',');
}

function parseVol(str) {
    if (str === 0 || str === "0") return 0;
    if (!str) return 0;
    if (typeof str === 'number') return str;
    return parseFloat(str.toString().replace(/,/g, ''));
}

let currentVbpData = [];
let currentHistoryData = [];

window.openModal = function(symbol) {
    activeModalSymbol = symbol;
    document.getElementById('modalSymbol').innerText = symbol;
    
    // Đặt lại UI AI
    const aiAnalysisResult = document.getElementById('aiAnalysisResult');
    const aiContent = document.getElementById('aiContent');
    const aiTimestamp = document.getElementById('aiTimestamp');
    const btnAiAnalyze = document.getElementById('btnAiAnalyze');
    const btnShowAi = document.getElementById('btnShowAi');
    
    aiAnalysisResult.style.display = 'none';
    aiTimestamp.style.display = 'none';
    btnAiAnalyze.innerText = '🤖 Phân tích AI (Gemini)';
    if (btnShowAi) {
        btnShowAi.style.display = 'none';
        btnShowAi.onclick = function() {
            aiAnalysisResult.style.display = 'block';
        };
    }
    
    let cachedChartLines = [];
    
    // Thử lấy cache từ API với force=false
    fetch(`${BASE_PATH}/api/analyze`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbol: symbol, force: false })
    }).then(r => r.json()).then(resData => {
        if (resData.status === 'success' && resData.timestamp) {
            // Có cache!
            if (btnShowAi) {
                btnShowAi.style.display = 'inline-block';
            }
            applyAiTimestamp(aiTimestamp, resData.timestamp);
            btnAiAnalyze.innerText = '🔄 Làm mới phân tích';
            
            const parsedResult = parseAIResponse(resData.data);
            if (parsedResult.success) {
                const aiData = parsedResult.data;
                aiContent.innerHTML = `
                    <div class="ai-json-report">
                        <div class="ai-section">
                            <div class="ai-sec-title">📈 Xu hướng giá (30 ngày)</div>
                            <div class="ai-sec-desc">${aiData.trend || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">🎯 Hỗ trợ & Kháng cự</div>
                            <div class="ai-sec-desc">${aiData.support_resistance || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">⚖️ Cung - Cầu hiện tại</div>
                            <div class="ai-sec-desc">${aiData.supply_demand || 'N/A'}</div>
                        </div>
                        <div class="ai-section">
                            <div class="ai-sec-title">💡 Kết luận tổng quan</div>
                            <div class="ai-sec-desc">${aiData.conclusion || 'N/A'}</div>
                        </div>
                        <div class="ai-section highlight">
                            <div class="ai-sec-title">⚡ Chiến lược Hành động</div>
                            <div class="ai-sec-desc">${aiData.strategy || 'N/A'}</div>
                        </div>
                    </div>
                `;
                if (aiData.chart_lines && Array.isArray(aiData.chart_lines)) {
                    cachedChartLines = aiData.chart_lines;
                }
            } else {
                aiContent.innerHTML = parseMarkdown(resData.data || 'Không có kết quả');
            }
        }
    }).catch(err => console.log("Cache fetch err:", err)).finally(() => {
        renderChart(symbol, cachedChartLines);
    });
    
    // Tìm dữ liệu stock hiện tại
    const stock = previousData[symbol];
    if (stock) {
        const r = stock.raw || [];
        const safeRaw = (idx) => r[idx] || '';
        
        document.getElementById('modalStats').innerHTML = `
            <div class="stat-item"><span class="stat-label">Giá khớp</span><span class="stat-value ${getColorClass(stock.matchPrice, stock.ref, stock.ceil, stock.floor)}">${safeRaw(11)}</span></div>
            <div class="stat-item"><span class="stat-label">Tổng KL</span><span class="stat-value">${safeRaw(4)}</span></div>
            <div class="stat-item"><span class="stat-label">Tham chiếu</span><span class="stat-value text-ref">${safeRaw(1)}</span></div>
            <div class="stat-item"><span class="stat-label">Trần</span><span class="stat-value text-ceil">${safeRaw(2)}</span></div>
            <div class="stat-item"><span class="stat-label">Sàn</span><span class="stat-value text-floor">${safeRaw(3)}</span></div>
            <div class="stat-item"><span class="stat-label">Cao nhất</span><span class="stat-value ${getColorClass(stock.high, stock.ref, stock.ceil, stock.floor)}">${safeRaw(20)}</span></div>
            <div class="stat-item"><span class="stat-label">Thấp nhất</span><span class="stat-value ${getColorClass(stock.low, stock.ref, stock.ceil, stock.floor)}">${safeRaw(22)}</span></div>
        `;
        
        renderDepth(stock);
    }
    // Fetch and render VBP
    renderVBP(symbol);
    
    modal.classList.add('show');
    // renderChart was moved into the finally block of the fetch cache promise
}

let scanProgressInterval = null;

async function fetchScanProgress() {
    const statusEl = document.getElementById('gemini-status');
    if (!statusEl) return;
    try {
        const response = await fetch(`${BASE_PATH}/api/gemini/scan_progress`);
        const resData = await response.json();
        if (resData.status === 'success' && resData.data) {
            const progress = resData.data;
            let accountStr = progress.account_info ? ` [Tài khoản: ${progress.account_info}]` : '';
            if (progress.status === "Đã quét xong toàn bộ") {
                statusEl.innerHTML = `<span class="dot" style="background-color: #00dc58;"></span> Gemini: Đã quét xong (${progress.scanned}/${progress.total})${accountStr}`;
                if (scanProgressInterval) clearInterval(scanProgressInterval);
            } else {
                let symbolText = progress.current_symbol ? `[${progress.current_symbol}]` : '';
                statusEl.innerHTML = `<span class="dot pulse" style="background-color: #00dc58;"></span> Gemini: ${progress.status} ${symbolText} (${progress.scanned}/${progress.total})${accountStr}`;
            }
        }
    } catch (e) {
        // Ignore progress fetch errors
    }
}

// --- Gemini Status ---
async function checkGeminiStatus() {
    const statusEl = document.getElementById('gemini-status');
    if (!statusEl) return;
    try {
        const response = await fetch(`${BASE_PATH}/api/gemini/status`);
        const data = await response.json();
        const geminiStatus = document.getElementById('gemini-status');
        const btnToggleAuto = document.getElementById('btn-toggle-auto');
        
        if (!btnToggleAuto.disabled) {
            if (data.data && data.data.is_auto_scan_paused) {
                btnToggleAuto.innerText = "Bật Auto";
                btnToggleAuto.style.background = "#2ecc71"; // Xanh
            } else {
                btnToggleAuto.innerText = "Tắt Auto";
                btnToggleAuto.style.background = "#e74c3c"; // Đỏ
            }
        }

        if (data.is_logged_in) {
            statusEl.innerHTML = '<span class="dot pulse" style="background-color: #00dc58;"></span> Gemini: Đã đăng nhập (Đang tải tiến độ...)';
            statusEl.onclick = null;
            statusEl.style.cursor = 'default';
            statusEl.style.color = '#00dc58';
            
            const btnResetScan = document.getElementById('btnResetScan');
            if (btnResetScan) btnResetScan.style.display = 'inline-block';
            
            if (!scanProgressInterval) {
                scanProgressInterval = setInterval(fetchScanProgress, 2000);
            }
            fetchScanProgress();
            
        } else {
            const btnResetScan = document.getElementById('btnResetScan');
            if (btnResetScan) btnResetScan.style.display = 'none';
            if (scanProgressInterval) {
                clearInterval(scanProgressInterval);
                scanProgressInterval = null;
            }
            statusEl.innerHTML = '<span class="dot" style="background-color: #ffcc00;"></span> Gemini: Chưa đăng nhập (Click để Đăng nhập)';
            statusEl.style.color = '#ffcc00';
            statusEl.style.cursor = 'pointer';
            statusEl.onclick = async function() {
                statusEl.innerHTML = '<span class="dot" style="background-color: #ffcc00;"></span> Đang mở cửa sổ đăng nhập...';
                await fetch(`${BASE_PATH}/api/login_gemini`, {method: 'POST'});
                setTimeout(checkGeminiStatus, 5000);
            };
        }
    } catch (e) {
        if (scanProgressInterval) {
            clearInterval(scanProgressInterval);
            scanProgressInterval = null;
        }
        statusEl.innerHTML = '<span class="dot" style="background-color: #ff3333;"></span> Gemini: Mất kết nối (Click để thử lại)';
        statusEl.style.color = '#ff3333';
        statusEl.style.cursor = 'pointer';
        statusEl.onclick = checkGeminiStatus;
    }
}
setTimeout(checkGeminiStatus, 2000);
setInterval(checkGeminiStatus, 60000); // Check every minute

const btnResetScan = document.getElementById('btnResetScan');
if (btnResetScan) {
    btnResetScan.onclick = async function() {
        btnResetScan.innerText = "Đang bắt đầu...";
        btnResetScan.disabled = true;
        try {
            await syncTargetsToServer(); // Đồng bộ mục tiêu đã chọn
            await fetch(`${BASE_PATH}/api/gemini/reset_scan`, { method: 'POST' });
            // Cập nhật ngay tiến trình để thấy phản hồi
            fetchScanProgress();
        } catch(e) {}
        setTimeout(() => {
            btnResetScan.innerText = "🔄 Quét lại";
            btnResetScan.disabled = false;
        }, 2000);
    };
}

async function renderVBP(symbol) {
    const vbpContent = document.getElementById('vbpContent');
    if (!vbpContent) return;
    
    vbpContent.innerHTML = '<div style="text-align:center; padding: 20px; color: #888;">Đang tải dữ liệu Khối lượng theo mức giá...</div>';
    
    try {
        const response = await fetch(`${BASE_PATH}/api/vbp/${symbol}`);
        const data = await response.json();
        currentVbpData = data;
        
        if (!data || data.length === 0) {
            vbpContent.innerHTML = '<div style="text-align:center; padding: 20px; color: #d40337;">Không có dữ liệu VBP.</div>';
            return;
        }
        
        // Find max volume to calculate bar widths
        let maxVol = 0;
        let totalVol = 0;
        let totalBuy = 0;
        let totalSell = 0;
        
        data.forEach(item => {
            if (item.volume > maxVol) maxVol = item.volume;
            totalVol += item.volume;
        });
        
        // Render
        let html = `
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #888; padding: 5px; border-bottom: 1px solid #333; margin-bottom: 5px;">
                <span style="width: 40px; text-align: left;">Giá</span>
                <span style="flex: 1; text-align: right;">Khối lượng</span>
                <span style="width: 40px; text-align: right;">%</span>
            </div>
        `;
        
        // Sort data descending by price for UI
        data.sort((a, b) => b.price - a.price);

        // Determine stock colors
        const stock = previousData[symbol] || {};
        const ref = parseVol(stock.ref) || 0;
        const ceil = parseVol(stock.ceil) || 0;
        const floor = parseVol(stock.floor) || 0;

        data.forEach(item => {
            const width = maxVol > 0 ? (item.volume / maxVol) * 100 : 0;
            const percent = totalVol > 0 ? ((item.volume / totalVol) * 100).toFixed(1) : 0;
            
            let pColorClass = 'text-ref';
            let barColor = 'rgba(255, 171, 0, 0.2)'; // default ref color
            
            if (item.price > ref && item.price < ceil) {
                pColorClass = 'text-up';
                barColor = 'rgba(14, 203, 129, 0.2)';
            } else if (item.price < ref && item.price > floor) {
                pColorClass = 'text-down';
                barColor = 'rgba(246, 70, 93, 0.2)';
            } else if (item.price === ceil) {
                pColorClass = 'text-ceil';
                barColor = 'rgba(200, 30, 200, 0.2)';
            } else if (item.price === floor) {
                pColorClass = 'text-floor';
                barColor = 'rgba(0, 200, 255, 0.2)';
            }
            
            html += `
                <div style="display: flex; position: relative; justify-content: space-between; padding: 4px 5px; font-size: 12px; margin-bottom: 2px; align-items: center;">
                    <div style="position: absolute; right: 0; top: 0; bottom: 0; width: ${width}%; background-color: ${barColor}; z-index: 0;"></div>
                    <span class="${pColorClass}" style="z-index: 1; font-weight: bold; width: 40px; text-align: left;">${item.price.toFixed(2)}</span>
                    <span style="z-index: 1; color: #fff; flex: 1; text-align: right;">${formatVol(item.volume * 1000)}</span>
                    <span style="z-index: 1; color: #888; width: 40px; text-align: right;">${percent}%</span>
                </div>
            `;
        });
        
        vbpContent.innerHTML = html;
        
    } catch (e) {
        console.error("VBP Render Error:", e);
        vbpContent.innerHTML = '<div style="text-align:center; padding: 20px; color: #d40337;">Lỗi khi tải VBP.</div>';
    }
}

function renderDepth(stock) {
    const depthContent = document.getElementById('depthContent');
    const r = stock.raw || [];
    const safeRaw = (idx) => r[idx] || '';
    
    const buys = [
        { p: stock.buyP1, pt: safeRaw(9), v: parseVol(safeRaw(10)), vt: safeRaw(10) },
        { p: stock.buyP2, pt: safeRaw(7), v: parseVol(safeRaw(8)), vt: safeRaw(8) },
        { p: stock.buyP3, pt: safeRaw(5), v: parseVol(safeRaw(6)), vt: safeRaw(6) }
    ].filter(x => x.p > 0);
    
    const sells = [
        { p: stock.sellP1, pt: safeRaw(14), v: parseVol(safeRaw(15)), vt: safeRaw(15) },
        { p: stock.sellP2, pt: safeRaw(16), v: parseVol(safeRaw(17)), vt: safeRaw(17) },
        { p: stock.sellP3, pt: safeRaw(18), v: parseVol(safeRaw(19)), vt: safeRaw(19) }
    ].filter(x => x.p > 0);
    
    // Tính max vol để chia phần trăm thanh
    let maxVol = 1;
    [...buys, ...sells].forEach(x => { if(x.v > maxVol) maxVol = x.v; });
    
    // Chuẩn bị html
    let html = '';
    
    for (let i = 0; i < 3; i++) {
        let b = buys[i] || { pt: '', vt: '', v: 0 };
        let s = sells[i] || { pt: '', vt: '', v: 0 };
        
        let bw = maxVol > 0 ? (b.v / maxVol) * 100 : 0;
        let sw = maxVol > 0 ? (s.v / maxVol) * 100 : 0;
        
        let bColor = b.pt ? getColorClass(b.p, stock.ref, stock.ceil, stock.floor) : '';
        let sColor = s.pt ? getColorClass(s.p, stock.ref, stock.ceil, stock.floor) : '';
        
        html += `
            <div class="depth-row" style="margin-bottom: 2px;">
                <div class="depth-buy-side" style="padding-right: 5px;">
                    <div class="depth-buy-bar" style="width: ${bw}%; right: 0; background-color: rgba(14, 203, 129, 0.2);"></div>
                    <span class="depth-val text-white" style="z-index: 1; text-align: left;">${b.vt}</span>
                    <span class="depth-price ${bColor}" style="z-index: 1; text-align: right; font-weight: bold; width: 45px;">${b.pt}</span>
                </div>
                
                <div class="depth-sell-side" style="padding-left: 5px; border-left: 1px solid #333;">
                    <div class="depth-sell-bar" style="width: ${sw}%; left: 0; background-color: rgba(246, 70, 93, 0.2);"></div>
                    <span class="depth-price ${sColor}" style="z-index: 1; text-align: left; font-weight: bold; width: 45px;">${s.pt}</span>
                    <span class="depth-val text-white" style="z-index: 1; text-align: right;">${s.vt}</span>
                </div>
            </div>
        `;
    }
    
    if (depthContent) depthContent.innerHTML = html;
}

let currentChart = null;
let currentCandlestickSeries = null;
async function renderChart(symbol, chartLines = []) {
    const chartContainer = document.getElementById('tv_chart_container');
    if (!chartContainer) return;
    
    // Xóa chart cũ nếu có
    if (currentChart) {
        currentChart.remove();
        currentChart = null;
        currentCandlestickSeries = null;
    }
    
    chartContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:#888; font-style:italic;">Đang tải dữ liệu biểu đồ...</div>';
    
    try {
        const response = await fetch(`${BASE_PATH}/api/history/${symbol}`);
        const data = await response.json();
        currentHistoryData = data;
        
        if (!data || data.length === 0) {
            chartContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:#d40337;">Không tìm thấy dữ liệu hoặc lỗi cào dữ liệu.</div>';
            return;
        }
        
        chartContainer.innerHTML = '';
        
        const chartOptions = {
            localization: {
                locale: 'en-GB',
            },
            layout: {
                textColor: '#d1d4dc',
                background: { type: 'solid', color: 'rgba(19, 23, 34, 1)' },
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 1)' },
                horzLines: { color: 'rgba(42, 46, 57, 1)' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: 'rgba(42, 46, 57, 1)',
            },
            timeScale: {
                borderColor: 'rgba(42, 46, 57, 1)',
                timeVisible: true,
                secondsVisible: false,
            },
        };
        
        currentChart = LightweightCharts.createChart(chartContainer, chartOptions);
        
        const candlestickSeries = currentChart.addCandlestickSeries({
            upColor: '#00dc58',
            downColor: '#d40337',
            borderDownColor: '#d40337',
            borderUpColor: '#00dc58',
            wickDownColor: '#d40337',
            wickUpColor: '#00dc58',
        });
        
        candlestickSeries.setData(data);
        
        const volumeSeries = currentChart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: '', 
        });
        
        currentChart.priceScale('').applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        currentChart.priceScale('right').applyOptions({
            scaleMargins: {
                top: 0.1,
                bottom: 0.25,
            },
        });
        
        const volumeData = data.map(d => ({
            time: d.time,
            value: d.value,
            color: d.close >= d.open ? 'rgba(0, 220, 88, 0.5)' : 'rgba(212, 3, 55, 0.5)'
        }));
        volumeSeries.setData(volumeData);
        
        currentCandlestickSeries = candlestickSeries;
        currentChart.timeScale().fitContent();
        
        // Vẽ các đường Hỗ trợ / Kháng cự từ AI
        if (chartLines && chartLines.length > 0) {
            chartLines.forEach(line => {
                const color = line.type === 'support' ? '#00dc58' : '#d40337';
                candlestickSeries.createPriceLine({
                    price: line.price,
                    color: color,
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: line.label,
                });
            });
        }
        
        // Thêm resize listener
        new ResizeObserver(entries => {
            if (entries.length === 0 || entries[0].target !== chartContainer) return;
            const newRect = entries[0].contentRect;
            currentChart.applyOptions({ height: newRect.height, width: newRect.width });
        }).observe(chartContainer);
        
    } catch (e) {
        console.error("Lỗi vẽ chart:", e);
        chartContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:#d40337;">Lỗi kết nối khi cào dữ liệu biểu đồ.</div>';
    }
}

// Cập nhật lại Modal Data nếu có cổ phiếu mới
setInterval(() => {
    if (activeModalSymbol && previousData[activeModalSymbol]) {
        renderDepth(previousData[activeModalSymbol]);
        
        const stock = previousData[activeModalSymbol];
        const r = stock.raw || [];
        const safeRaw = (idx) => r[idx] || '';
        
        const statsEl = document.getElementById('modalStats');
        if (statsEl) {
            statsEl.innerHTML = `
                <div class="stat-item"><span class="stat-label">Giá khớp</span><span class="stat-value ${getColorClass(stock.matchPrice, stock.ref, stock.ceil, stock.floor)}">${safeRaw(11)}</span></div>
                <div class="stat-item"><span class="stat-label">Tổng KL</span><span class="stat-value">${safeRaw(4)}</span></div>
                <div class="stat-item"><span class="stat-label">Tham chiếu</span><span class="stat-value text-ref">${safeRaw(1)}</span></div>
                <div class="stat-item"><span class="stat-label">Trần</span><span class="stat-value text-ceil">${safeRaw(2)}</span></div>
                <div class="stat-item"><span class="stat-label">Sàn</span><span class="stat-value text-floor">${safeRaw(3)}</span></div>
                <div class="stat-item"><span class="stat-label">Cao nhất</span><span class="stat-value ${getColorClass(stock.high, stock.ref, stock.ceil, stock.floor)}">${safeRaw(20)}</span></div>
                <div class="stat-item"><span class="stat-label">Thấp nhất</span><span class="stat-value ${getColorClass(stock.low, stock.ref, stock.ceil, stock.floor)}">${safeRaw(22)}</span></div>
            `;
        }
    }
}, 1000);

// --- Quick Navigation Logic ---
function getVisibleSymbols() {
    const symbols = [];
    document.querySelectorAll('#board-body tr.stock-row').forEach(row => {
        if (row.style.display !== 'none') {
            symbols.push(row.id.replace('stock-', ''));
        }
    });
    return symbols;
}

const btnPrevStock = document.getElementById('btnPrevStock');
const btnNextStock = document.getElementById('btnNextStock');

if (btnPrevStock) {
    btnPrevStock.onclick = function() {
        const visibleSymbols = getVisibleSymbols();
        if (!activeModalSymbol || visibleSymbols.length === 0) return;
        let idx = visibleSymbols.indexOf(activeModalSymbol);
        if (idx > 0) {
            openModal(visibleSymbols[idx - 1]);
        } else if (idx === 0) {
            // Vòng lại stock cuối cùng
            openModal(visibleSymbols[visibleSymbols.length - 1]);
        }
    };
}

if (btnNextStock) {
    btnNextStock.onclick = function() {
        const visibleSymbols = getVisibleSymbols();
        if (!activeModalSymbol || visibleSymbols.length === 0) return;
        let idx = visibleSymbols.indexOf(activeModalSymbol);
        if (idx !== -1 && idx < visibleSymbols.length - 1) {
            openModal(visibleSymbols[idx + 1]);
        } else if (idx === visibleSymbols.length - 1) {
            // Vòng lại stock đầu tiên
            openModal(visibleSymbols[0]);
        }
    };
}

function changeIndustry(val, btnContainer) {
    document.querySelectorAll('.tabs-menu .tab-item').forEach(t => t.classList.remove('active'));
    if (btnContainer) btnContainer.classList.add('active');
    
    currentIndustry = val;
    currentCategory = 'all'; // Khi chọn ngành thì bỏ lọc sàn

    // Cập nhật text cho menu CP Ngành (đã bị vô hiệu hóa để tránh thay đổi kích thước menu)
    /*
    if (btnContainer) {
        const dropbtn = btnContainer.querySelector('.dropbtn');
        if (dropbtn) {
            dropbtn.innerHTML = `${val} <span class="arrow">▼</span>`;
        }
    }
    */
    
    // Đặt lại các menu sàn về mặc định
    const btnHose = document.getElementById('btn-hose');
    const btnHnx = document.getElementById('btn-hnx');
    const btnUpcom = document.getElementById('btn-upcom');
    if (btnHose) btnHose.innerHTML = `HOSE <span class="arrow">▼</span>`;
    if (btnHnx) btnHnx.innerHTML = `HNX <span class="arrow">▼</span>`;
    if (btnUpcom) btnUpcom.innerHTML = `UPCOM <span class="arrow">▼</span>`;


    // Áp dụng ngay bộ lọc lên các dòng hiện tại
    const rows = document.querySelectorAll('#board-body tr.stock-row');
    rows.forEach(tr => {
        let sym = tr.id.replace('stock-', '');
        let stock = previousData[sym];
        if (stock) {
            tr.style.display = isVisible(stock) ? '' : 'none';
        }
    });
}


async function changeCategory(cat, btn, displayName) {
    document.querySelectorAll('.tabs-menu .tab-item').forEach(t => t.classList.remove('active'));
    
    let container = null;
    if (btn) {
        if (btn.classList.contains('tab-item')) {
            container = btn;
        } else {
            container = btn.closest('.tab-item');
        }
        if (container) container.classList.add('active');
        
        // Update text if it's a dropdown menu (đã bị vô hiệu hóa để menu cố định)
        /*
        if (container && container.classList.contains('dropdown') && displayName) {
            const dropbtn = container.querySelector('.dropbtn');
            if (dropbtn) {
                dropbtn.innerHTML = `${displayName} <span class="arrow">▼</span>`;
            }
        }
        */
    }
    
    // Đặt lại menu CP Ngành về mặc định
    const indBtn = document.querySelector('#industry-dropdown')?.closest('.tab-item')?.querySelector('.dropbtn');
    if (indBtn) indBtn.innerHTML = `CP ngành <span class="arrow">▼</span>`;
    
    currentCategory = cat.toLowerCase();
    currentIndustry = 'all';
    
    // Áp dụng ngay bộ lọc lên các dòng hiện tại
    const rows = document.querySelectorAll('#board-body tr.stock-row');
    rows.forEach(tr => {
        let sym = tr.id.replace('stock-', '');
        let stock = previousData[sym];
        if (stock) {
            tr.style.display = isVisible(stock) ? '' : 'none';
        }
    });
}
syncTargetsToServer();
// trigger reload
