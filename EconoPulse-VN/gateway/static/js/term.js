/* ==========================================================================
   Market Pulse — term.js  ·  TỪ ĐIỂN THUẬT NGỮ DÙNG CHUNG + tooltip F0
   --------------------------------------------------------------------------
   ĐÂY LÀ NGUỒN DUY NHẤT của mọi chú thích thuật ngữ trên toàn hệ thống.
   Mọi trang (stock.js, market.js, home-v3.js, screener.js...) PHẢI đọc từ đây
   thay vì tự viết lại chú thích, nếu không cùng một từ sẽ có hai nghĩa lệch nhau.

   Xuất ra window.MPTerm:
     MPTerm.TERMS               — object thô { key: {vi, plain, unit?} }
     MPTerm.get(key)            — tra 1 từ (không phân biệt hoa/thường, có bảng alias)
     MPTerm.vi(key)             — tên đầy đủ tiếng Việt
     MPTerm.plain(key)          — 1 câu "nghĩa là gì" cho người chưa biết gì
     MPTerm.attrs(key)          — chuỗi thuộc tính HTML để gắn vào 1 thẻ bất kỳ
     MPTerm.chip(key, label)    — HTML nhãn có gạch chấm, tap/hover ra chú thích
     MPTerm.hint(key)           — HTML chú thích HIỆN SẴN dạng chữ (không phải tap)
     MPTerm.label(key, label)   — nhãn + chú thích hiện sẵn (dùng cho chỉ số quan trọng)
     MPTerm.list()              — mảng [{key, vi, plain}] đã sắp A→Z (cho trang /kien-thuc)
     MPTerm.scan(root)          — quét text, tự gạch chấm thuật ngữ trong vùng root

   Tooltip: TAP mở được trên mobile, tap ra ngoài / Esc để đóng, có role="tooltip"
   + aria-describedby, đi được bằng bàn phím (Tab → Enter/Space).
   ========================================================================== */
(function () {
  "use strict";

  /* ---------------------------------------------------------------------
     TỪ ĐIỂN. Quy tắc viết:
       vi    = tên đầy đủ tiếng Việt (viết hết chữ, không viết tắt).
       plain = MỘT câu trả lời cho câu hỏi "nghĩa là gì", dùng từ đời thường.
               KHÔNG được giải thích thuật ngữ bằng một thuật ngữ khác.
     --------------------------------------------------------------------- */
  const TERMS = {
    /* ---- giao dịch hằng ngày ---- */
    "KLGD": {
      vi: "Khối lượng giao dịch",
      plain: "Số cổ phiếu đã được mua đi bán lại trong phiên. Càng nhiều thì càng nhiều người đang tham gia mua bán mã đó.",
    },
    "GTGD": {
      vi: "Giá trị giao dịch",
      plain: "Tổng số tiền đã trao tay khi mua bán mã đó trong phiên, tính bằng đồng.",
    },
    "thanh khoản": {
      vi: "Thanh khoản",
      plain: "Mức dễ mua dễ bán. Thanh khoản cao nghĩa là lúc bạn muốn bán thì có người mua ngay, không phải hạ giá nhiều để bán được.",
    },
    "vốn hóa": {
      vi: "Vốn hóa thị trường",
      plain: "Giá một cổ phiếu nhân với tổng số cổ phiếu công ty đã phát hành — tức số tiền thị trường đang trả cho toàn bộ công ty.",
    },
    "khối ngoại": {
      vi: "Khối ngoại (nhà đầu tư nước ngoài)",
      plain: "Nhóm người mua bán đến từ nước ngoài. Họ mua nhiều hơn bán gọi là mua ròng, bán nhiều hơn mua gọi là bán ròng.",
    },
    "mua ròng": {
      vi: "Mua ròng",
      plain: "Trong cùng khoảng thời gian, số tiền mua nhiều hơn số tiền bán; phần chênh lệch đó gọi là mua ròng.",
    },
    "bán ròng": {
      vi: "Bán ròng",
      plain: "Trong cùng khoảng thời gian, số tiền bán nhiều hơn số tiền mua; phần chênh lệch đó gọi là bán ròng.",
    },
    "độ rộng thị trường": {
      vi: "Độ rộng thị trường",
      plain: "Đếm xem trong phiên có bao nhiêu mã tăng giá và bao nhiêu mã giảm giá. Nhiều mã tăng thì cả thị trường đang khỏe, chứ không chỉ vài mã lớn kéo.",
    },
    "breadth": {
      vi: "Độ rộng thị trường",
      plain: "Đếm xem trong phiên có bao nhiêu mã tăng giá và bao nhiêu mã giảm giá, để biết cả thị trường khỏe hay chỉ vài mã lớn khỏe.",
    },

    /* ---- định giá ---- */
    "P/E": {
      vi: "Giá trên lợi nhuận một cổ phiếu",
      plain: "Bạn phải trả bao nhiêu đồng để mua được một đồng lợi nhuận mỗi năm của công ty. Số càng lớn thì đang trả càng đắt; chỉ có ý nghĩa khi so với công ty cùng ngành.",
    },
    "P/B": {
      vi: "Giá trên giá trị sổ sách một cổ phiếu",
      plain: "Bạn phải trả bao nhiêu đồng để mua một đồng tài sản ròng mà công ty đang ghi trên sổ sách. Trên 1 là trả cao hơn giá trị ghi sổ.",
    },
    "EPS": {
      vi: "Lợi nhuận trên mỗi cổ phiếu",
      plain: "Chia toàn bộ lợi nhuận cả năm của công ty cho số cổ phiếu, xem mỗi cổ phiếu làm ra được bao nhiêu đồng lãi.",
    },
    "EV/EBITDA": {
      vi: "Giá trị doanh nghiệp trên lợi nhuận trước lãi vay, thuế và khấu hao",
      plain: "Một cách xem công ty đắt hay rẻ có tính cả số nợ công ty đang vay, không chỉ tính giá cổ phiếu.",
    },

    /* ---- hiệu quả kinh doanh ---- */
    "ROE": {
      vi: "Tỷ suất lợi nhuận trên vốn chủ sở hữu",
      plain: "Với 100 đồng tiền của các ông chủ góp vào, công ty làm ra bao nhiêu đồng lãi một năm. Càng cao càng làm ăn giỏi.",
    },
    "ROA": {
      vi: "Tỷ suất lợi nhuận trên tổng tài sản",
      plain: "Với 100 đồng tài sản đang có (nhà xưởng, tiền, hàng hóa...), công ty làm ra bao nhiêu đồng lãi một năm.",
    },
    "DuPont": {
      vi: "Cách tách ROE theo DuPont",
      plain: "Cách bóc tách xem công ty lãi nhiều là do bán được giá, do quay vòng hàng nhanh, hay do vay nợ nhiều.",
    },

    /* ---- cổ tức ---- */
    "cổ tức": {
      vi: "Cổ tức",
      plain: "Phần lãi công ty chia lại cho người đang giữ cổ phiếu, trả bằng tiền hoặc bằng cổ phiếu mới.",
    },
    "tỷ suất cổ tức": {
      vi: "Tỷ suất cổ tức",
      plain: "Số tiền cổ tức nhận được trong một năm so với số tiền bỏ ra mua cổ phiếu, tính theo phần trăm — giống cách nhìn lãi gửi tiết kiệm.",
    },
    "payout": {
      vi: "Tỷ lệ chi trả cổ tức",
      plain: "Trong 100 đồng lãi kiếm được, công ty đem chia cho chủ sở hữu bao nhiêu đồng, còn lại giữ để làm ăn tiếp.",
    },
    "GDKHQ": {
      vi: "Ngày giao dịch không hưởng quyền",
      plain: "Từ ngày này trở đi, ai mới mua cổ phiếu sẽ không được nhận đợt cổ tức hay quyền lợi đang chia lần đó.",
    },

    /* ---- sức khỏe tài chính ---- */
    "F-Score": {
      vi: "Điểm sức khỏe tài chính Piotroski",
      plain: "Chấm 9 câu hỏi kiểu có hoặc không về sổ sách công ty (lãi hay lỗ, tiền vào có thật không, nợ tăng hay giảm...). Được mấy câu tốt thì tính mấy điểm, tối đa 9.",
    },
    "F-score": {
      vi: "Điểm sức khỏe tài chính Piotroski",
      plain: "Chấm 9 câu hỏi có hoặc không về sổ sách công ty; càng nhiều câu đạt thì nền tảng tài chính càng vững, tối đa 9 điểm.",
    },
    "Piotroski F-score": {
      vi: "Điểm sức khỏe tài chính Piotroski",
      plain: "Chấm 9 câu hỏi có hoặc không về sổ sách công ty; càng nhiều câu đạt thì nền tảng tài chính càng vững, tối đa 9 điểm.",
    },
    "Altman Z": {
      vi: "Điểm cảnh báo khó khăn tài chính Altman",
      plain: "Một công thức cộng 4 con số trên sổ sách để đoán khả năng công ty rơi vào cảnh mất khả năng trả nợ. Điểm càng thấp càng đáng lo. Không dùng cho ngân hàng.",
    },
    "Altman Z''-score": {
      vi: "Điểm cảnh báo khó khăn tài chính Altman",
      plain: "Công thức cộng 4 con số trên sổ sách để đoán khả năng công ty mất khả năng trả nợ. Trên 2,6 là an toàn, 1,1–2,6 là vùng cần theo dõi, dưới 1,1 là đáng lo. Không dùng cho ngân hàng.",
    },
    "Z''-score": {
      vi: "Điểm cảnh báo khó khăn tài chính Altman",
      plain: "Công thức cộng 4 con số trên sổ sách để đoán khả năng công ty mất khả năng trả nợ; điểm càng thấp càng đáng lo.",
    },
    "nợ trên vốn chủ sở hữu": {
      vi: "Nợ trên vốn chủ sở hữu",
      plain: "Cứ 1 đồng tiền các ông chủ góp thì công ty đang vay bao nhiêu đồng. Vay càng nhiều thì lãi vay càng nặng và càng dễ gặp khó khi buôn bán chậm.",
    },

    /* ---- kỹ thuật giá ---- */
    "RSI": {
      vi: "Chỉ số sức mạnh tương đối của giá",
      plain: "Một con số từ 0 đến 100 cho biết giá vừa tăng liên tục hay giảm liên tục trong khoảng hai tuần gần đây. Trên 70 là đã tăng rất nhiều, dưới 30 là đã giảm rất nhiều.",
    },
    "MA": {
      vi: "Đường giá trung bình",
      plain: "Lấy giá đóng cửa của nhiều ngày gần nhất rồi tính trung bình, vẽ thành một đường mượt để thấy xu hướng chung mà không bị nhiễu bởi từng ngày lên xuống.",
    },
    "MA20": {
      vi: "Đường giá trung bình 20 ngày",
      plain: "Giá trung bình của 20 ngày giao dịch gần nhất, cho thấy hướng đi ngắn hạn của giá.",
    },
    "MA50": {
      vi: "Đường giá trung bình 50 ngày",
      plain: "Giá trung bình của 50 ngày giao dịch gần nhất, cho thấy hướng đi trung hạn của giá.",
    },
    "MA200": {
      vi: "Đường giá trung bình 200 ngày",
      plain: "Giá trung bình của 200 ngày giao dịch gần nhất, thường dùng để nhìn hướng đi dài hạn của giá.",
    },
    "beta": {
      vi: "Độ nhạy của giá so với thị trường",
      plain: "Khi cả thị trường nhích 1 phần, mã này thường nhích bao nhiêu phần. Lớn hơn 1 là nhảy mạnh hơn thị trường, cả lúc lên lẫn lúc xuống.",
    },
    "volatility": {
      vi: "Mức dao động giá",
      plain: "Giá thường lên xuống nhiều hay ít. Dao động lớn nghĩa là giá nhảy mạnh, giữ mã đó cảm giác bấp bênh hơn.",
    },
    "RS": {
      vi: "Sức mạnh tương đối",
      plain: "So mã hoặc ngành này chạy nhanh hay chậm hơn cả thị trường trong cùng khoảng thời gian (hệ thống dùng 12 tuần).",
    },

    /* ---- thời gian & so sánh kỳ ---- */
    "YoY": {
      vi: "So với cùng kỳ năm trước",
      plain: "Đem con số kỳ này so với đúng kỳ đó của năm ngoái, ví dụ quý 2 năm nay so với quý 2 năm ngoái, để bỏ qua yếu tố mùa vụ.",
    },
    "QoQ": {
      vi: "So với quý liền trước",
      plain: "Đem con số quý này so với quý ngay trước đó, để thấy thay đổi mới nhất.",
    },
    "TTM": {
      vi: "Bốn quý gần nhất cộng lại",
      plain: "Cộng số liệu của 4 quý vừa qua thành một năm trọn, để có bức tranh mới nhất mà không phải chờ hết năm.",
    },

    /* ---- thống kê & mô hình ---- */
    "percentile": {
      vi: "Mốc phân vị",
      plain: "Nói mức này thấp hay cao so với quá khứ: mốc 25 nghĩa là 25 phần trăm số lần trong quá khứ còn thấp hơn mức đó.",
    },
    "trung vị": {
      vi: "Trung vị",
      plain: "Xếp tất cả số liệu từ nhỏ đến lớn rồi lấy số nằm giữa. Khác trung bình, nó không bị một vài số cực lớn kéo lệch.",
    },
    "khoảng tin cậy": {
      vi: "Khoảng tin cậy",
      plain: "Dải giá trị mà kết quả thật có nhiều khả năng nằm trong đó. Dải rộng nghĩa là dự báo còn nhiều điều chưa chắc.",
    },
    "Sharpe": {
      vi: "Hệ số Sharpe",
      plain: "Đo xem để có được mức lời đó thì phải chịu bao nhiêu cảnh giá nhảy lên nhảy xuống. Số cao là lời được nhiều mà ít chao đảo.",
    },
    "Sharpe ratio": {
      vi: "Hệ số Sharpe",
      plain: "Đo xem để có được mức lời đó thì phải chịu bao nhiêu cảnh giá nhảy lên nhảy xuống; số cao là lời nhiều mà ít chao đảo.",
    },
    "HHI": {
      vi: "Mức tập trung dòng tiền",
      plain: "Cho biết tiền mua bán đang dồn vào ít mã hay trải đều nhiều mã. Dồn vào ít mã thì thị trường lệ thuộc vào vài mã đó.",
    },
    "SARIMAX": {
      vi: "Mô hình dự báo theo chuỗi thời gian có yếu tố mùa vụ",
      plain: "Một công thức máy tính học từ số liệu nhiều năm để đoán số liệu các kỳ tới, có tính đến chuyện mỗi năm lặp lại theo mùa.",
    },
    "QUBO": {
      vi: "Bài toán tối ưu dạng chọn hoặc không chọn",
      plain: "Cách viết lại bài toán chọn ra vài mã trong rất nhiều mã, dưới dạng mỗi mã chỉ có hai lựa chọn: lấy hoặc không lấy.",
    },
    "QAOA": {
      vi: "Thuật toán tối ưu kiểu lượng tử",
      plain: "Một cách tìm phương án tốt trong cực nhiều phương án, ở đây chạy trên máy tính thường mô phỏng lại cách máy lượng tử làm.",
    },
    "CBTT": {
      vi: "Công bố thông tin",
      plain: "Tin công ty buộc phải thông báo công khai cho mọi người biết theo quy định của sàn, ví dụ đổi lãnh đạo hay kết quả kinh doanh.",
    },
  };

  /* Từ đồng nghĩa/biến thể → khóa chính, để tra cứu không bị vỡ khi gọi khác cách. */
  const ALIAS = {
    "pe": "P/E", "p/e": "P/E", "pb": "P/B", "p/b": "P/B",
    "eps": "EPS", "roe": "ROE", "roa": "ROA", "rsi": "RSI", "ma": "MA",
    "klgd": "KLGD", "gtgd": "GTGD",
    "khối lượng giao dịch": "KLGD", "khoi luong giao dich": "KLGD",
    "giá trị giao dịch": "GTGD", "gia tri giao dich": "GTGD",
    "vốn hóa thị trường": "vốn hóa", "marketcap": "vốn hóa", "market cap": "vốn hóa",
    "fscore": "F-Score", "f_score": "F-Score", "f-score": "F-Score",
    "piotroski": "F-Score", "piotroski f-score": "F-Score",
    "altman": "Altman Z", "altman z": "Altman Z", "z-score": "Altman Z",
    "zscore": "Altman Z", "altman z-score": "Altman Z",
    "yoy": "YoY", "qoq": "QoQ", "ttm": "TTM",
    "de": "nợ trên vốn chủ sở hữu", "d/e": "nợ trên vốn chủ sở hữu",
    "debt_to_equity": "nợ trên vốn chủ sở hữu",
    "dividend_yield": "tỷ suất cổ tức", "dividend yield": "tỷ suất cổ tức",
    "co tuc": "cổ tức", "dividend": "cổ tức",
    "liquidity": "thanh khoản", "thanh khoan": "thanh khoản",
    "foreign": "khối ngoại", "khoi ngoai": "khối ngoại",
    "breadth": "độ rộng thị trường", "do rong thi truong": "độ rộng thị trường",
    "beta": "beta", "sharpe": "Sharpe",
  };

  /* Những từ QUAN TRỌNG NHẤT với người mới — nghĩa phải hiện sẵn dạng chữ,
     không bắt người dùng tap mới thấy (dùng bởi MPTerm.label / data-term-label). */
  const ALWAYS_VISIBLE = new Set([
    "P/E", "P/B", "ROE", "EPS", "vốn hóa", "thanh khoản",
    "F-Score", "Altman Z", "tỷ suất cổ tức", "độ rộng thị trường", "khối ngoại",
  ]);

  function resolve(key) {
    if (!key) return null;
    const raw = String(key).trim();
    if (TERMS[raw]) return raw;
    const low = raw.toLowerCase();
    if (ALIAS[low] && TERMS[ALIAS[low]]) return ALIAS[low];
    for (const k of Object.keys(TERMS)) if (k.toLowerCase() === low) return k;
    return null;
  }
  function get(key) {
    const k = resolve(key);
    return k ? Object.assign({ key: k }, TERMS[k]) : null;
  }
  function vi(key) { const t = get(key); return t ? t.vi : String(key || ""); }
  function plain(key) { const t = get(key); return t ? t.plain : ""; }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* Thuộc tính HTML gắn vào bất kỳ thẻ nào để nó trở thành nhãn có chú thích.
     Có tabindex + role=button để bàn phím Tab tới được và Enter/Space mở được. */
  function attrs(key) {
    const t = get(key);
    if (!t) return "";
    return `class="term" data-term="${esc(t.key)}" tabindex="0" role="button" ` +
      `aria-label="${esc(t.vi)} — xem giải thích" aria-expanded="false"`;
  }

  function chip(key, label) {
    const t = get(key);
    const text = label != null ? label : (t ? t.key : key);
    if (!t) return esc(text);
    return `<span ${attrs(t.key)}>${esc(text)}</span>`;
  }

  /* Chú thích HIỆN SẴN — không cần tap. */
  function hint(key) {
    const t = get(key);
    if (!t) return "";
    return `<span class="term-hint">${esc(t.plain)}</span>`;
  }

  /* Nhãn + chú thích hiện sẵn (dùng cho các chỉ số quan trọng trên thẻ số liệu). */
  function label(key, labelText) {
    const t = get(key);
    if (!t) return esc(labelText != null ? labelText : key);
    const head = labelText != null ? labelText : `${t.key} (${t.vi})`;
    return `<span class="term-label"><span class="term-label-name">${esc(head)}</span>${hint(t.key)}</span>`;
  }

  function list() {
    const seen = new Set(); const out = [];
    for (const k of Object.keys(TERMS)) {
      const sig = TERMS[k].vi + "|" + TERMS[k].plain;
      if (seen.has(sig)) continue;           // bỏ bản trùng nghĩa (F-score/F-Score...)
      seen.add(sig);
      out.push({ key: k, vi: TERMS[k].vi, plain: TERMS[k].plain });
    }
    return out.sort((a, b) => a.key.localeCompare(b.key, "vi"));
  }

  /* -------------------------------------------------------------------
     Popover: tap mở, tap ngoài/Esc đóng, aria-describedby + role=tooltip
     ------------------------------------------------------------------- */
  let pop = null, current = null;

  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.className = "term-pop";
    pop.id = "term-pop";
    pop.setAttribute("role", "tooltip");
    pop.hidden = true;
    document.body.appendChild(pop);
    return pop;
  }

  function showPop(target, key) {
    const t = get(key);
    if (!t) return;
    const p = ensurePop();
    p.innerHTML =
      `<button type="button" class="term-pop-x" aria-label="Đóng giải thích">×</button>` +
      `<b>${esc(t.key)}</b> — <span class="term-pop-vi">${esc(t.vi)}</span>` +
      `<div class="term-pop-body">${esc(t.plain)}</div>` +
      `<a class="term-pop-more" href="/kien-thuc">Xem toàn bộ thuật ngữ →</a>`;
    p.hidden = false;
    if (current && current !== target) {
      current.removeAttribute("aria-describedby");
      current.setAttribute("aria-expanded", "false");
    }
    current = target;
    target.setAttribute("aria-describedby", "term-pop");
    target.setAttribute("aria-expanded", "true");

    const r = target.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    const w = Math.min(320, vw - 16);
    p.style.maxWidth = w + "px";
    let left = r.left + window.scrollX;
    left = Math.min(left, window.scrollX + vw - w - 8);
    p.style.top = (r.bottom + window.scrollY + 6) + "px";
    p.style.left = Math.max(8, left) + "px";
  }

  function hidePop() {
    if (pop) pop.hidden = true;
    if (current) {
      current.removeAttribute("aria-describedby");
      current.setAttribute("aria-expanded", "false");
      current = null;
    }
  }

  const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "CODE", "PRE", "A", "BUTTON", "SELECT", "OPTION", "KBD"]);
  const WORDCH = /[A-Za-z0-9À-ỹ]/;
  const seenPerRun = new Set();
  /* Chỉ tự gạch chấm những khóa "an toàn" — cụm dài trước để khớp đúng. */
  const KEYS = Object.keys(TERMS).sort((a, b) => b.length - a.length);

  function scanTextNode(node) {
    const txt = node.nodeValue;
    if (!txt || txt.length < 2 || !/\S/.test(txt)) return;
    for (const key of KEYS) {
      if (seenPerRun.has(key)) continue;
      const idx = txt.indexOf(key);
      if (idx < 0) continue;
      const before = txt[idx - 1], after = txt[idx + key.length];
      if (before && WORDCH.test(before)) continue;
      if (after && WORDCH.test(after)) continue;
      const span = document.createElement("span");
      span.className = "term";
      span.textContent = key;
      span.dataset.term = key;
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      span.setAttribute("aria-label", TERMS[key].vi + " — xem giải thích");
      span.setAttribute("aria-expanded", "false");
      const afterNode = node.splitText(idx);
      afterNode.nodeValue = afterNode.nodeValue.slice(key.length);
      node.parentNode.insertBefore(span, afterNode);
      seenPerRun.add(key);
      return;
    }
  }

  function walk(root) {
    if (!root) return;
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const p = n.parentNode;
        if (!p || SKIP.has(p.nodeName)) return NodeFilter.FILTER_REJECT;
        if (p.classList && (p.classList.contains("term") || p.classList.contains("term-hint") ||
          p.classList.contains("source-tag"))) return NodeFilter.FILTER_REJECT;
        if (p.closest && p.closest(".term-pop, .cmdk-box, input, textarea")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    let n; while ((n = tw.nextNode())) nodes.push(n);
    nodes.forEach(scanTextNode);
  }

  /* Điền chú thích hiện sẵn cho các thẻ khai báo data-term-label / data-term-hint. */
  function fillDeclared(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-term-hint]:not([data-term-done])").forEach((el) => {
      const t = get(el.getAttribute("data-term-hint"));
      if (!t) return;
      el.setAttribute("data-term-done", "1");
      el.insertAdjacentHTML("beforeend", hint(t.key));
    });
    scope.querySelectorAll("[data-term-label]:not([data-term-done])").forEach((el) => {
      const t = get(el.getAttribute("data-term-label"));
      if (!t) return;
      el.setAttribute("data-term-done", "1");
      el.innerHTML = label(t.key, el.textContent.trim() || null);
    });
  }

  function scan(root) {
    seenPerRun.clear();
    const target = root || document.querySelector("main") || document.body;
    try { walk(target); } catch (_) { }
    try { fillDeclared(target.querySelector ? target : document); } catch (_) { }
  }

  /* ---- tương tác: hover (chuột), tap (mobile), bàn phím ---- */
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest && e.target.closest(".term");
    if (t && t.dataset.term) showPop(t, t.dataset.term);
  });
  document.addEventListener("mouseout", (e) => {
    const t = e.target.closest && e.target.closest(".term");
    // giữ popover nếu nó đang được mở bằng tap/bàn phím
    if (t && t === current && t.dataset.tapOpen !== "1") hidePop();
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest && e.target.closest(".term-pop-x")) { hidePop(); return; }
    const t = e.target.closest && e.target.closest(".term");
    if (t && t.dataset.term) {
      if (current === t && pop && !pop.hidden) { delete t.dataset.tapOpen; hidePop(); }
      else { t.dataset.tapOpen = "1"; showPop(t, t.dataset.term); }
      e.stopPropagation();
      return;
    }
    if (!e.target.closest || !e.target.closest(".term-pop")) hidePop();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { hidePop(); return; }
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    const t = e.target && e.target.closest && e.target.closest(".term");
    if (!t || !t.dataset.term) return;
    e.preventDefault();
    if (current === t && pop && !pop.hidden) hidePop();
    else showPop(t, t.dataset.term);
  });
  window.addEventListener("resize", hidePop);

  /* CSS nạp bằng JS để không phải sửa base.html (file dùng chung nhiều nhóm). */
  function ensureCss() {
    const href = "/static/css/f0-term.css";
    if (document.querySelector(`link[href="${href}"]`)) return;
    const l = document.createElement("link");
    l.rel = "stylesheet"; l.href = href;
    document.head.appendChild(l);
  }

  let timer = null;
  function schedule() { clearTimeout(timer); timer = setTimeout(() => scan(), 400); }

  function init() {
    ensureCss();
    scan();
    const mo = new MutationObserver((muts) => {
      for (const m of muts) if (m.addedNodes && m.addedNodes.length) { schedule(); break; }
    });
    const main = document.querySelector("main") || document.body;
    mo.observe(main, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  window.MPTerm = {
    TERMS, ALWAYS_VISIBLE,
    get, vi, plain, attrs, chip, hint, label, list, scan,
    isKeyTerm: (k) => { const t = get(k); return !!t && ALWAYS_VISIBLE.has(t.key); },
  };
})();
