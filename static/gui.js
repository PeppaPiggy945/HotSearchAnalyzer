/**
 * HotSearch Crawler — 管理面板
 * 模块化前端架构
 */
;(function () {
  'use strict';

  /* ================================================================
   *  Constants & State
   * ================================================================ */
  const API = '';
  const CATEGORY_NAMES = {
    social: '社交平台', news: '新闻媒体', finance: '金融财经',
    tech: '科技数码', entertainment: '娱乐视频',
  };
  const PAGE_KEYS = ['dashboard', 'operations', 'platforms', 'user-config', 'outputs', 'reports', 'config-editor', 'logs'];

  const state = {
    currentPage: 'dashboard',
    platformDetails: {},
    platformMgmtData: {},
    outputsCache: {},
    cronTimes: ['08:00'],
    currentConfigKey: '',
    autoRefreshTimer: null,
    apiKey: null,
  };

  /* ================================================================
   *  API Key 管理
   * ================================================================ */
  const ApiKeyManager = {
    STORAGE_KEY: 'hotsearch_api_key',

    init() {
      // 优先从 URL 参数获取
      const urlParams = new URLSearchParams(window.location.search);
      const urlKey = urlParams.get('api_key');
      if (urlKey) {
        this.setKey(urlKey);
        // 清除 URL 中的 api_key 参数（安全考虑）
        urlParams.delete('api_key');
        const newUrl = urlParams.toString()
          ? `${window.location.pathname}?${urlParams.toString()}`
          : window.location.pathname;
        window.history.replaceState({}, '', newUrl);
        return true;
      }
      // 从 localStorage 读取
      const savedKey = localStorage.getItem(this.STORAGE_KEY);
      if (savedKey) {
        state.apiKey = savedKey;
        return true;
      }
      return false;
    },

    setKey(key) {
      state.apiKey = key;
      localStorage.setItem(this.STORAGE_KEY, key);
    },

    clearKey() {
      state.apiKey = null;
      localStorage.removeItem(this.STORAGE_KEY);
    },

    showInputDialog() {
      const existing = document.getElementById('api-key-modal');
      if (existing) return;

      const modal = document.createElement('div');
      modal.id = 'api-key-modal';
      modal.innerHTML = `
        <div class="modal-overlay show" style="z-index:9999">
          <div class="modal" style="max-width:420px">
            <div class="modal-header"><h3>🔐 API 密钥验证</h3></div>
            <div class="modal-body" style="padding:24px">
              <p style="margin-bottom:16px;color:var(--text-sec)">此服务需要 API 密钥才能访问。请输入密钥：</p>
              <input type="password" id="api-key-input" class="form-input" placeholder="请输入 API 密钥" style="width:100%;margin-bottom:12px">
              <label style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text-faint)">
                <input type="checkbox" id="api-key-remember" checked> 记住密钥（存储在本地）
              </label>
              <div id="api-key-error" style="color:var(--red);font-size:13px;margin-top:8px;display:none"></div>
            </div>
            <div class="modal-footer" style="padding:12px 24px 24px;display:flex;gap:8px;justify-content:flex-end">
              <button class="btn" onclick="document.getElementById('api-key-modal').remove()">取消</button>
              <button class="btn btn-primary" id="api-key-submit">确认</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      const input = modal.querySelector('#api-key-input');
      const submitBtn = modal.querySelector('#api-key-submit');
      const errorDiv = modal.querySelector('#api-key-error');

      const doSubmit = async () => {
        const key = input.value.trim();
        if (!key) { errorDiv.textContent = '请输入密钥'; errorDiv.style.display = 'block'; return; }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> 验证中...';

        // 临时设置密钥进行验证
        const originalKey = state.apiKey;
        state.apiKey = key;
        try {
          await http.get('/api/health');
          // 验证成功
          if (modal.querySelector('#api-key-remember').checked) {
            this.setKey(key);
          } else {
            state.apiKey = key; // 仅会话使用
          }
          modal.remove();
          // 刷新当前页面
          Pages.Dashboard.load();
        } catch (e) {
          state.apiKey = originalKey;
          errorDiv.textContent = '密钥无效，请重试';
          errorDiv.style.display = 'block';
          submitBtn.disabled = false;
          submitBtn.textContent = '确认';
        }
      };

      submitBtn.onclick = doSubmit;
      input.onkeydown = (e) => { if (e.key === 'Enter') doSubmit(); };
      input.focus();
    },
  };

  /* ================================================================
   *  API Client — 统一请求封装
   * ================================================================ */
  const http = {
    async request(path, opts = {}) {
      const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
      const serviceKey = state.apiKey;
      if (serviceKey) headers['X-API-Key'] = serviceKey;
      const res = await fetch(API + path, { ...opts, headers });
      const data = await res.json();
      if (!res.ok && !data.success) throw new Error(data.message || `HTTP ${res.status}`);
      return data;
    },
    get(path)    { return this.request(path); },
    post(path, body) { return this.request(path, { method: 'POST', body: JSON.stringify(body || {}) }); },
    put(path, body)  { return this.request(path, { method: 'PUT', body: JSON.stringify(body || {}) }); },
    delete(path) { return this.request(path, { method: 'DELETE' }); },
  };

  /* ================================================================
   *  Utility Helpers
   * ================================================================ */
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const escHtml = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escAttr = s => (s || '').replace(/'/g, "\\'");
  const fmtTime = t => t ? new Date(t).toLocaleString('zh-CN') : '-';

  function debounce(fn, ms = 300) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  }

  /* ================================================================
   *  Toast Notification
   * ================================================================ */
  const Toast = {
    show(msg, type = 'info') {
      const el = document.createElement('div');
      el.className = `toast toast-${type}`;
      el.textContent = msg;
      $('#toast-container').appendChild(el);
      el._timer = setTimeout(() => this.dismiss(el), 4500);
      return el;
    },
    dismiss(el) {
      el.classList.add('fade-out');
      setTimeout(() => el.remove(), 300);
    },
    success(msg) { return this.show(msg, 'success'); },
    error(msg)   { return this.show(msg, 'error'); },
    info(msg)    { return this.show(msg, 'info'); },
  };

  /* ================================================================
   *  Modal Manager
   * ================================================================ */
  const Modal = {
    open(title, contentHtml) {
      $('#modal-title').textContent = title;
      $('#modal-body').innerHTML = contentHtml;
      $('#file-modal').classList.add('show');
    },
    close() { $('#file-modal').classList.remove('show'); },
    loading() { return '<div style="text-align:center;padding:40px;color:var(--text-faint)"><span class="spinner spinner-lg"></span> 加载中...</div>'; },
  };

  /* ================================================================
   *  UI Helpers
   * ================================================================ */
  function setBtnLoading(id, loading) {
    const btn = $(`#${id}`);
    if (!btn) return;
    if (loading) { btn.disabled = true; btn._orig = btn.innerHTML; btn.innerHTML = '<span class="spinner"></span> 执行中...'; }
    else { btn.disabled = false; btn.innerHTML = btn._orig; }
  }

  function showOpStatus(id, type, msg) {
    const el = $(`#${id}`);
    if (!el) return;
    el.className = 'op-status show ' + type;
    el.innerHTML = type === 'running'
      ? `<span class="spinner" style="border-color:var(--accent);border-top-color:transparent"></span> ${msg}`
      : msg;
  }

  function showProgress(id, show) { const el = $(`#${id}`); if (el) el.style.display = show ? 'block' : 'none'; }

  function setEl(id, val) {
    const el = $(`#${id}`); if (!el) return;
    if (el.type === 'checkbox') el.checked = !!val;
    else if (val !== undefined && val !== null) el.value = val;
  }

  function getVal(id) {
    const el = $(`#${id}`); if (!el) return undefined;
    if (el.type === 'checkbox') return el.checked;
    if (el.type === 'number') return parseFloat(el.value) || undefined;
    return el.value || undefined;
  }

  /* ================================================================
   *  Router / Navigation
   * ================================================================ */
  const Router = {
    init() {
      $$('.nav-item').forEach(item => {
        item.addEventListener('click', () => this.goTo(item.dataset.page));
      });
    },
    goTo(page) {
      state.currentPage = page;
      $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
      $$('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page}`));
      // Lazy load page data (arrow wrappers preserve `this` context)
      const loaders = {
        dashboard: () => Pages.Dashboard.load(),
        operations: () => Pages.Operations.load(),
        platforms: () => Pages.Platforms.load(),
        'user-config': () => Pages.UserConfig.load(),
        outputs: () => Pages.Outputs.load(),
        reports: () => Pages.Reports.load(),
        logs: () => Pages.Logs.load(),
      };
      if (loaders[page]) loaders[page]();
    },
  };

  /* ================================================================
   *  Page Modules
   * ================================================================ */
  const Pages = {};

  /* ---- Dashboard ---- */
  Pages.Dashboard = {
    async load() {
      // 逐个请求，避免 Promise.all 吞掉具体错误来源
      let st = {}, platRes = {};
      try {
        await http.get('/api/health');
      } catch (e) {
        $('#st-status').innerHTML = '<span class="badge badge-red">离线</span>';
        Toast.error('/api/health 失败: ' + e.message);
        return;
      }
      try {
        const statusRes = await http.get('/api/status');
        st = statusRes.data || {};
      } catch (e) {
        Toast.error('/api/status 失败: ' + e.message);
      }
      try {
        platRes = await http.get('/api/platforms');
      } catch (e) {
        Toast.error('/api/platforms 失败: ' + e.message);
      }
      try {
        $('#st-status').innerHTML = '<span class="badge badge-green">运行中</span>';
        $('#st-scheduler').innerHTML = st.scheduler_running
          ? '<span class="badge badge-green">运行中</span>'
          : '<span class="badge badge-orange">已停止</span>';
        $('#st-fetches').textContent = st.total_fetches || 0;
        $('#st-analyses').textContent = st.total_analyses || 0;
        $('#st-prompts').textContent = st.total_prompts || 0;
        $('#st-platforms').textContent = platRes.data?.total || 0;
        $('#st-last-fetch').textContent = fmtTime(st.last_fetch_time);
        $('#st-last-analysis').textContent = fmtTime(st.last_analysis_time);
        $('#st-last-prompt').textContent = fmtTime(st.last_prompt_time);
        $('#st-last-insight').textContent = fmtTime(st.last_insight_time);
      } catch (e) { /* ignore render errors */ }
    },
  };

  /* ---- Operations ---- */
  Pages.Operations = {
    async load() {
      this.loadPlatforms();
      this.loadScheduler();
    },

    async loadPlatforms() {
      try {
        const res = await http.get('/api/platforms');
        state.platformDetails = res.data?.details || {};
        const grid = $('#fetch-platform-grid');
        grid.innerHTML = '';
        const groups = {};
        for (const [key, info] of Object.entries(state.platformDetails)) {
          if (!info.enabled) continue;
          const cat = info.category || 'other';
          (groups[cat] ||= []).push({ key, name: info.name || key });
        }
        for (const cat of ['social', 'news', 'finance', 'tech', 'entertainment']) {
          if (!groups[cat]) continue;
          groups[cat].forEach(p => {
            const chip = document.createElement('div');
            chip.className = 'platform-chip';
            chip.dataset.key = p.key;
            chip.innerHTML = `<input type="checkbox" value="${p.key}"><span class="chip-dot"></span><span>${p.name}</span>`;
            chip.addEventListener('click', () => {
              const cb = chip.querySelector('input');
              cb.checked = !cb.checked;
              chip.classList.toggle('checked', cb.checked);
            });
            grid.appendChild(chip);
          });
        }
      } catch (e) { Toast.error('加载平台失败: ' + e.message); }
    },

    toggleAll(checked) {
      $$('#fetch-platform-grid .platform-chip').forEach(chip => {
        chip.querySelector('input').checked = checked;
        chip.classList.toggle('checked', checked);
      });
    },

    async doFetch() {
      setBtnLoading('btn-fetch', true);
      showProgress('fetch-progress', true);
      showOpStatus('fetch-status', 'running', '正在爬取数据，请稍候...');
      try {
        const chips = $$('#fetch-platform-grid .platform-chip.checked');
        const platforms = chips.map(c => c.dataset.key);
        const res = await http.post('/api/fetch', platforms.length ? { platforms } : {});
        const r = res.data;
        const ok = r.failed > 0 ? 'error' : 'success';
        showOpStatus('fetch-status', ok, `完成: 成功 ${r.success}, 失败 ${r.failed}`);
        Toast[ok === 'success' ? 'success' : 'error'](`爬取完成: 成功 ${r.success}, 失败 ${r.failed}`);
      } catch (e) { showOpStatus('fetch-status', 'error', '失败: ' + e.message); Toast.error(e.message); }
      showProgress('fetch-progress', false); setBtnLoading('btn-fetch', false);
    },

    async doAnalyze() {
      setBtnLoading('btn-analyze', true);
      showProgress('analyze-progress', true);
      showOpStatus('analyze-status', 'running', '正在生成分析报告...');
      try {
        await http.post('/api/analyze');
        showOpStatus('analyze-status', 'success', '分析报告生成完成'); Toast.success('完成');
      } catch (e) { showOpStatus('analyze-status', 'error', '失败: ' + e.message); Toast.error(e.message); }
      showProgress('analyze-progress', false); setBtnLoading('btn-analyze', false);
    },

    async doPrompt() {
      setBtnLoading('btn-prompt', true);
      showProgress('prompt-progress', true);
      showOpStatus('prompt-status', 'running', '正在生成 Prompt...');
      try {
        const days = parseInt($('#prompt-days').value) || 10;
        await http.post('/api/prompt', { days });
        showOpStatus('prompt-status', 'success', 'Prompt 生成完成'); Toast.success('完成');
      } catch (e) { showOpStatus('prompt-status', 'error', '失败: ' + e.message); Toast.error(e.message); }
      showProgress('prompt-progress', false); setBtnLoading('btn-prompt', false);
    },

    async doWorkflow() {
      setBtnLoading('btn-workflow', true);
      showProgress('workflow-progress', true);
      showOpStatus('workflow-status', 'running', '正在执行完整工作流，请耐心等待...');
      try {
        await http.post('/api/workflow');
        showOpStatus('workflow-status', 'success', '工作流执行完成');
        Toast.success('完成'); Pages.Dashboard.load();
      } catch (e) { showOpStatus('workflow-status', 'error', '失败: ' + e.message); Toast.error(e.message); }
      showProgress('workflow-progress', false); setBtnLoading('btn-workflow', false);
    },

    /* -- Scheduler -- */
    async loadScheduler() {
      try {
        const res = await http.get('/api/scheduler/config');
        const c = res.data || {};
        $('#sched-type').value = c.type || 'cron';
        state.cronTimes = Array.isArray(c.cron_time) ? [...c.cron_time] : [c.cron_time || '08:00'];
        $('#sched-interval').value = c.interval_minutes || 60;
        this.renderCronTags();
        this.toggleSchedMode();
        this.updateSchedStatus(c.scheduler_running);
      } catch (e) { console.warn('加载调度配置失败:', e); }
    },

    toggleSchedMode() {
      const isCron = $('#sched-type').value === 'cron';
      $('#sched-cron-group').style.display = isCron ? 'block' : 'none';
      $('#sched-interval-group').style.display = isCron ? 'none' : 'block';
    },

    updateSchedStatus(running) {
      const card = $('#sched-status-card');
      const ind = $('#sched-indicator');
      const txt = $('#sched-status-text');
      if (running) { card.className = 'sched-status-card active'; ind.className = 'sched-indicator on'; txt.textContent = '调度器运行中'; }
      else { card.className = 'sched-status-card inactive'; ind.className = 'sched-indicator off'; txt.textContent = '调度器未启动'; }
    },

    renderCronTags() {
      $('#cron-tags').innerHTML = state.cronTimes.map((t, i) =>
        `<span class="cron-tag">${t}<span class="cron-tag-remove" data-idx="${i}">&times;</span></span>`
      ).join('');
      $$('.cron-tag-remove').forEach(el => {
        el.addEventListener('click', (e) => { e.stopPropagation(); this.removeCronTime(parseInt(el.dataset.idx)); });
      });
    },

    addCronTime() {
      const val = $('#cron-new-time').value;
      if (!val || !/^\d{1,2}:\d{2}$/.test(val)) { Toast.error('请输入有效时间 HH:MM'); return; }
      if (state.cronTimes.includes(val)) { Toast.error('该时间已存在'); return; }
      state.cronTimes.push(val); state.cronTimes.sort();
      this.renderCronTags();
    },

    removeCronTime(i) {
      if (state.cronTimes.length <= 1) { Toast.error('至少保留一个时间点'); return; }
      state.cronTimes.splice(i, 1); this.renderCronTags();
    },

    async doSchedulerStart() {
      const type = $('#sched-type').value;
      const config = { type };
      if (type === 'cron') config.cron_time = state.cronTimes;
      else config.interval_minutes = parseInt($('#sched-interval').value) || 60;

      const btn = $('#btn-sched-start');
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 启动中...';
      try {
        await http.put('/api/scheduler/config', config);
        await http.post('/api/scheduler/start');
        this.updateSchedStatus(true);
        const desc = type === 'cron' ? state.cronTimes.join(', ') : config.interval_minutes + '分钟间隔';
        showOpStatus('scheduler-status', 'success', `定时任务已启动 (${desc})`);
        Toast.success('定时任务已启动');
        Pages.Dashboard.load();
      } catch (e) { showOpStatus('scheduler-status', 'error', '启动失败: ' + e.message); Toast.error(e.message); }
      btn.disabled = false; btn.innerHTML = '▶ 应用并启动';
    },

    async doSchedulerStop() {
      setBtnLoading('btn-sched-stop', true);
      try {
        await http.post('/api/scheduler/stop');
        this.updateSchedStatus(false);
        showOpStatus('scheduler-status', 'success', '定时任务已停止'); Toast.success('已停止');
        Pages.Dashboard.load();
      } catch (e) { showOpStatus('scheduler-status', 'error', e.message); Toast.error(e.message); }
      setBtnLoading('btn-sched-stop', false);
    },
  };

  /* ---- Platforms ---- */
  Pages.Platforms = {
    async load() {
      try {
        const res = await http.get('/api/platforms');
        const details = res.data?.details || {};
        state.platformMgmtData = {};
        const groups = {};
        for (const [key, info] of Object.entries(details)) {
          const cat = info.category || 'other';
          (groups[cat] ||= []).push({ key, name: info.name || key, enabled: info.enabled, fetch_items: info.default_fetch_items || 10 });
          state.platformMgmtData[key] = { enabled: info.enabled, fetch_items: info.default_fetch_items || 10 };
        }
        const container = $('#platform-mgmt-list');
        container.innerHTML = '';
        for (const cat of ['social', 'news', 'finance', 'tech', 'entertainment']) {
          if (!groups[cat]) continue;
          const section = document.createElement('div');
          section.innerHTML = `<div class="cat-header"><span class="cat-dot cat-dot-${cat}"></span>${CATEGORY_NAMES[cat] || cat} (${groups[cat].length})</div>`;
          groups[cat].forEach(p => {
            const row = document.createElement('div');
            row.className = 'platform-mgmt-row';
            row.innerHTML = `
              <label class="switch"><input type="checkbox" data-platform="${p.key}" ${p.enabled ? 'checked' : ''}><span class="slider"></span></label>
              <span class="mgmt-name">${p.name}</span>
              <span class="mgmt-items">爬取数: <input type="number" min="1" max="200" value="${p.fetch_items}" data-platform="${p.key}"></span>`;
            row.querySelector('input[type="checkbox"]').addEventListener('change', function () {
              state.platformMgmtData[this.dataset.platform].enabled = this.checked;
            });
            row.querySelector('input[type="number"]').addEventListener('change', function () {
              state.platformMgmtData[this.dataset.platform].fetch_items = parseInt(this.value) || 10;
            });
            section.appendChild(row);
          });
          container.appendChild(section);
        }
      } catch (e) { Toast.error('加载平台失败: ' + e.message); }
    },

    async save() {
      try {
        const enabledMap = Object.fromEntries(Object.entries(state.platformMgmtData).map(([k, v]) => [k, v.enabled]));
        await http.put('/api/platforms/enabled', { platforms: enabledMap });
        const configMap = {};
        for (const [key, val] of Object.entries(state.platformMgmtData)) {
          configMap[key] = { default_fetch_items: val.fetch_items };
        }
        await http.put('/api/platforms/config', { platforms: configMap });
        Toast.success('平台配置已保存');
      } catch (e) { Toast.error('保存失败: ' + e.message); }
    },
  };

  /* ---- User Config ---- */
  Pages.UserConfig = {
    async load() {
      try {
        const res = await http.get('/api/config-files/user_config');
        const c = res.data?.data; if (!c) return;
        setEl('uc-email-enabled', c.notification?.email?.enabled);
        setEl('uc-smtp-server', c.notification?.email?.smtp_server);
        setEl('uc-smtp-port', c.notification?.email?.smtp_port);
        setEl('uc-email-sender', c.notification?.email?.sender);
        setEl('uc-email-password', c.notification?.email?.password);
        setEl('uc-email-recipients', (c.notification?.email?.recipients || []).join(', '));
        setEl('uc-analysis-save', c.analysis?.report?.save_to_file);
        setEl('uc-analysis-dir', c.analysis?.report?.output_dir);
        setEl('uc-llm-enabled', c.llm?.enabled);
        setEl('uc-llm-mode', c.llm?.mode || 'local');
        setEl('uc-llm-device', c.llm?.device || 'auto');
        setEl('uc-llm-model', c.llm?.model_name);
        setEl('uc-llm-api-url', c.llm?.api_base_url);
        setEl('uc-llm-api-key', c.llm?.api_key);
        setEl('uc-llm-api-model', c.llm?.api_model);
        setEl('uc-llm-batch', c.llm?.batch_size);
        setEl('uc-insight-enabled', c.ai_insight?.enabled);
        setEl('uc-insight-api-url', c.ai_insight?.api_base_url);
        setEl('uc-insight-api-key', c.ai_insight?.api_key);
        setEl('uc-insight-days', c.ai_insight?.days);
        setEl('uc-insight-model', c.ai_insight?.api_model);
        setEl('uc-insight-tokens', c.ai_insight?.max_tokens);
        setEl('uc-insight-temp', c.ai_insight?.temperature);
        setEl('uc-insight-timeout', c.ai_insight?.timeout);
        setEl('uc-insight-retries', c.ai_insight?.max_retries);
        setEl('uc-prompt-auto', c.prompt?.auto_generate);
        setEl('uc-prompt-dir', c.prompt?.output_dir);
        setEl('uc-log-level', c.logging?.level || 'INFO');
        setEl('uc-log-console', c.logging?.console);
        setEl('uc-log-file', c.logging?.file);
        setEl('uc-service-port', c.service?.port);
        setEl('uc-service-apikey', c.service?.api_key);
        // 初始化折叠状态
        this.initCollapsibleStates(c);
      } catch (e) { Toast.error('加载配置失败: ' + e.message); }
    },

    initCollapsibleStates(c) {
      // 邮件通知
      this.toggleGroup('email', c.notification?.email?.enabled);
      // 分析配置
      this.toggleGroup('analysis', c.analysis?.report?.save_to_file);
      // LLM 分析
      this.toggleGroup('llm', c.llm?.enabled);
      this.toggleLlmMode(c.llm?.mode || 'local');
      // AI 洞察
      this.toggleGroup('insight', c.ai_insight?.enabled);
      // Prompt
      this.toggleGroup('prompt', c.prompt?.auto_generate);
    },

    toggleGroup(name, enabled) {
      const grp = $(`#${name}-config-group`);
      if (grp) grp.style.display = enabled ? 'block' : 'none';
    },

    toggleLlmMode(m) {
      const localGrp = $('#uc-llm-local-group');
      const apiGrp = $('#uc-llm-api-group');
      if (localGrp) localGrp.style.display = m === 'api' ? 'none' : 'block';
      if (apiGrp) apiGrp.style.display = m === 'api' ? 'block' : 'none';
    },

    async save() {
      const btn = $('#btn-save-user-config');
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 保存中...';
      try {
        const recipients = (getVal('uc-email-recipients') || '').split(/[,，]/).map(s => s.trim()).filter(Boolean);
        const emailEnabled = getVal('uc-email-enabled');
        const config = {
          notification: { enabled: emailEnabled, email: { enabled: emailEnabled, smtp_server: getVal('uc-smtp-server'), smtp_port: getVal('uc-smtp-port'), sender: getVal('uc-email-sender'), password: getVal('uc-email-password'), recipients } },
          analysis: { report: { save_to_file: getVal('uc-analysis-save'), output_dir: getVal('uc-analysis-dir') } },
          llm: { enabled: getVal('uc-llm-enabled'), mode: getVal('uc-llm-mode'), device: getVal('uc-llm-device'), model_name: getVal('uc-llm-model'), api_base_url: getVal('uc-llm-api-url'), api_key: getVal('uc-llm-api-key'), api_model: getVal('uc-llm-api-model'), batch_size: getVal('uc-llm-batch'), max_new_tokens: 10, temperature: 0.1 },
          ai_insight: { enabled: getVal('uc-insight-enabled'), days: getVal('uc-insight-days') || 3, api_base_url: getVal('uc-insight-api-url'), api_key: getVal('uc-insight-api-key'), api_model: getVal('uc-insight-model'), max_tokens: getVal('uc-insight-tokens') || 8000, temperature: getVal('uc-insight-temp') || 0.7, timeout: getVal('uc-insight-timeout') || 300, max_retries: getVal('uc-insight-retries') || 2, report: { output_dir: 'outputs/insight', filename_prefix: 'ai_insight' }, preprocessing: { enabled: true, min_heat_score: 10, max_events_detail: 40, similarity_threshold: 0.55 } },
          prompt: { auto_generate: getVal('uc-prompt-auto'), output_dir: getVal('uc-prompt-dir'), template: 'templates/analysis_prompt.md' },
          logging: { level: getVal('uc-log-level'), console: getVal('uc-log-console'), file: getVal('uc-log-file'), file_path: 'logs/service.log' },
          service: { port: getVal('uc-service-port') || 5000, api_key: getVal('uc-service-apikey') || '' },
          keyword_tracking: { enabled: true, groups: [{ name: '游戏', keywords: [{ name: '王者荣耀', keywords: ['KPL', '王者荣耀'] }] }, { name: '国际局势', keywords: [{ name: '美国', keywords: ['美国', '特朗普'] }, { name: '中东', keywords: ['中东', '伊朗'] }] }], max_matches_per_keyword: 5 },
        };
        const yamlContent = YamlGen.generate(config);
        await http.put('/api/config-files/user_config', { content: yamlContent });
        $('#uc-save-status').innerHTML = '<span style="color:var(--green)">&#10003; 已保存</span>';
        Toast.success('用户配置已保存并生效');
      } catch (e) {
        $('#uc-save-status').innerHTML = `<span style="color:var(--red)">保存失败: ${e.message}</span>`;
        Toast.error('保存失败: ' + e.message);
      }
      btn.disabled = false; btn.innerHTML = '💾 保存用户配置';
    },
  };

  /* ---- File Manager ---- */
  Pages.Outputs = {
    allFiles: [],
    currentFilter: 'all',
    collapsedGroups: new Set(),
    dateRange: 'all',  // 'all', 'today', '7d', '30d', 'custom'
    dateStart: null,
    dateEnd: null,

    async load() {
      try {
        const res = await http.get('/api/outputs');
        const cats = res.data || {};
        this.allFiles = [];
        for (const [catKey, catData] of Object.entries(cats)) {
          for (const f of (catData.files || [])) {
            f.cat = catKey;
            f.catLabel = catData.label || catKey;
            f.catIcon = catData.icon || '';
            f.dateStr = f.modified ? f.modified.split(' ')[0] : 'unknown';
            this.allFiles.push(f);
          }
        }
        this.allFiles.sort((a, b) => (b.modified || '').localeCompare(a.modified || ''));
        this.renderList();
      } catch (e) { Toast.error('加载失败: ' + e.message); }
    },

    setFilter(filter) {
      this.currentFilter = filter;
      $$('#output-filters .filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
      this.renderList();
    },

    setDateRange(range) {
      this.dateRange = range;
      $$('.date-quick-btn').forEach(b => b.classList.toggle('active', b.dataset.range === range));
      if (range !== 'custom') {
        this.dateStart = null;
        this.dateEnd = null;
        $('#date-start').value = '';
        $('#date-end').value = '';
      }
      this.renderList();
    },

    applyCustomDate() {
      const start = $('#date-start').value;
      const end = $('#date-end').value;
      if (start && end && start > end) {
        Toast.error('开始日期不能晚于结束日期');
        return;
      }
      this.dateStart = start || null;
      this.dateEnd = end || null;
      this.dateRange = 'custom';
      $$('.date-quick-btn').forEach(b => b.classList.remove('active'));
      this.renderList();
    },

    clearDate() {
      this.dateRange = 'all';
      this.dateStart = null;
      this.dateEnd = null;
      $('#date-start').value = '';
      $('#date-end').value = '';
      $$('.date-quick-btn').forEach(b => b.classList.toggle('active', b.dataset.range === 'all'));
      this.renderList();
    },

    _filterByDate(files) {
      if (this.dateRange === 'all') return files;
      
      const today = new Date().toISOString().slice(0, 10);
      
      if (this.dateRange === 'today') {
        return files.filter(f => f.dateStr === today);
      }
      
      if (this.dateRange === '7d' || this.dateRange === '30d') {
        const days = this.dateRange === '7d' ? 7 : 30;
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        const cutoffStr = cutoff.toISOString().slice(0, 10);
        return files.filter(f => f.dateStr >= cutoffStr);
      }
      
      if (this.dateRange === 'custom') {
        return files.filter(f => {
          if (this.dateStart && f.dateStr < this.dateStart) return false;
          if (this.dateEnd && f.dateStr > this.dateEnd) return false;
          return true;
        });
      }
      
      return files;
    },

    toggleGroup(date) {
      if (this.collapsedGroups.has(date)) this.collapsedGroups.delete(date);
      else this.collapsedGroups.add(date);
      this.renderList();
    },

    renderList() {
      const container = $('#output-file-list');
      let filtered = this.currentFilter === 'all'
        ? this.allFiles
        : this.allFiles.filter(f => f.cat === this.currentFilter);
      
      // Apply date filter
      filtered = this._filterByDate(filtered);

      if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>暂无文件</p><p style="font-size:12px;margin-top:8px;color:var(--text-faint)">执行爬取或分析后，文件将显示在这里</p></div>';
        return;
      }

      // group by date
      const groups = {};
      for (const f of filtered) { (groups[f.dateStr] ||= []).push(f); }
      const dates = Object.keys(groups).sort((a, b) => b.localeCompare(a));
      const totalSize = filtered.reduce((s, f) => s + (f.size || 0), 0);
      const totalSizeText = totalSize > 1024 * 1024
        ? (totalSize / 1024 / 1024).toFixed(1) + ' MB'
        : (totalSize / 1024).toFixed(1) + ' KB';

      let html = `<div class="output-summary">共 <b>${filtered.length}</b> 个文件，合计 <b>${totalSizeText}</b></div>`;
      for (const date of dates) {
        const files = groups[date];
        const isToday = date === new Date().toISOString().slice(0, 10);
        const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
        const isYesterday = date === yesterday;
        
        // Format date label nicely
        let label;
        if (isToday) {
          label = '今天';
        } else if (isYesterday) {
          label = '昨天';
        } else {
          // Format as "4月15日" or "2025/4/15" for older dates
          const d = new Date(date);
          const now = new Date();
          const sameYear = d.getFullYear() === now.getFullYear();
          if (sameYear) {
            label = `${d.getMonth() + 1}月${d.getDate()}日`;
          } else {
            label = `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
          }
        }
        
        const collapsed = this.collapsedGroups.has(date);
        const arrow = collapsed ? '▸' : '▾';

        html += `<div class="output-date-group"><div class="output-date-header" data-action="toggle-date" data-date="${date}" style="cursor:pointer">
          <span class="date-dot ${isToday ? 'today' : ''}"></span>
          <span class="date-arrow">${arrow}</span>
          <span class="date-label">${label}</span>
          <span class="date-count">${files.length} 个文件</span></div>`;

        if (!collapsed) {
          for (const f of files) {
            const isHtml = f.extension === '.html';
            const isJson = f.cat === 'hotsearch';
            const iconCls = isJson ? 'json' : isHtml ? 'html' : 'md';
            const iconEmoji = isJson ? '📄' : isHtml ? '🌐' : '📝';
            const filePath = f.path || f.name;
            const displayName = escHtml(f.display_name || f.name);
            const preview = f.preview ? escHtml(f.preview).substring(0, 80) : '';

            let badgeHtml;
            if (isJson && f.platform) {
              badgeHtml = `<span class="cat-badge cat-badge-platform">🏷 ${escHtml(f.platform)}</span>`;
            } else {
              badgeHtml = `<span class="cat-badge cat-badge-${f.cat}">${f.catIcon} ${f.catLabel}</span>`;
            }

            html += `<div class="output-file-item">
              <div class="file-icon ${iconCls}">${iconEmoji}</div>
              <div class="file-info">
                <div class="file-name" title="${escAttr(f.name)}">${displayName}</div>
                <div class="file-meta">${badgeHtml}<span>${f.modified}</span><span>${f.size_text}</span></div>
                ${preview ? `<div class="file-preview">${preview}...</div>` : ''}
              </div>
              <div class="file-actions">
                ${isHtml ? `<button class="btn btn-sm fa-btn-open" data-action="open" data-cat="${f.cat}" data-file="${escAttr(filePath)}">打开网页</button>` : ''}
                <button class="btn btn-sm fa-btn-view" data-action="view" data-cat="${f.cat}" data-file="${escAttr(filePath)}">查看</button>
                <button class="btn btn-sm fa-btn-dl" data-action="download" data-cat="${f.cat}" data-file="${escAttr(filePath)}">下载</button>
                <button class="btn btn-sm fa-btn-del" data-action="delete" data-cat="${f.cat}" data-file="${escAttr(filePath)}" data-name="${escAttr(f.name)}">删除</button>
              </div>
            </div>`;
          }
        }
        html += '</div>';
      }
      container.innerHTML = html;

      container.onclick = (e) => {
        const toggle = e.target.closest('[data-action="toggle-date"]');
        if (toggle) { this.toggleGroup(toggle.dataset.date); return; }
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const { action, cat, file, name } = btn.dataset;
        if (action === 'view') this.openFile(cat, file);
        else if (action === 'open') this.openInBrowser(cat, file);
        else if (action === 'download') this.downloadFile(cat, file);
        else if (action === 'delete') this.deleteFile(cat, file, name);
      };
    },

    async openFile(cat, filePath) {
      const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
      Modal.open(filePath.split('/').pop(), Modal.loading());
      try {
        const res = await http.get(`/api/outputs/${cat}/${encodedPath}`);
        const d = res.data;
        if (d.is_html) {
          $('#modal-body').innerHTML = `<iframe srcdoc="${escAttr(d.content)}" style="width:100%;height:70vh;border:none;border-radius:var(--radius)"></iframe>`;
        } else if (d.is_json) {
          try {
            const formatted = JSON.stringify(JSON.parse(d.content), null, 2);
            $('#modal-body').innerHTML = `<pre class="json-preview">${escHtml(formatted)}</pre>`;
          } catch { $('#modal-body').innerHTML = `<pre>${escHtml(d.content)}</pre>`; }
        } else {
          const highlighted = escHtml(d.content)
            .replace(/^(#{1,6} .+)$/gm, '<span style="font-weight:700;color:var(--accent)">$1</span>')
            .replace(/^(\d+\. .+)$/gm, '<span style="font-weight:600">$1</span>')
            .replace(/^(\*{1,3}.+?\*{1,3})$/gm, '<span style="font-weight:600">$1</span>')
            .replace(/^(- .+)$/gm, '<span style="color:var(--text-sec)">$1</span>');
          $('#modal-body').innerHTML = `<pre>${highlighted}</pre>`;
        }
      } catch (e) { $('#modal-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--red)">${escHtml(e.message)}</div>`; }
    },

    async openInBrowser(cat, filePath) {
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        const res = await http.get(`/api/outputs/${cat}/${encodedPath}`);
        const blob = new Blob([res.data?.content || ''], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      } catch (e) { Toast.error('打开失败: ' + e.message); }
    },

    async downloadFile(cat, filePath) {
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        const res = await http.get(`/api/outputs/${cat}/${encodedPath}`);
        const content = res.data?.content || '';
        const ext = (res.data?.name || filePath).split('.').pop();
        const mime = ext === 'html' ? 'text/html' : ext === 'json' ? 'application/json' : 'text/markdown';
        const blob = new Blob([content], { type: `${mime};charset=utf-8` });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filePath.split('/').pop();
        document.body.appendChild(a); a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        Toast.success('已开始下载');
      } catch (e) { Toast.error('下载失败: ' + e.message); }
    },

    async deleteFile(cat, filePath, name) {
      if (!confirm(`确定要删除「${name}」吗？此操作不可撤销。`)) return;
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        await http.delete(`/api/outputs/${cat}/${encodedPath}`);
        Toast.success(`已删除: ${name}`);
        this.load();
      } catch (e) { Toast.error('删除失败: ' + e.message); }
    },

    async cleanup() {
      const keepDays = parseInt($('#cleanup-days').value) || 30;
      const maxFiles = parseInt($('#cleanup-max-files').value) || 80;
      if (!confirm(
        `确定要清理吗？\n` +
        `- 保留最近 ${keepDays} 天的数据\n` +
        `- 密度函数: f(0)=${maxFiles}, f(${keepDays})=0\n` +
        `- 超出密度上限的旧文件将被删除\n\n此操作不可撤销。`
      )) return;
      const btn = document.querySelector('[onclick="doCleanup()"]');
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 清理中...';
      try {
        const res = await http.post('/api/cleanup', {
          keep_days: keepDays,
          max_files_per_platform: maxFiles,
        });
        const deleted = res.data?.deleted_count || 0;
        showOpStatus('cleanup-status', 'success', `清理完成，删除 ${deleted} 个文件`);
        Toast.success(`清理完成，删除 ${deleted} 个文件`);
        this.load();
      } catch (e) {
        showOpStatus('cleanup-status', 'error', '清理失败: ' + e.message);
        Toast.error('清理失败: ' + e.message);
      }
      btn.disabled = false; btn.innerHTML = '🗑️ 执行清理';
    },

    renderDensityCurve() {
      const el = $('#cleanup-curve');
      if (!el) return;
      const keepDays = parseInt($('#cleanup-days').value) || 30;
      const maxFiles = parseInt($('#cleanup-max-files').value) || 80;

      const W = 280, H = 52, padL = 20, padR = 4, padT = 5, padB = 15;
      const plotW = W - padL - padR, plotH = H - padT - padB;

      const f = t => maxFiles * Math.exp(-3.5 * Math.max(0, t / keepDays));

      const toX = t => padL + (t / keepDays) * plotW;
      const toY = v => padT + (1 - Math.max(0, v) / maxFiles) * plotH;

      let svg = `<svg width="100%" viewBox="0 0 ${W} ${H}" style="display:block">`;

      // 面积
      const N = 120;
      let area = `M${toX(0)},${toY(f(0))}`;
      for (let i = 0; i <= N; i++) area += ` L${toX(i / N * keepDays)},${toY(f(i / N * keepDays))}`;
      area += ` L${toX(keepDays)},${toY(0)} Z`;
      svg += `<path d="${area}" fill="var(--accent)" fill-opacity="0.06"/>`;

      // 曲线
      let curve = '';
      for (let i = 0; i <= N; i++) {
        const t = i / N * keepDays;
        curve += (i === 0 ? 'M' : ' L') + `${toX(t).toFixed(1)},${toY(f(t)).toFixed(1)}`;
      }
      svg += `<path d="${curve}" fill="none" stroke="var(--accent)" stroke-width="1.2"/>`;

      // 轴线
      svg += `<line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}" stroke="var(--border-light)" stroke-width="0.6"/>`;
      svg += `<line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="var(--border-light)" stroke-width="0.6"/>`;

      // 起点：圆点在左，数值在右上方
      const sx = toX(0), sy = toY(maxFiles);
      svg += `<circle cx="${sx}" cy="${sy}" r="1.8" fill="var(--accent)"/>`;
      svg += `<text x="${sx + 4}" y="${sy - 2}" font-size="8" fill="var(--accent)" dominant-baseline="baseline">${maxFiles}</text>`;

      // 终点数值
      const endV = Math.max(1, Math.round(f(keepDays)));
      svg += `<text x="${W - padR}" y="${toY(endV) - 1}" font-size="8" fill="var(--text-faint)" text-anchor="end">${endV}</text>`;

      // X轴标签
      svg += `<text x="${padL}" y="${H - 2}" font-size="8" fill="var(--text-faint)">今天</text>`;
      svg += `<text x="${W - padR}" y="${H - 2}" font-size="8" fill="var(--text-faint)" text-anchor="end">${keepDays}天前</text>`;

      svg += '</svg>';
      el.innerHTML = svg;
    },
  };

  /* ---- Reports ---- */
  Pages.Reports = {
    allReports: [],
    dateFilter: 'all',

    async load() {
      try {
        const res = await http.get('/api/outputs');
        const cats = res.data || {};
        const analysisCat = cats.analysis || {};
        // Filter only hotsearch_report HTML files
        this.allReports = (analysisCat.files || [])
          .filter(f => f.name && f.name.startsWith('hotsearch_report') && f.name.endsWith('.html'));
        this.allReports.sort((a, b) => (b.modified || '').localeCompare(a.modified || ''));
        this.render();
      } catch (e) {
        $('#report-container').innerHTML = `<div class="empty-state"><div class="empty-state-icon">❌</div><p>加载失败: ${e.message}</p></div>`;
      }
    },

    filterByDate() {
      this.dateFilter = $('#report-date-filter').value;
      this.render();
    },

    _getDateFilter(reports) {
      if (this.dateFilter === 'all') return reports;
      const today = new Date().toISOString().slice(0, 10);
      if (this.dateFilter === 'today') {
        return reports.filter(r => (r.modified || '').slice(0, 10) === today);
      }
      const days = this.dateFilter === '7d' ? 7 : 30;
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      return reports.filter(r => (r.modified || '').slice(0, 10) >= cutoffStr);
    },

    render() {
      const container = $('#report-container');
      const filtered = this._getDateFilter(this.allReports);

      if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>暂无报告</p><p style="font-size:12px;margin-top:8px;color:var(--text-faint)">执行分析后将生成报告</p></div>';
        return;
      }

      // Group by date
      const groups = {};
      for (const r of filtered) {
        const date = (r.modified || '').slice(0, 10);
        (groups[date] ||= []).push(r);
      }
      const dates = Object.keys(groups).sort((a, b) => b.localeCompare(a));

      let html = '';
      for (const date of dates) {
        const reports = groups[date];
        const isToday = date === new Date().toISOString().slice(0, 10);
        const label = isToday ? '今天' : date;

        html += `<div class="report-date-section">
          <div class="report-date-header">
            <span class="report-date-dot ${isToday ? 'today' : ''}"></span>
            <span class="report-date-label">${label}</span>
            <span class="report-date-count">${reports.length} 份报告</span>
          </div>
          <div class="report-grid">`;

        for (const r of reports) {
          const time = (r.modified || '').slice(11, 16);
          const displayName = r.display_name || r.name.replace(/^hotsearch_report_/, '').replace(/\.html$/, '');
          const filePath = r.path || r.name;
          
          // Extract time from filename for display
          const timeMatch = r.name.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
          const displayTime = timeMatch 
            ? `${timeMatch[1]}-${timeMatch[2]}-${timeMatch[3]} ${timeMatch[4]}:${timeMatch[5]}`
            : r.modified || '';

          // 使用后端提取的元数据
          const topicCount = r.topic_count != null ? r.topic_count : '?';
          const collectTime = r.collect_time || '未知';

          html += `<div class="report-card" data-path="${escAttr(filePath)}" data-time="${escAttr(displayTime)}">
            <div class="report-card-header">
              <span class="report-time-badge">🕐 ${displayTime}</span>
              <span class="report-size-badge">${r.size_text || ''}</span>
            </div>
            <div class="report-card-body">
              <div class="report-icon">📊</div>
              <div class="report-info">
                <div class="report-title">热搜分析报告</div>
                <div class="report-meta">
                  <span class="meta-item">追踪 <strong>${topicCount}</strong> 个话题</span>
                  <span class="meta-sep">·</span>
                  <span class="meta-item" title="${escAttr(collectTime)}">采集于 ${collectTime.split('~')[0].trim().slice(11)}</span>
                </div>
              </div>
            </div>
            <div class="report-card-actions">
              <button class="btn btn-sm report-btn-preview" data-action="preview">👁 预览</button>
              <button class="btn btn-sm report-btn-fullscreen" data-action="fullscreen">⛶ 全屏</button>
              <button class="btn btn-sm report-btn-download" data-action="download">⬇ 下载</button>
            </div>
          </div>`;
        }

        html += '</div></div>';
      }

      container.innerHTML = html;

      // Bind click events
      container.onclick = async (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const card = btn.closest('.report-card');
        const action = btn.dataset.action;
        const path = card.dataset.path;

        if (action === 'preview') {
          this.showPreview(path);
        } else if (action === 'fullscreen') {
          this.openFullscreen(path);
        } else if (action === 'download') {
          this.download(path);
        }
      };
    },

    async showPreview(filePath) {
      Modal.open('报告预览', Modal.loading());
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        const res = await http.get(`/api/outputs/analysis/${encodedPath}`);
        const content = res.data?.content || '';
        // 使用 Blob URL 让 iframe 完整渲染（CSS、主题等）
        const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        $('#modal-body').innerHTML = `<iframe src="${url}" style="width:100%;height:75vh;border:none;border-radius:var(--radius);background:#0f0f1a"></iframe>`;
        // 模态框关闭时释放 URL
        const modal = $('#file-modal');
        const cleanup = () => { URL.revokeObjectURL(url); modal.removeEventListener('click', cleanup); };
        modal.addEventListener('click', (e) => { if (e.target.closest('.modal-close') || e.target === modal) cleanup(); });
      } catch (e) {
        $('#modal-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--red)">${escHtml(e.message)}</div>`;
      }
    },

    async openFullscreen(filePath) {
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        const res = await http.get(`/api/outputs/analysis/${encodedPath}`);
        const blob = new Blob([res.data?.content || ''], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      } catch (e) {
        Toast.error('打开失败: ' + e.message);
      }
    },

    async download(filePath) {
      try {
        const encodedPath = filePath.split('/').map(encodeURIComponent).join('/');
        const res = await http.get(`/api/outputs/analysis/${encodedPath}`);
        const content = res.data?.content || '';
        const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath.split('/').pop();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        Toast.success('已开始下载');
      } catch (e) {
        Toast.error('下载失败: ' + e.message);
      }
    },
  };

  /* ---- Config Editor ---- */
  Pages.ConfigEditor = {
    async loadFile() {
      const key = $('#config-file-select').value;
      if (!key) { $('#config-editor-wrap').style.display = 'none'; return; }
      try {
        const res = await http.get(`/api/config-files/${key}`);
        $('#config-editor').value = res.data?.raw || '';
        const sz = res.data?.raw ? (res.data.raw.length / 1024).toFixed(1) + ' KB' : '0 B';
        $('#config-filename-display').textContent = `已加载 (${sz})`;
        $('#config-status').textContent = '';
        $('#config-status').className = '';
        $('#config-editor-wrap').style.display = 'block';
        state.currentConfigKey = key;
      } catch (e) { Toast.error('加载失败: ' + e.message); }
    },

    async saveFile() {
      if (!state.currentConfigKey) return;
      const content = $('#config-editor').value;
      const statusEl = $('#config-status');
      try {
        await http.put(`/api/config-files/${state.currentConfigKey}`, { content });
        statusEl.textContent = '已保存于 ' + new Date().toLocaleTimeString('zh-CN');
        statusEl.className = 'config-hint ok';
        Toast.success('配置已保存');
      } catch (e) { statusEl.textContent = '保存失败: ' + e.message; statusEl.className = 'config-hint err'; Toast.error(e.message); }
    },
  };

  /* ---- Logs ---- */
  Pages.Logs = {
    async load() {
      const lines = parseInt($('#log-lines').value) || 500;
      try {
        const res = await http.get(`/api/logs?lines=${lines}`);
        $('#log-file-info').textContent = `文件: ${res.data?.log_file || 'N/A'} | 共 ${res.data?.total_lines || 0} 行`;
        const viewer = $('#log-viewer');
        if (res.data?.hint) { viewer.innerHTML = `<span style="color:#f7c948">${escHtml(res.data.hint)}</span>`; return; }
        const text = res.data?.lines || '';
        const highlighted = escHtml(text)
          .replace(/(ERROR|CRITICAL)/g, '<span class="log-error">$1</span>')
          .replace(/(WARNING|WARN)/g, '<span class="log-warn">$1</span>')
          .replace(/(INFO)/g, '<span class="log-info">$1</span>')
          .replace(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/g, '<span style="color:#86909c">$1</span>');
        viewer.innerHTML = highlighted || '<span style="color:#86909c">(无日志内容)</span>';
      } catch (e) {
        $('#log-viewer').innerHTML = `<span class="log-error">${escHtml(e.message)}</span>`;
        Toast.error('加载日志失败: ' + e.message);
      }
    },

    scrollToBottom() { const el = $('#log-viewer'); if (el) el.scrollTop = el.scrollHeight; },

    async clearLogs() {
      if (!confirm('确定要清除所有日志文件吗？此操作不可撤销。')) return;
      const btn = document.querySelector('[onclick="clearLogs()"]');
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 清除中...';
      try {
        const res = await http.delete('/api/logs');
        const cleared = res.data?.cleared || [];
        Toast.success(`已清空 ${cleared.length} 个日志文件`);
        this.load();
      } catch (e) {
        Toast.error('清除失败: ' + e.message);
      }
      btn.disabled = false; btn.innerHTML = '🗑 清除日志';
    },
  };

  /* ================================================================
   *  YAML Generator (for user config save)
   * ================================================================ */
  const YamlGen = {
    SECTION_MAP: { notification: '通知配置', analysis: '分析配置', llm: 'LLM 分析配置', ai_insight: 'AI 洞察报告配置', prompt: 'Prompt 配置', logging: '日志配置', service: '服务配置', keyword_tracking: '关键词追踪配置', crawler: '爬虫调度配置' },
    generate(obj) {
      const lines = ['# 用户配置文件', '# 由 GUI 管理面板自动生成', ''];
      for (const [key, val] of Object.entries(obj)) {
        if (val === undefined || val === null) continue;
        lines.push(`# ==================== ${this.SECTION_MAP[key] || key} ====================`);
        lines.push(this.dump(key, val, 0));
        lines.push('');
      }
      return lines.join('\n');
    },
    dump(key, val, indent) {
      const pad = '  '.repeat(indent);
      if (val === undefined || val === null) return '';
      if (typeof val === 'boolean') return pad + key + ': ' + val;
      if (typeof val === 'number') return pad + key + ': ' + val;
      if (typeof val === 'string') return pad + key + ": '" + val.replace(/'/g, "''") + "'";
      if (Array.isArray(val)) {
        if (val.length === 0) return pad + key + ': []';
        if (typeof val[0] === 'string') return pad + key + ': [' + val.map(v => `'${v}'`).join(', ') + ']';
        let out = pad + key + ':\n';
        val.forEach(item => {
          if (typeof item === 'string') { out += pad + "  - '" + item + "'\n"; return; }
          out += pad + "  - name: '" + (item.name || '') + "'\n";
          for (const [k, v] of Object.entries(item)) {
            if (k === 'name') continue;
            if (Array.isArray(v)) out += pad + '    ' + k + ': [' + v.map(x => `'${x}'`).join(', ') + ']\n';
            else if (typeof v === 'object') out += pad + '    ' + k + ':\n' + pad + '      name: \'' + (v.name || '') + '\'\n' + pad + '      keywords: [' + (v.keywords || []).map(x => `'${x}'`).join(', ') + ']\n';
            else out += pad + '    ' + k + ': ' + (typeof v === 'boolean' ? v : `'${v}'`) + '\n';
          }
        });
        return out.trimEnd();
      }
      if (typeof val === 'object') {
        let out = pad + key + ':\n';
        for (const [k, v] of Object.entries(val)) out += this.dump(k, v, indent + 1) + '\n';
        return out.trimEnd();
      }
      return pad + key + ': ' + val;
    },
  };

  /* ================================================================
   *  Theme (Dark Mode)
   * ================================================================ */
  const Theme = {
    init() {
      const saved = localStorage.getItem('hsc-theme');
      if (saved === 'dark') this.apply('dark');
      const btn = $('#theme-toggle');
      if (btn) btn.addEventListener('click', () => this.toggle());
    },
    toggle() {
      const current = document.documentElement.getAttribute('data-theme');
      this.apply(current === 'dark' ? 'light' : 'dark');
    },
    apply(mode) {
      document.documentElement.setAttribute('data-theme', mode);
      localStorage.setItem('hsc-theme', mode);
      const btn = $('#theme-toggle');
      if (btn) btn.textContent = mode === 'dark' ? '☀️' : '🌙';
    },
  };

  /* ================================================================
   *  Keyboard Shortcuts
   * ================================================================ */
  const Shortcuts = {
    init() {
      document.addEventListener('keydown', (e) => {
        // Ignore when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
          if (e.key === 'Escape') { e.target.blur(); return; }
          return;
        }
        if (e.key === 'Escape') { Modal.close(); return; }
        if (e.ctrlKey || e.metaKey) {
          const idx = parseInt(e.key);
          if (idx >= 1 && idx <= PAGE_KEYS.length) {
            e.preventDefault();
            Router.goTo(PAGE_KEYS[idx - 1]);
          }
        }
      });
    },
  };

  /* ================================================================
   *  Sidebar Toggle (mobile)
   * ================================================================ */
  const Sidebar = {
    init() {
      const toggle = $('#sidebar-toggle');
      if (toggle) toggle.addEventListener('click', () => this.mobileToggle());
      const collapseBtn = $('#sidebar-collapse');
      if (collapseBtn) collapseBtn.addEventListener('click', () => this.collapseToggle());
    },
    mobileToggle() {
      $('#sidebar').classList.toggle('mobile-open');
    },
    collapseToggle() {
      $('#sidebar').classList.toggle('collapsed');
    },
  };

  /* ================================================================
   *  Event Bindings
   * ================================================================ */
  function bindEvents() {
    // Output filter buttons
    $$('#output-filters .filter-btn').forEach(btn => {
      btn.addEventListener('click', () => Pages.Outputs.setFilter(btn.dataset.filter));
    });

    // Date quick filter buttons
    $$('.date-quick-btn').forEach(btn => {
      btn.addEventListener('click', () => Pages.Outputs.setDateRange(btn.dataset.range));
    });

    // Global button handlers (delegated via onclick attributes in HTML)
    // Using window to keep backward compatibility
    window.toggleAllPlatforms = (checked) => Pages.Operations.toggleAll(checked);
    window.doFetch = () => Pages.Operations.doFetch();
    window.doAnalyze = () => Pages.Operations.doAnalyze();
    window.doPrompt = () => Pages.Operations.doPrompt();
    window.doWorkflow = () => Pages.Operations.doWorkflow();
    window.addCronTime = () => Pages.Operations.addCronTime();
    window.doSchedulerStart = () => Pages.Operations.doSchedulerStart();
    window.doScheduler = (action) => action === 'stop' ? Pages.Operations.doSchedulerStop() : null;
    window.savePlatforms = () => Pages.Platforms.save();
    window.saveUserConfig = () => Pages.UserConfig.save();
    window.loadConfigFile = () => Pages.ConfigEditor.loadFile();
    window.saveConfigFile = () => Pages.ConfigEditor.saveFile();
    window.loadLogs = () => Pages.Logs.load();
    window.autoScrollLogs = () => Pages.Logs.scrollToBottom();
    window.clearLogs = () => Pages.Logs.clearLogs();
    window.loadOutputs = () => Pages.Outputs.load();
    window.loadDashboard = () => Pages.Dashboard.load();
    window.doCleanup = () => Pages.Outputs.cleanup();
    window.closeModal = () => Modal.close();
    window.applyDateFilter = () => Pages.Outputs.applyCustomDate();
    window.clearDateFilter = () => Pages.Outputs.clearDate();
    window.loadReports = () => Pages.Reports.load();
    window.filterReports = () => Pages.Reports.filterByDate();
    // 配置折叠切换
    window.toggleConfigGroup = (name) => {
      const checkbox = $(`#uc-${name === 'email' ? 'email-enabled' : name === 'analysis' ? 'analysis-save' : name === 'llm' ? 'llm-enabled' : name === 'insight' ? 'insight-enabled' : 'prompt-auto'}`);
      const enabled = checkbox?.checked;
      Pages.UserConfig.toggleGroup(name, enabled);
    };

    // LLM mode toggle
    window.toggleLLMMode = () => {
      const mode = $('#uc-llm-mode')?.value || 'local';
      Pages.UserConfig.toggleLlmMode(mode);
    };
    $('#uc-llm-mode')?.addEventListener('change', toggleLLMMode);

    // 更换 API 密钥
    window.changeApiKey = () => {
      ApiKeyManager.clearKey();
      ApiKeyManager.showInputDialog();
    };

    // Cleanup density curve preview
    const curveInputs = ['#cleanup-days', '#cleanup-max-files'];
    curveInputs.forEach(sel => {
      const el = $(sel);
      if (el) el.addEventListener('input', () => Pages.Outputs.renderDensityCurve());
    });

    // Modal overlay close
    $('#file-modal')?.addEventListener('click', function (e) { if (e.target === this) Modal.close(); });

    // Scheduler type change
    $('#sched-type')?.addEventListener('change', () => Pages.Operations.toggleSchedMode());
  }

  /* ================================================================
   *  Init
   * ================================================================ */
  function init() {
    Theme.init();
    // 初始化 API 密钥
    const hasKey = ApiKeyManager.init();
    Router.init();
    Sidebar.init();
    Shortcuts.init();
    bindEvents();
    Pages.Outputs.renderDensityCurve();
    // 如果没有密钥，显示输入框；否则加载仪表盘
    if (!hasKey) {
      ApiKeyManager.showInputDialog();
    } else {
      Pages.Dashboard.load();
    }
  }

  // Boot
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

})();
