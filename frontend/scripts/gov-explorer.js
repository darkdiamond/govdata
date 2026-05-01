// gov-explorer.js — in-page search + paginated table over a CKAN
// (data.gov.il) datastore_search resource. Pre-loaded by the Nuxt
// dataset shell (see frontend/utils/dataset-libs.ts), so agent-emitted
// content.html can call window.GovExplorer.create({...}) without any
// <script src=>.
//
// CORS: data.gov.il responds with permissive CORS for plain GETs to
// /api/3/action/. We do not set custom headers and do not send
// credentials, so no preflight is issued.
//
// Safety: row rendering is structured — cells are plain descriptors
// ({text, dir, class, badge, align}) and the lib only calls
// createElement/textContent. There is no innerHTML/insertAdjacentHTML
// path that an agent's renderRow can route data through, so untrusted
// CKAN field values cannot inject markup.
;(function () {
  'use strict';

  function ensureStyles() {
    if (document.getElementById('gov-explorer-styles')) return;
    var style = document.createElement('style');
    style.id = 'gov-explorer-styles';
    style.textContent =
      '.gov-explorer-tbl-wrap{overflow-x:auto}' +
      'table.gov-explorer-tbl{width:100%;border-collapse:collapse;font-size:.85rem;font-family:Rubik,sans-serif}' +
      'table.gov-explorer-tbl th{background:#f1f7ff;color:#0b3668;padding:.5rem .75rem;border-bottom:2px solid #c3cfe7;font-weight:600;text-align:right;white-space:nowrap}' +
      'table.gov-explorer-tbl td{padding:.45rem .75rem;border-bottom:1px solid #eef2fa;color:#0c3058;vertical-align:top}' +
      'table.gov-explorer-tbl tbody tr:hover td{background:#f1f7ff}' +
      '.gov-explorer-search{border:1px solid #c3cfe7;border-radius:.3rem;padding:.4rem .75rem;font-family:Rubik,sans-serif;font-size:.9rem;color:#0c3058;width:100%;max-width:420px;background:#fff}' +
      '.gov-explorer-search:focus{outline:2px solid #0068f5;outline-offset:1px}' +
      '.gov-explorer-hint{font-size:.8rem;color:#6c757d;margin-top:.5rem;text-align:right}' +
      '.gov-explorer-more{margin-top:.75rem;padding:.4rem 1rem;background:#fff;color:#0068f5;border:1px solid #0068f5;border-radius:.5rem;font-family:Rubik,sans-serif;font-size:.85rem;cursor:pointer}' +
      '.gov-explorer-more:hover{background:#f1f7ff}' +
      '.gov-explorer-more[disabled]{opacity:.5;cursor:not-allowed}' +
      '.gov-explorer-state{padding:1.5rem;text-align:center;color:#6c757d;font-size:.9rem}' +
      '.gov-explorer-state[data-kind=error]{color:#dc3545}' +
      '.gov-explorer-skel{display:block;height:1rem;margin:.5rem 0;background:linear-gradient(90deg,#f1f7ff 0%,#e7eef9 50%,#f1f7ff 100%);background-size:200% 100%;border-radius:.2rem;animation:gov-explorer-pulse 1.4s ease-in-out infinite}' +
      '.gov-explorer-badge{border-radius:50rem;padding:.15rem .6rem;font-size:.75rem;font-weight:600;display:inline-block}' +
      '.gov-explorer-badge--ok{background:#d1e7dd;color:#0a3622}' +
      '.gov-explorer-badge--warn{background:#fff3cd;color:#664d03}' +
      '.gov-explorer-badge--mut{background:#e9ecef;color:#495057}' +
      '.gov-explorer-badge--info{background:#cff4fc;color:#055160}' +
      '.gov-explorer-badge--danger{background:#f8d7da;color:#58151c}' +
      '@keyframes gov-explorer-pulse{0%{background-position:100% 0}100%{background-position:-100% 0}}';
    document.head.appendChild(style);
  }

  function resolveEl(target) {
    if (typeof target === 'string') return document.querySelector(target);
    if (target instanceof Element) return target;
    return null;
  }

  function debounce(fn, wait) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function formatNumHe(n) {
    try { return Number(n).toLocaleString('he-IL'); }
    catch (_) { return String(n); }
  }

  function makeCellNode(descriptor) {
    var td = document.createElement('td');
    if (descriptor == null) { td.textContent = ''; return td; }
    var d = (typeof descriptor === 'object') ? descriptor : { text: descriptor };
    if (d.dir === 'ltr' || d.dir === 'rtl') td.setAttribute('dir', d.dir);
    if (d.align === 'right' || d.align === 'left' || d.align === 'center') td.style.textAlign = d.align;
    if (d.class) td.className = String(d.class);
    var text = d.text == null ? '' : String(d.text);
    if (d.badge) {
      var span = document.createElement('span');
      span.className = 'gov-explorer-badge gov-explorer-badge--' + d.badge;
      span.textContent = text;
      td.appendChild(span);
    } else {
      td.textContent = text;
    }
    return td;
  }

  function defaultRowDescriptor(record, fields) {
    return fields.map(function (f) { return { text: record[f] }; });
  }

  async function fetchPage(opts) {
    var params = new URLSearchParams();
    params.set('resource_id', opts.resourceId);
    if (opts.fields && opts.fields.length) params.set('fields', opts.fields.join(','));
    if (opts.sort) params.set('sort', opts.sort);
    params.set('limit', String(opts.limit));
    if (opts.offset) params.set('offset', String(opts.offset));
    params.set('include_total', 'true');
    var url = 'https://data.gov.il/api/3/action/datastore_search?' + params.toString();
    var res = await fetch(url);
    if (!res.ok) throw new Error('http ' + res.status);
    var data = await res.json();
    if (!data || !data.success || !data.result) throw new Error('ckan reject');
    return { records: data.result.records || [], total: data.result.total || 0 };
  }

  function create(config) {
    if (!config) { console.warn('[GovExplorer] missing config'); return; }
    var container = resolveEl(config.container);
    if (!container) { console.warn('[GovExplorer] container not found', config.container); return; }
    if (!config.resourceId) { console.warn('[GovExplorer] resourceId is required'); return; }

    var fields = Array.isArray(config.fields) ? config.fields.slice() : [];
    var headers = (Array.isArray(config.headers) && config.headers.length === fields.length)
      ? config.headers.slice() : fields.slice();
    var searchFields = (Array.isArray(config.searchFields) && config.searchFields.length)
      ? config.searchFields.slice() : fields.slice();
    var pageSize = Math.max(1, Number(config.pageSize) || 50);
    var totalCap = Math.max(pageSize, Number(config.totalCap) || 5000);
    var sort = config.sort || '_id asc';
    var renderRow = typeof config.renderRow === 'function'
      ? config.renderRow
      : function (r) { return defaultRowDescriptor(r, fields); };
    var emptyMessage = config.emptyMessage || 'לא נמצאו רשומות תואמות.';

    ensureStyles();

    var allRows = [];
    var visibleCount = pageSize;
    var serverTotal = null;
    var query = '';

    clearChildren(container);

    var wrap = document.createElement('div');
    wrap.className = 'gov-explorer-tbl-wrap';
    var table = document.createElement('table');
    table.className = 'gov-explorer-tbl';
    var thead = document.createElement('thead');
    var headTr = document.createElement('tr');
    headers.forEach(function (h) {
      var th = document.createElement('th');
      th.textContent = String(h);
      headTr.appendChild(th);
    });
    thead.appendChild(headTr);
    var tbody = document.createElement('tbody');
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);

    var hint = document.createElement('p');
    hint.className = 'gov-explorer-hint';

    var moreBtn = document.createElement('button');
    moreBtn.className = 'gov-explorer-more';
    moreBtn.type = 'button';
    moreBtn.textContent = 'הצג עוד';
    moreBtn.style.display = 'none';

    container.appendChild(wrap);
    container.appendChild(moreBtn);
    container.appendChild(hint);

    function setStateRow(kind, message) {
      clearChildren(tbody);
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.colSpan = headers.length || 1;
      var box = document.createElement('div');
      box.className = 'gov-explorer-state';
      box.setAttribute('data-kind', kind);
      box.textContent = message;
      td.appendChild(box);
      tr.appendChild(td);
      tbody.appendChild(tr);
      moreBtn.style.display = 'none';
    }

    function showSkeleton() {
      clearChildren(tbody);
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.colSpan = headers.length || 1;
      [100, 80, 90].forEach(function (w) {
        var s = document.createElement('span');
        s.className = 'gov-explorer-skel';
        s.style.width = w + '%';
        td.appendChild(s);
      });
      tr.appendChild(td);
      tbody.appendChild(tr);
      moreBtn.style.display = 'none';
      hint.textContent = 'טוען נתונים...';
    }

    function applyFilter() {
      if (!query) return allRows;
      var q = query.toLowerCase();
      return allRows.filter(function (r) {
        for (var i = 0; i < searchFields.length; i++) {
          var v = r[searchFields[i]];
          if (v != null && String(v).toLowerCase().indexOf(q) !== -1) return true;
        }
        return false;
      });
    }

    function buildHint(matched, showing) {
      var loaded = allRows.length;
      var total = serverTotal != null ? serverTotal : loaded;
      var capped = loaded >= totalCap && total > totalCap;
      var parts;
      if (query) {
        parts = ['מוצגות ' + formatNumHe(showing) + ' מתוך ' + formatNumHe(matched) + ' רשומות תואמות'];
        if (loaded < total) parts.push('— החיפוש מבוצע על ' + formatNumHe(loaded) + ' רשומות שכבר נטענו (סה"כ במאגר: ' + formatNumHe(total) + ')');
      } else {
        parts = ['מוצגות ' + formatNumHe(showing) + ' מתוך ' + formatNumHe(total) + ' רשומות'];
      }
      if (capped) parts.push('— הוגבל ל-' + formatNumHe(totalCap) + '. להורדת הרשימה המלאה השתמש/י בקישור ה-CSV.');
      return parts.join(' ');
    }

    function render() {
      var filtered = applyFilter();
      var matched = filtered.length;
      if (matched === 0) { setStateRow('empty', emptyMessage); hint.textContent = ''; return; }

      var slice = filtered.slice(0, visibleCount);
      var frag = document.createDocumentFragment();
      for (var i = 0; i < slice.length; i++) {
        var record = slice[i];
        var descriptors;
        try { descriptors = renderRow(record); }
        catch (e) { console.warn('[GovExplorer] renderRow threw', e); continue; }
        if (!Array.isArray(descriptors)) {
          console.warn('[GovExplorer] renderRow must return an array of cell descriptors');
          continue;
        }
        var tr = document.createElement('tr');
        for (var c = 0; c < descriptors.length; c++) tr.appendChild(makeCellNode(descriptors[c]));
        frag.appendChild(tr);
      }
      clearChildren(tbody);
      tbody.appendChild(frag);
      hint.textContent = buildHint(matched, slice.length);

      var loaded = allRows.length;
      var serverHasMore = serverTotal != null && loaded < Math.min(serverTotal, totalCap);
      var clientHasMore = matched > slice.length;
      if (clientHasMore || (!query && serverHasMore)) {
        moreBtn.style.display = '';
        moreBtn.disabled = false;
        moreBtn.textContent = 'הצג עוד';
      } else {
        moreBtn.style.display = 'none';
      }
    }

    async function loadInitial() {
      showSkeleton();
      try {
        var res = await fetchPage({
          resourceId: config.resourceId,
          fields: fields,
          sort: sort,
          limit: Math.min(totalCap, Math.max(pageSize * 4, 200)),
          offset: 0,
        });
        allRows = res.records;
        serverTotal = res.total;
        visibleCount = pageSize;
        render();
      } catch (err) {
        console.warn('[GovExplorer] fetch failed', err);
        setStateRow('error', 'לא ניתן לטעון את הרשימה כעת. להורדה ישירה השתמש/י בקישור ה-CSV בכרטיס "קבצים להורדה".');
        hint.textContent = '';
      }
    }

    async function loadMoreFromServer() {
      var cap = Math.min(serverTotal || 0, totalCap);
      if (allRows.length >= cap) return;
      moreBtn.disabled = true;
      moreBtn.textContent = 'טוען...';
      try {
        var batch = Math.min(cap - allRows.length, Math.max(pageSize * 4, 200));
        var res = await fetchPage({
          resourceId: config.resourceId,
          fields: fields,
          sort: sort,
          limit: batch,
          offset: allRows.length,
        });
        allRows = allRows.concat(res.records);
        visibleCount += pageSize;
        render();
      } catch (err) {
        console.warn('[GovExplorer] loadMore failed', err);
        moreBtn.disabled = false;
        moreBtn.textContent = 'הצג עוד';
      }
    }

    moreBtn.addEventListener('click', function () {
      var filtered = applyFilter();
      if (filtered.length > visibleCount) {
        visibleCount += pageSize;
        render();
        return;
      }
      loadMoreFromServer();
    });

    var searchEl = config.searchInput ? resolveEl(config.searchInput) : null;
    if (searchEl) {
      var onInput = debounce(function () {
        query = (searchEl.value || '').trim();
        visibleCount = pageSize;
        render();
      }, 150);
      searchEl.addEventListener('input', onInput);
    }

    loadInitial();
  }

  window.GovExplorer = { create: create };
})();
