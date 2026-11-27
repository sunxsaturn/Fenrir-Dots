'use strict';

const $ = (id) => document.getElementById(id);
const state = { view: 'chat', conversationId: null, models: [], chats: [], sending: false, weather: null, wallpaperSchedule: null, wallpaperSyncPlan: null, publicLibraryPlan: null, publicLibraryAudit: null };
const views = ['chat', 'weather', 'system', 'doctor', 'wallpapers', 'history', 'settings'];

async function api(path, options = {}) {
  const response = await fetch(path, { cache: 'no-store', ...options, headers: { ...(options.headers || {}), ...(options.body ? { 'Content-Type': 'application/json' } : {}) } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function toast(message) {
  const target = $('toast');
  target.textContent = message;
  target.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => target.classList.remove('show'), 3200);
}

function showView(name) {
  if (!views.includes(name)) return;
  state.view = name;
  document.querySelectorAll('[data-view]').forEach((button) => button.classList.toggle('active', button.dataset.view === name));
  views.forEach((view) => {
    const element = $(`${view}-view`);
    if (element) element.classList.toggle('hidden', view !== name);
  });
  const titles = { chat: ['YOUR WORKSPACE', 'Chat'], weather: ['YOUR LOCAL FORECAST', 'Weather'], system: ['LIVE HARDWARE TELEMETRY', 'System'], doctor: ['DIAGNOSTICS · UPDATES · RECOVERY', 'Fenrir Doctor'], wallpapers: ['RIGHTS-AWARE WALLPAPER LIBRARY', 'Wallpapers'], history: ['YOUR PRIVATE ARCHIVE', 'History'], settings: ['PERSONALIZE FENRIR DOCTOR', 'Settings'] };
  $('view-eyebrow').textContent = titles[name][0];
  $('view-title').textContent = titles[name][1];
  if (name === 'weather') loadWeather(true);
  if (name === 'system') loadSystem(true);
  if (name === 'doctor') loadDoctor(true);
  if (name === 'wallpapers') loadWallpapers(true);
  if (name === 'history') renderHistory();
  if (name === 'settings') loadSettings();
}

function createMessage(role, content, model = '') {
  const wrapper = document.createElement('article');
  wrapper.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'YOU' : (model ? `FENRIR DOCTOR · ${model}` : 'FENRIR DOCTOR');
  const body = document.createElement('p');
  body.className = 'message-body';
  body.textContent = content;
  wrapper.append(label, body);
  return wrapper;
}

function renderEmptyChat() {
  const messages = $('messages');
  messages.replaceChildren();
  const welcome = document.createElement('div');
  welcome.className = 'welcome';
  const orb = document.createElement('div'); orb.className = 'welcome-orb'; orb.textContent = '✧';
  const kicker = document.createElement('div'); kicker.className = 'eyebrow'; kicker.textContent = 'A QUIET SPACE TO THINK';
  const heading = document.createElement('h2'); heading.textContent = 'Hello. I\'m Fenrir Doctor.';
  const description = document.createElement('p'); description.textContent = 'Your private assistant, running locally on your own machine. Let\'s work through something.';
  const suggestions = document.createElement('div'); suggestions.className = 'suggestions';
  [['Plan a project', 'Help me plan a project step by step.'], ['Learn something', 'Explain a difficult concept clearly, with examples.'], ['Solve a problem', 'Help me debug this problem. Ask for any missing details first.']].forEach(([label, prompt]) => {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label; button.dataset.prompt = prompt; suggestions.append(button);
  });
  welcome.append(orb, kicker, heading, description, suggestions);
  messages.append(welcome);
}

function appendConversation(messages) {
  const target = $('messages');
  target.replaceChildren();
  if (!messages.length) return renderEmptyChat();
  for (const message of messages) target.append(createMessage(message.role, message.content, message.model || ''));
  target.scrollTop = target.scrollHeight;
}

async function refreshChats() {
  try {
    const data = await api('/api/chats');
    state.chats = data.chats || [];
    renderChatList();
    renderRecentActivity();
  } catch (error) { console.warn('Could not refresh conversation list:', error); }
}

function addChatButton(chat, container, compact = false) {
  const button = document.createElement('button');
  button.className = compact ? 'chat-item' : 'history-item';
  button.type = 'button';
  const title = document.createElement('strong'); title.textContent = chat.title || 'Untitled conversation';
  const date = document.createElement('small'); date.textContent = new Date(`${chat.updated_at || chat.created_at}Z`).toLocaleString();
  button.append(title, date);
  button.addEventListener('click', () => loadConversation(chat.id));
  container.append(button);
}

function renderChatList() {
  const target = $('chat-list'); target.replaceChildren();
  if (!state.chats.length) {
    const empty = document.createElement('p'); empty.className = 'empty-list'; empty.textContent = 'Your conversations will appear here.'; target.append(empty); return;
  }
  state.chats.slice(0, 12).forEach((chat) => addChatButton(chat, target, true));
}

function renderRecentActivity() {
  const target = $('recent-activity'); target.replaceChildren();
  if (!state.chats.length) {
    const empty = document.createElement('p'); empty.className = 'empty-list'; empty.textContent = 'Start a conversation to see activity here.'; target.append(empty); return;
  }
  state.chats.slice(0, 4).forEach((chat) => {
    const row = document.createElement('button'); row.className = 'activity-item'; row.type = 'button';
    const icon = document.createElement('span'); icon.className = 'activity-icon'; icon.textContent = '◌';
    const meta = document.createElement('span');
    const title = document.createElement('strong'); title.textContent = chat.title;
    const date = document.createElement('small'); date.textContent = new Date(`${chat.updated_at}Z`).toLocaleString();
    meta.append(title, date); row.append(icon, meta); row.addEventListener('click', () => loadConversation(chat.id)); target.append(row);
  });
}

async function loadConversation(id) {
  try {
    const data = await api(`/api/chats/${id}`);
    state.conversationId = data.chat.id;
    appendConversation(data.messages || []);
    showView('chat');
  } catch (error) { toast(error.message); }
}

function renderHistory() {
  const target = $('history-content'); target.replaceChildren();
  if (!state.chats.length) { const empty = document.createElement('p'); empty.className = 'loading-card'; empty.textContent = 'No saved conversations yet.'; target.append(empty); return; }
  state.chats.forEach((chat) => addChatButton(chat, target));
}

async function loadModels() {
  try {
    const data = await api('/api/models');
    state.models = data.models || [];
    const settings = await api('/api/settings');
    const select = $('model-select');
    const settingsSelect = $('settings-model');
    [select, settingsSelect].forEach((node) => node.replaceChildren());
    state.models.forEach((model) => {
      const name = model.name;
      [select, settingsSelect].forEach((node) => { const option = document.createElement('option'); option.value = name; option.textContent = name; node.append(option); });
    });
    if (!state.models.length) {
      [select, settingsSelect].forEach((node) => { const option = document.createElement('option'); option.value = ''; option.textContent = 'No local model found'; node.append(option); });
    }
    const preferred = settings.default_model && state.models.some((model) => model.name === settings.default_model) ? settings.default_model : (state.models[0]?.name || '');
    select.value = preferred; settingsSelect.value = preferred;
    if (preferred && preferred !== settings.default_model) await api('/api/settings', { method: 'POST', body: JSON.stringify({ default_model: preferred, location: settings.weather.location || '', latitude: settings.weather.latitude, longitude: settings.weather.longitude }) });
    $('service-status').textContent = state.models.length ? `${state.models.length} local model${state.models.length === 1 ? '' : 's'} ready` : 'Ollama online · no models';
  } catch (error) {
    state.models = [];
    $('service-status').textContent = 'Local model offline';
    $('model-select').replaceChildren(new Option('Start Ollama to load models', ''));
    $('settings-model').replaceChildren(new Option('Ollama is offline', ''));
  }
}

function setMetric(id, meterId, value, suffix = '%') {
  const label = $(id); const meter = $(meterId);
  if (value === null || value === undefined || Number.isNaN(Number(value))) { label.textContent = '—'; meter.style.width = '0%'; meter.classList.add('unavailable'); return; }
  const number = Math.max(0, Math.min(100, Number(value)));
  label.textContent = `${Math.round(number)}${suffix}`; meter.style.width = `${number}%`; meter.classList.remove('unavailable');
}

function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) return 'Unavailable';
  const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); const minutes = Math.floor((seconds % 3600) / 60);
  return [days ? `${days}d` : '', `${hours}h`, `${minutes}m`].filter(Boolean).join(' ');
}

async function loadSystem(showError = false) {
  try {
    const data = await api('/api/system');
    setMetric('cpu-value', 'cpu-meter', data.cpu_percent);
    setMetric('memory-value', 'memory-meter', data.memory_percent);
    setMetric('gpu-value', 'gpu-meter', data.gpu_percent);
    const summary = data.gpu_percent === null ? 'GPU telemetry unavailable' : `${data.gpu_name} responding`;
    $('health-summary').textContent = summary;
    $('health-indicator').classList.toggle('offline', data.gpu_percent === null);
    const content = $('system-content'); content.replaceChildren();
    const cards = [
      ['CPU load', data.cpu_percent === null ? '—' : `${data.cpu_percent}%`, 'Recent aggregate usage'],
      ['Memory', data.memory_percent === null ? '—' : `${data.memory_used_gib} / ${data.memory_total_gib} GiB`, 'System memory in use'],
      ['GPU activity', data.gpu_percent === null ? 'Not exposed' : `${data.gpu_percent}%`, data.gpu_name],
      ['Home storage', `${data.disk_used_gib} / ${data.disk_total_gib} GiB`, `${data.disk_percent ?? '—'}% used`],
      ['Uptime', formatUptime(data.uptime_seconds), 'Since the last boot'],
      ['Load average', data.load_average ? data.load_average.map((number) => Number(number).toFixed(2)).join(' · ') : '—', '1 / 5 / 15 minute averages'],
    ];
    cards.forEach(([title, value, description]) => {
      const card = document.createElement('article'); card.className = 'metric-card';
      const heading = document.createElement('span'); heading.className = 'eyebrow'; heading.textContent = title;
      const number = document.createElement('strong'); number.textContent = value;
      const help = document.createElement('small'); help.textContent = description;
      card.append(heading, number, help); content.append(card);
    });
  } catch (error) { if (showError) toast(error.message); }
}

function weatherIcon(description, isDay = true) {
  const text = (description || '').toLowerCase();
  if (text.includes('thunder')) return 'ϟ';
  if (text.includes('rain') || text.includes('drizzle')) return '☂';
  if (text.includes('snow')) return '❄';
  if (text.includes('cloud') || text.includes('overcast')) return '☁';
  if (text.includes('fog')) return '≋';
  return isDay ? '☼' : '☾';
}

async function loadWeather(showError = false) {
  try {
    const data = await api('/api/weather'); state.weather = data;
    $('rail-weather-location').textContent = data.location || 'Forecast';
    if (!data.configured) {
      $('rail-weather-temp').textContent = '—°'; $('rail-weather-description').textContent = 'Location not set'; $('rail-weather-feels').textContent = 'Configure in Settings'; $('rail-forecast').replaceChildren();
      if (state.view === 'weather') {
        const node = document.createElement('div'); node.className = 'loading-card'; node.textContent = data.message; $('weather-content').replaceChildren(node);
      }
      return;
    }
    $('rail-weather-temp').textContent = `${Math.round(data.temperature)}°`;
    $('rail-weather-description').textContent = data.description;
    $('rail-weather-feels').textContent = `Feels like ${Math.round(data.feels_like)}° · ${data.humidity}% humidity`;
    const forecast = $('rail-forecast'); forecast.replaceChildren();
    data.days.slice(0, 4).forEach((day) => {
      const item = document.createElement('div'); item.className = 'forecast-mini';
      const date = document.createElement('small'); date.textContent = new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' });
      const icon = document.createElement('span'); icon.textContent = weatherIcon(day.description);
      const range = document.createElement('strong'); range.textContent = `${Math.round(day.high)}°/${Math.round(day.low)}°`;
      item.append(date, icon, range); forecast.append(item);
    });
    if (state.view === 'weather') renderWeatherPage(data);
  } catch (error) {
    $('rail-weather-description').textContent = 'Forecast unavailable';
    if (showError) toast(error.message);
  }
}

function renderWeatherPage(data) {
  const target = $('weather-content'); target.replaceChildren();
  const current = document.createElement('div'); current.className = 'weather-hero glass-inset';
  const icon = document.createElement('div'); icon.className = 'weather-hero-icon'; icon.textContent = weatherIcon(data.description, data.is_day);
  const text = document.createElement('div'); text.className = 'weather-hero-text';
  const temp = document.createElement('strong'); temp.textContent = `${Math.round(data.temperature)}°`;
  const desc = document.createElement('span'); desc.textContent = data.description;
  const place = document.createElement('small'); place.textContent = `${data.location} · Feels like ${Math.round(data.feels_like)}°`;
  text.append(temp, desc, place); current.append(icon, text);
  const details = document.createElement('div'); details.className = 'weather-details';
  [['Humidity', `${data.humidity}%`], ['Wind', `${data.wind_speed} km/h`], ['Provider', data.provider]].forEach(([label, value]) => {
    const item = document.createElement('article'); item.className = 'metric-card';
    const h = document.createElement('span'); h.className = 'eyebrow'; h.textContent = label;
    const v = document.createElement('strong'); v.textContent = value; item.append(h, v); details.append(item);
  });
  const heading = document.createElement('h3'); heading.className = 'subheading'; heading.textContent = 'Five-day forecast';
  const days = document.createElement('div'); days.className = 'forecast-days';
  data.days.forEach((day) => {
    const card = document.createElement('article'); card.className = 'forecast-day glass-inset';
    const date = document.createElement('small'); date.textContent = new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric' });
    const weather = document.createElement('span'); weather.className = 'forecast-symbol'; weather.textContent = weatherIcon(day.description);
    const description = document.createElement('span'); description.textContent = day.description;
    const range = document.createElement('strong'); range.textContent = `${Math.round(day.high)}° / ${Math.round(day.low)}°`;
    card.append(date, weather, description, range); days.append(card);
  });
  target.append(current, details, heading, days);
}

function addDoctorCheck(item, target) {
  const card = document.createElement('article'); card.className = 'doctor-check metric-card';
  const head = document.createElement('div'); head.className = 'doctor-check-head';
  const name = document.createElement('strong'); name.textContent = item.name;
  const status = document.createElement('span'); status.className = 'doctor-status ' + item.status; status.textContent = item.status.toUpperCase();
  const detail = document.createElement('small'); detail.textContent = item.detail || '';
  head.append(name, status); card.append(head, detail); target.append(card);
}

async function loadDoctor(showError = false) {
  try {
    const values = await Promise.all([api('/api/doctor/diagnostics'), api('/api/doctor/updates'), api('/api/doctor/backups')]);
    const diagnostics = values[0], updates = values[1], backups = values[2];
    $('doctor-summary').textContent = diagnostics.summary.ok + '/' + diagnostics.summary.total + ' checks passed · ' + diagnostics.summary.warning + ' warnings · ' + diagnostics.summary.attention + ' attention required';
    const checks = $('doctor-checks'); checks.replaceChildren();
    diagnostics.checks.forEach((item) => addDoctorCheck(item, checks));
    const updateTarget = $('update-content'); updateTarget.replaceChildren();
    updates.components.forEach((component) => {
      const row = document.createElement('article'); row.className = 'doctor-row';
      const info = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = component.repository;
      const detail = document.createElement('small');
      detail.textContent = component.status === 'available'
        ? 'Installed ' + component.current + ' · Latest ' + (component.latest || 'unknown')
        : (component.status === 'no_release'
          ? 'Installed ' + component.current + ' · No published release available'
          : 'Installed ' + component.current + ' · Release check unavailable' + (component.detail ? ': ' + component.detail : ''));
      info.append(title, detail);
      const stateLabel = document.createElement('span'); stateLabel.className = 'doctor-status ' + (component.update_available ? 'warning' : (component.status === 'unavailable' ? 'attention' : 'ok'));
      stateLabel.textContent = component.update_available ? 'UPDATE' : (component.status === 'available' ? 'CURRENT' : (component.status === 'no_release' ? 'NO RELEASE' : 'CHECK FAILED'));
      row.append(info, stateLabel);
      if (component.url) {
        const link = document.createElement('a'); link.href = component.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'Release notes'; row.append(link);
      }
      updateTarget.append(row);
    });
    $('update-status').textContent = updates.update_available ? 'A newer project release is available.' : 'No newer published release detected.';
    renderBackups(backups.backups || []);
  } catch (error) { if (showError) toast(error.message); }
}

function renderBackups(backups) {
  const target = $('backup-content'); target.replaceChildren();
  if (!backups.length) {
    const empty = document.createElement('p'); empty.className = 'loading-card'; empty.textContent = 'No Fenrir configuration backups are available yet.'; target.append(empty); return;
  }
  backups.forEach((backup) => {
    const row = document.createElement('article'); row.className = 'doctor-row';
    const info = document.createElement('div');
    const name = document.createElement('strong'); name.textContent = backup.id;
    const detail = document.createElement('small'); detail.textContent = backup.files + ' backed-up files';
    info.append(name, detail);
    const button = document.createElement('button'); button.type = 'button'; button.className = 'widget-link';
    button.dataset.restoreBackup = backup.id; button.textContent = 'Restore';
    row.append(info, button); target.append(row);
  });
}

async function loadWallpapers(showError = false) {
  try {
    const data = await api('/api/doctor/wallpapers');
    $('wallpaper-summary').textContent = data.catalog_available
      ? data.detail
      : data.detail + ' Existing local wallpapers remain available.';
    const metrics = $('wallpaper-metrics'); metrics.replaceChildren();
    [
      ['Accepted catalog records', data.accepted_asset_count === null ? 'Not connected' : Number(data.accepted_asset_count).toLocaleString(), 'Human acceptance is separate from rights approval.'],
      ['Qualifying local wallpapers', Number(data.local_image_count).toLocaleString(), 'Landscape, at least 2560×1440, with an allowed dominant palette.'],
      ['Excluded yellow / orange / brown', Number(data.palette_metrics?.excluded_palette_color || 0).toLocaleString(), 'Excluded by Fenrir’s wallpaper color policy.'],
      ['Other unusable files', (Number(data.palette_metrics?.below_resolution_or_wrong_orientation || 0) + Number(data.palette_metrics?.invalid_files || 0)).toLocaleString(), 'Undersized, portrait, corrupt or unsupported files.'],
    ].forEach(([title, value, detail]) => {
      const card = document.createElement('article'); card.className = 'metric-card';
      const label = document.createElement('span'); label.className = 'eyebrow'; label.textContent = title;
      const number = document.createElement('strong'); number.textContent = value;
      const help = document.createElement('small'); help.textContent = detail;
      card.append(label, number, help); metrics.append(card);
    });

    const publicLibrary = data.public_library || {};
    const publicRunning = publicLibrary.running === true;
    const publicPlan = state.publicLibraryPlan;
    const publicAvailable = publicLibrary.available === true;
    $('wallpaper-public-library-plan-button').disabled = !publicAvailable || publicRunning;
    $('wallpaper-public-library-sync-button').disabled = !publicAvailable || publicRunning
      || !publicPlan || Number(publicPlan.selected_downloads || 0) === 0;
    $('wallpaper-public-library-sync-button').textContent = publicRunning
      ? 'Public library synchronization running…' : 'Synchronize public volumes';
    $('wallpaper-public-library-status').textContent = publicRunning
      ? 'Downloading verified public wallpapers; progress is recorded in the log below.'
      : (publicLibrary.returncode === 0 ? 'Last public-library synchronization completed.'
        : (publicLibrary.returncode !== null && publicLibrary.returncode !== undefined
          ? 'Public-library synchronization stopped (exit ' + publicLibrary.returncode + ').'
          : (publicAvailable ? 'Ready; preview before starting.' : 'fenrir-wallpaper is not installed.')));
    $('wallpaper-public-library-log').textContent = publicLibrary.log || '';
    if (!publicPlan) {
      $('wallpaper-public-library-summary').textContent = publicAvailable
        ? 'The public mirror is ready. Preview the active volumes and missing images before downloading.'
        : 'The Fenrir wallpaper command is unavailable.';
      $('wallpaper-public-library-plan-status').textContent = publicRunning
        ? 'Synchronization is already running.' : 'Read-only preview has not been run.';
    }

    const portfolio = data.portfolio || {};
    const portfolioSummary = $('wallpaper-portfolio-summary');
    const portfolioMetrics = $('wallpaper-portfolio-metrics');
    const providerCards = $('wallpaper-portfolio-providers');
    const profileRows = $('wallpaper-portfolio-profiles');
    portfolioMetrics.replaceChildren();
    providerCards.replaceChildren();
    profileRows.replaceChildren();
    if (portfolio.available && portfolio.report) {
      const report = portfolio.report;
      const inventory = report.collection_status || {};
      portfolioSummary.textContent = inventory.status === 'observed_trend'
        ? 'Observed accepted-asset activity over the last ' + Number(inventory.history_days).toLocaleString()
          + ' days. This is inventory history, not a target or completion forecast.'
        : 'Insufficient recent human-acceptance history for a trend. Current inventory and campaign activity are shown without a size goal.';
      if (!portfolio.attribution_count_is_exact) {
        portfolioSummary.textContent += ' Local Catalog attribution sidecar is unavailable; local-copy reconciliation remains unknown.';
      }
      [
        ['Qualifying local wallpapers', Number(inventory.local_qualifying_count || 0).toLocaleString(),
          'Readable landscape images meeting Fenrir resolution and palette rules.'],
        ['Accepted and quality eligible', Number(inventory.accepted_quality_eligible_count || 0).toLocaleString(),
          'Human acceptance, rights checks, valid stored image and the Fenrir palette policy.'],
        ['Accepted assets not attributed locally', inventory.estimated_accepted_not_yet_local === null
          || inventory.estimated_accepted_not_yet_local === undefined ? 'Unknown'
          : Number(inventory.estimated_accepted_not_yet_local).toLocaleString(),
          inventory.attribution_note || 'Observed from the local Catalog attribution sidecar.'],
        ['Recent human acceptance pace', Number(inventory.recent_acceptance_rate_per_day || 0).toFixed(2) + ' / day',
          Number(inventory.recent_accepted_count || 0).toLocaleString() + ' quality-eligible acceptances in '
          + Number(inventory.history_days || 0).toLocaleString() + ' days.'],
        ['New discovery metadata', Number((report.providers || []).reduce(
          (sum, item) => sum + Number(item.new_assets || 0), 0
        )).toLocaleString(),
          'Metadata records only; not downloads, rights approvals or accepted images.']
      ].forEach(([title, value, detail]) => {
        const card = document.createElement('article'); card.className = 'metric-card';
        const label = document.createElement('span'); label.className = 'eyebrow'; label.textContent = title;
        const number = document.createElement('strong'); number.textContent = value;
        const help = document.createElement('small'); help.textContent = detail;
        card.append(label, number, help); portfolioMetrics.append(card);
      });
      (report.providers || []).forEach((provider) => {
        const card = document.createElement('article'); card.className = 'portfolio-provider-card';
        const title = document.createElement('strong');
        title.textContent = ({
          openverse: 'Openverse',
          wikimedia_commons: 'Wikimedia Commons',
          wallhaven: 'Wallhaven',
          cleveland_museum: 'Cleveland Museum of Art (CC0)'
        })[provider.source_key] || provider.source_key;
        const budget = provider.provider_budget || {};
        const stats = document.createElement('small');
        stats.textContent = Number(provider.estimated_api_requests || 0).toLocaleString()
          + ' estimated requests · ' + Number(provider.pages_processed || 0).toLocaleString()
          + ' pages · ' + Number(provider.new_assets || 0).toLocaleString() + ' new records';
        const policy = document.createElement('small');
        policy.textContent = Number(budget.max_api_requests_per_slice || 0).toLocaleString()
          + ' max requests / turn · ' + Number(budget.max_queries_per_slice || 0)
          + ' queries × ' + Number(budget.max_pages_per_query || 0) + ' pages';
        const status = document.createElement('small');
        status.textContent = Number(provider.completed_campaigns || 0).toLocaleString()
          + ' complete · ' + Number(provider.paused_campaigns || 0).toLocaleString()
          + ' paused · ' + Number(provider.failed_campaigns || 0).toLocaleString() + ' failed';
        card.append(title, stats, policy, status); providerCards.append(card);
      });
      (report.profiles || []).forEach((profile) => {
        const row = document.createElement('div'); row.className = 'portfolio-profile-row';
        const name = document.createElement('strong'); name.textContent = profile.profile_key;
        const detail = document.createElement('span');
        detail.textContent = Number(profile.new_assets || 0).toLocaleString()
          + ' new records · ' + Number(profile.pages_processed || 0).toLocaleString()
          + ' pages · ' + Number(profile.completed_campaigns || 0).toLocaleString()
          + ' campaigns complete';
        row.append(name, detail); profileRows.append(row);
      });
    } else {
      portfolioSummary.textContent = portfolio.detail || 'The local Catalog inventory report is unavailable.';
    }
    const sync = data.sync || {};
    const syncPlan = state.wallpaperSyncPlan;
    const syncAvailable = data.catalog_available && data.sync_destination_allowed && !sync.running;
    $('wallpaper-sync-plan-button').disabled = !syncAvailable;
    $('wallpaper-sync-button').disabled = !syncAvailable || !syncPlan || !syncPlan.sync_allowed;
    $('wallpaper-sync-button').textContent = sync.running ? 'Synchronization running…' : 'Sync accepted wallpapers';
    $('wallpaper-sync-status').textContent = sync.running ? 'Copying verified accepted assets…' : (sync.returncode === 0 ? 'Last synchronization completed.' : (sync.returncode ? 'Synchronization stopped (exit ' + sync.returncode + ').' : 'Ready'));
    if (!syncPlan) {
      $('wallpaper-sync-plan-status').textContent = 'Run a fresh read-only preflight before synchronization.';
    } else if (syncPlan.sync_allowed) {
      $('wallpaper-sync-plan-status').textContent = 'Preflight ready: '
        + Number(syncPlan.planned_new_copies).toLocaleString() + ' new accepted assets; all eligible metadata inspected.';
    } else if (!syncPlan.plan_complete) {
      $('wallpaper-sync-plan-status').textContent = 'Preflight incomplete: the technical metadata scan ceiling was reached. Synchronization is blocked.';
    } else {
      $('wallpaper-sync-plan-status').textContent = 'No new accepted assets are currently ready for synchronization. Review the blockers in the Catalog.';
    }
    $('wallpaper-sync-log').textContent = sync.log || '';

    const discovery = data.discovery || {};
    const campaign = discovery.campaign;
    const discoverySummary = $('wallpaper-discovery-summary');
    discoverySummary.replaceChildren();
    if (campaign) {
      const progress = campaign.progress || {};
      const heading = document.createElement('strong');
      heading.textContent = campaign.profile_key || 'Wallpaper campaign';
      const detail = document.createElement('small');
      detail.textContent = (campaign.status || 'unknown').toUpperCase() + ' · '
        + Number(progress.completed_queries || 0) + '/' + Number(progress.total_queries || 0) + ' queries · '
        + Number(progress.new_assets || 0).toLocaleString() + ' new metadata records · '
        + Number(progress.observations_recorded || 0).toLocaleString() + ' observations';
      const id = document.createElement('small');
      id.textContent = 'Campaign ID: ' + campaign.campaign_id;
      discoverySummary.append(heading, detail, id);
      if (campaign.error_summary) {
        const error = document.createElement('small');
        error.textContent = campaign.error_summary;
        discoverySummary.append(error);
      }
      $('wallpaper-source').value = discovery.source || campaign.source_key || 'openverse';
      $('wallpaper-profile').value = discovery.profile || campaign.profile_key || 'fenrir-nordic-fantasy-v1';
    } else {
      const empty = document.createElement('p');
      empty.className = 'loading-card';
      empty.textContent = discovery.error || 'No wallpaper discovery campaign has been started.';
      discoverySummary.append(empty);
    }
    $('wallpaper-discovery-log').textContent = discovery.log || '';
    const discoveryRunning = Boolean(discovery.process_running);
    $('wallpaper-discover-button').disabled = discoveryRunning || !data.catalog_available;
    $('wallpaper-discover-button').textContent = discoveryRunning
      ? 'Discovery running…'
      : (campaign && campaign.status !== 'completed' ? 'Resume discovery campaign' : 'Start discovery campaign');
    $('wallpaper-discovery-status').textContent = discoveryRunning
      ? 'Searching provider metadata only…'
      : (campaign ? 'Last campaign: ' + campaign.status : 'Ready');

    const schedule = discovery.scheduler || {};
    state.wallpaperSchedule = schedule;
    $('wallpaper-schedule-interval').value = String(schedule.interval_minutes || 360);
    $('wallpaper-schedule-mode').value = schedule.run_mode || 'continuous';
    $('wallpaper-schedule-mode').disabled = Boolean(schedule.enabled);
    $('wallpaper-schedule-interval').disabled = Boolean(schedule.enabled) || schedule.run_mode === 'continuous';
    const queueInputs = document.querySelectorAll('.wallpaper-queue-source, .wallpaper-queue-profile');
    queueInputs.forEach((input) => { input.disabled = Boolean(schedule.enabled); });
    $('wallpaper-source').disabled = Boolean(schedule.enabled);
    $('wallpaper-profile').disabled = Boolean(schedule.enabled);
    $('wallpaper-contact').disabled = Boolean(schedule.enabled);
    const scheduleButton = $('wallpaper-schedule-button');
    const resumableQueue = schedule.last_status === 'paused'
      && Number(schedule.queue_total || 0) > Number(schedule.queue_index || 0);
    scheduleButton.textContent = schedule.enabled
      ? 'Pause metadata discovery'
      : (resumableQueue ? 'Resume discovery run' : 'Start metadata discovery');
    scheduleButton.disabled = !schedule.enabled && !data.catalog_available;
    const currentQueueItem = schedule.queue_current || null;
    const currentQueueLabel = currentQueueItem
      ? ' · ' + currentQueueItem.source + ' / ' + currentQueueItem.profile
      : '';
    const queueProgress = Number(schedule.queue_total || 0) > 0
      ? ' · turn ' + Math.min(Number(schedule.queue_position || 0), Number(schedule.queue_total))
        + '/' + Number(schedule.queue_total) + ' · '
        + Number(schedule.queue_completed_count || 0) + ' completed' + currentQueueLabel
      : '';
    if (schedule.enabled) {
      if (schedule.run_mode === 'continuous') {
        $('wallpaper-schedule-status').textContent = 'Continuous metadata discovery active' + queueProgress + ' · next bounded slice starts automatically';
      } else {
        const next = schedule.next_run_at
          ? new Date(schedule.next_run_at * 1000).toLocaleString()
          : 'when the current slice finishes';
        $('wallpaper-schedule-status').textContent = 'Scheduled discovery active' + queueProgress + ' · next slice ' + next;
      }
    } else if (schedule.last_status === 'needs_review') {
      $('wallpaper-schedule-status').textContent = 'Queue complete. Human rights review and explicit acceptance are required.';
    } else if (schedule.last_status === 'paused_error' || schedule.last_status === 'invalid') {
      $('wallpaper-schedule-status').textContent = 'Stopped safely: ' + (schedule.last_error || schedule.pause_reason || 'inspect scheduler status');
    } else if (schedule.last_status === 'paused') {
      $('wallpaper-schedule-status').textContent = 'Automatic discovery paused. ' + (resumableQueue ? 'The saved queue can be resumed.' : 'A running slice is allowed to finish.');
    } else {
      $('wallpaper-schedule-status').textContent = 'Automatic discovery is off.';
    }
    if (schedule.enabled) $('wallpaper-discover-button').disabled = true;
    updateCommonsContactVisibility();
    loadWallpaperRightsReview();
    loadWallpaperAcquisitionQueue();
  } catch (error) { if (showError) toast(error.message); }
}


async function loadWallpaperRightsReview(showError = false) {
  const summary = $('wallpaper-rights-review-summary');
  const metrics = $('wallpaper-rights-review-metrics');
  const items = $('wallpaper-rights-review-items');
  const status = $('wallpaper-rights-review-status');
  try {
    const data = await api('/api/doctor/wallpapers/rights-review');
    summary.textContent = data.detail || 'Rights-review snapshot loaded.';
    metrics.replaceChildren();
    items.replaceChildren();
    const queue = data.queue;
    if (!data.available || !queue) {
      items.append(Object.assign(document.createElement('p'), {
        className: 'loading-card',
        textContent: data.detail || 'Rights-review queue is unavailable.'
      }));
      status.textContent = 'Read-only snapshot unavailable';
      return;
    }

    const counts = queue.status_counts || {};
    [
      ['Open rights cases', Number(queue.total_count || 0).toLocaleString(), 'Recorded statuses still requiring human review.'],
      ['Unknown', Number(counts.unknown || 0).toLocaleString(), 'No recorded rights conclusion yet.'],
      ['Review required', Number(counts.review_required || 0).toLocaleString(), 'Additional evidence or human judgment is needed.'],
      ['Policy-eligible', Number(counts.eligible || 0).toLocaleString(), 'Policy assessment is not human approval.']
    ].forEach(([title, value, detail]) => {
      const card = document.createElement('article');
      card.className = 'metric-card';
      const label = document.createElement('span');
      label.className = 'eyebrow';
      label.textContent = title;
      const number = document.createElement('strong');
      number.textContent = value;
      const help = document.createElement('small');
      help.textContent = detail;
      card.append(label, number, help);
      metrics.append(card);
    });

    (queue.items || []).forEach((item) => {
      const row = document.createElement('article');
      row.className = 'doctor-row';
      const info = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = item.title || 'Untitled asset';
      const detail = document.createElement('small');
      detail.textContent = (item.source_key || 'Unknown source') + ' · ' + item.rights_status
        + ' · ' + (item.license_identifier || 'No license recorded');
      const gaps = document.createElement('small');
      gaps.textContent = item.metadata_gaps && item.metadata_gaps.length
        ? 'Evidence gaps: ' + item.metadata_gaps.join(', ')
        : 'No basic metadata gaps reported';
      info.append(name, detail, gaps);
      row.append(info);
      items.append(row);
    });
    if (!(queue.items || []).length) {
      const empty = document.createElement('p');
      empty.className = 'loading-card';
      empty.textContent = 'No unresolved rights cases were returned.';
      items.append(empty);
    }
    status.textContent = 'Read-only · no rights decisions or acquisition authorizations created'
      + (queue.has_more ? ' · more cases available in the Studio' : '');
  } catch (error) {
    summary.textContent = error.message;
    if (showError) toast(error.message);
  }
}

async function loadWallpaperAcquisitionQueue(showError = false) {
  const summary = $('wallpaper-acquisition-summary');
  const metrics = $('wallpaper-acquisition-metrics');
  const items = $('wallpaper-acquisition-items');
  const status = $('wallpaper-acquisition-status');
  try {
    const data = await api('/api/doctor/wallpapers/acquisition-queue');
    summary.textContent = data.detail || 'Campaign acquisition report loaded.';
    metrics.replaceChildren();
    items.replaceChildren();
    const queue = data.queue;
    if (!queue) {
      const empty = document.createElement('p');
      empty.className = 'loading-card';
      empty.textContent = data.detail || 'No acquisition queue is available.';
      items.append(empty);
      status.textContent = 'Read-only · no transfers started';
      return;
    }

    const stages = queue.stage_counts || {};
    [
      ['Campaign assets', Number(queue.total_campaign_assets || 0).toLocaleString(), 'Unique assets observed by this discovery campaign.'],
      ['Ready for authorization', Number(queue.ready_for_authorization_count || 0).toLocaleString(), 'Evidence checks pass; explicit per-asset authorization is still required.'],
      ['Batch-ready', Number(queue.authorized_batch_ready_count || 0).toLocaleString(), 'Current authorization and evidence still pass revalidation.'],
      ['Blocked', Number(queue.blocked_count || 0).toLocaleString(), 'Rights, license, provider or recovery evidence needs attention.'],
      ['Quarantined for review', Number(stages.quarantined_pending_review || 0).toLocaleString(), 'Downloaded files still require duplicate review and explicit human acceptance.']
    ].forEach(([title, value, detail]) => {
      const card = document.createElement('article');
      card.className = 'metric-card';
      const label = document.createElement('span');
      label.className = 'eyebrow';
      label.textContent = title;
      const number = document.createElement('strong');
      number.textContent = value;
      const help = document.createElement('small');
      help.textContent = detail;
      card.append(label, number, help);
      metrics.append(card);
    });

    (queue.items || []).forEach((item) => {
      const row = document.createElement('article');
      row.className = 'doctor-row';
      const info = document.createElement('div');
      const heading = document.createElement('strong');
      heading.textContent = item.title || item.asset_id;
      const details = document.createElement('small');
      details.textContent = item.source_key + ' · ' + (item.license_identifier || 'license unknown')
        + ' · ' + (item.width || '?') + '×' + (item.height || '?');
      const stage = document.createElement('small');
      const stageLabels = {
        ready_for_authorization: 'Ready for explicit acquisition authorization',
        blocked_for_authorization: 'Blocked: rights / license / provider checks',
        authorized_pending_acquisition: 'Authorized · ready for provider batch',
        authorization_stale: 'Authorization stale · refresh evidence',
        blocked_unresolved_attempt: 'Blocked · reconcile previous transfer',
        quarantined_pending_review: 'Quarantined · duplicate review and acceptance required',
        accepted: 'Accepted · eligible for curation and sync',
        rejected: 'Rejected',
        other: item.stage || 'Other'
      };
      stage.textContent = stageLabels[item.stage] || item.stage || 'Unknown status';
      info.append(heading, details, stage);
      row.append(info);

      if (Array.isArray(item.blockers) && item.blockers.length) {
        const blocker = document.createElement('small');
        blocker.textContent = item.blockers.map((entry) => entry.code).join(', ');
        row.append(blocker);
      }
      items.append(row);
    });

    if (!queue.count) {
      const empty = document.createElement('p');
      empty.className = 'loading-card';
      empty.textContent = 'No assets have been observed by this campaign yet.';
      items.append(empty);
    }
    const shown = Number(queue.count || 0);
    const total = Number(queue.total_campaign_assets || 0);
    status.textContent = 'Read-only · ' + shown.toLocaleString() + ' shown'
      + (total > shown ? ' of ' + total.toLocaleString() + ' · CLI supports further pages' : '')
      + ' · 0 downloads';
  } catch (error) {
    summary.textContent = 'Acquisition readiness is unavailable.';
    metrics.replaceChildren();
    items.replaceChildren();
    const empty = document.createElement('p');
    empty.className = 'loading-card';
    empty.textContent = error.message;
    items.append(empty);
    status.textContent = 'No changes made';
    if (showError) toast(error.message);
  }
}

async function loadSettings() {
  try {
    const data = await api('/api/settings');
    $('settings-model').value = data.default_model || $('model-select').value;
    $('weather-location').value = data.weather.location || '';
    $('weather-latitude').value = data.weather.latitude ?? '';
    $('weather-longitude').value = data.weather.longitude ?? '';
      } catch (error) { toast(error.message); }
}

$('settings-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    default_model: $('settings-model').value,
    location: $('weather-location').value,
    latitude: $('weather-latitude').value,
    longitude: $('weather-longitude').value,
  };
  try {
    await api('/api/settings', { method: 'POST', body: JSON.stringify(payload) });
    $('model-select').value = payload.default_model;
    $('settings-status').textContent = 'Saved locally';
    toast('Preferences saved');
    loadWeather();
  } catch (error) { $('settings-status').textContent = ''; toast(error.message); }
});

$('upgrade-button').addEventListener('click', async () => {
  $('update-status').textContent = 'Opening interactive updater…';
  try {
    const result = await api('/api/doctor/upgrade', { method: 'POST', body: JSON.stringify({}) });
    $('update-status').textContent = result.message;
    toast('Fenrir updater opened in a terminal');
  } catch (error) { $('update-status').textContent = error.message; toast(error.message); }
});

function updateCommonsContactVisibility() {
  const group = $('commons-contact-group');
  const queueUsesCommons = Array.from(document.querySelectorAll('.wallpaper-queue-source:checked'))
    .some((input) => input.value === 'wikimedia_commons');
  if (group) group.classList.toggle('hidden',
    $('wallpaper-source').value !== 'wikimedia_commons' && !queueUsesCommons);
}

$('wallpaper-source').addEventListener('change', updateCommonsContactVisibility);
document.querySelectorAll('.wallpaper-queue-source').forEach((input) => {
  input.addEventListener('change', updateCommonsContactVisibility);
});

$('wallpaper-acquisition-refresh').addEventListener('click', () => loadWallpaperAcquisitionQueue(true));

$('wallpaper-rights-review-refresh').addEventListener('click', () => loadWallpaperRightsReview(true));

$('wallpaper-rights-review-open').addEventListener('click', async () => {
  const button = $('wallpaper-rights-review-open');
  const status = $('wallpaper-rights-review-status');
  const waitingTab = window.open('about:blank', '_blank');
  button.disabled = true;
  status.textContent = 'Starting the private Catalog review board…';
  try {
    const result = await api('/api/doctor/wallpapers/rights-studio', {
      method: 'POST',
      body: JSON.stringify({})
    });
    const target = new URL(result.url);
    if (
      target.protocol !== 'http:'
      || target.hostname !== '127.0.0.1'
      || target.port === ''
      || !/^\/s\/[A-Za-z0-9_-]{32,64}\/$/.test(target.pathname)
      || target.search
      || target.hash
    ) {
      throw new Error('Fenrir returned an invalid local Rights Review Studio address.');
    }
    if (waitingTab && !waitingTab.closed) {
      waitingTab.opener = null;
      waitingTab.location.replace(target.href);
    } else {
      const link = document.createElement('a');
      link.href = target.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Open Fenrir Rights Review Studio';
      status.replaceChildren(link);
    }
    status.textContent = result.already_running
      ? 'Existing private Rights Review Studio session opened.'
      : 'Private Rights Review Studio started.';
    toast('Rights Review Studio ready');
  } catch (error) {
    if (waitingTab && !waitingTab.closed) waitingTab.close();
    status.textContent = error.message;
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});

$('wallpaper-discover-button').addEventListener('click', async () => {
  const source = $('wallpaper-source').value;
  const profile = $('wallpaper-profile').value;
  const contact = $('wallpaper-contact').value.trim();
  if (source === 'wikimedia_commons' && !contact) {
    toast('Enter a contact email or project URL for Wikimedia Commons.');
    $('wallpaper-contact').focus();
    return;
  }
  const confirmText = source === 'openverse'
    ? 'Run the full bounded Openverse metadata profile? It may take several minutes. No image files will be downloaded or accepted.'
    : (source === 'wallhaven'
      ? 'Run the full bounded SFW Wallhaven metadata profile? It may take several minutes. No image files will be downloaded or accepted.'
      : (source === 'cleveland_museum'
        ? 'Run the Cleveland Museum of Art CC0 metadata profile? Only artworks individually marked CC0 with qualifying landscape images are retained. No image files will be downloaded or accepted.'
        : 'Run the full bounded Wikimedia Commons metadata profile using this contact identifier? It may take several minutes. No image files will be downloaded or accepted.'));
  if (!window.confirm(confirmText)) return;
  $('wallpaper-discover-button').disabled = true;
  $('wallpaper-discovery-status').textContent = 'Creating resumable campaign…';
  try {
    const result = await api('/api/doctor/wallpapers/discover', {
      method: 'POST',
      body: JSON.stringify({ source, profile, contact: source === 'wikimedia_commons' ? contact : null })
    });
    $('wallpaper-discovery-status').textContent = 'Campaign started: ' + result.campaign_id;
    toast('Wallpaper discovery started');
    loadWallpapers();
    window.setTimeout(loadWallpapers, 1500);
  } catch (error) {
    $('wallpaper-discovery-status').textContent = error.message;
    $('wallpaper-discover-button').disabled = false;
    toast(error.message);
  }
});

$('wallpaper-schedule-mode').addEventListener('change', () => {
  $('wallpaper-schedule-interval').disabled = $('wallpaper-schedule-mode').value === 'continuous';
});

$('wallpaper-schedule-button').addEventListener('click', async () => {
  const schedule = state.wallpaperSchedule || {};
  if (schedule.enabled) {
    if (!window.confirm('Pause future automatic discovery slices? Any metadata slice already running will finish safely.')) return;
    try {
      await api('/api/doctor/wallpapers/schedule', {
        method: 'POST',
        body: JSON.stringify({ enabled: false })
      });
      toast('Automatic wallpaper discovery paused');
      loadWallpapers();
    } catch (error) {
      $('wallpaper-schedule-status').textContent = error.message;
      toast(error.message);
    }
    return;
  }

  const interval = Number($('wallpaper-schedule-interval').value);
  const runMode = $('wallpaper-schedule-mode').value;
  const resumableQueue = schedule.last_status === 'paused'
    && Array.isArray(schedule.queue)
    && Number(schedule.queue_total || 0) > Number(schedule.queue_index || 0);
  let payload;
  let description;

  if (resumableQueue) {
    payload = { enabled: true, resume_existing_queue: true, interval_minutes: interval, run_mode: runMode };
    description = 'Resume the saved queue at campaign '
      + (Number(schedule.queue_index || 0) + 1) + ' of ' + Number(schedule.queue_total)
      + '? Completed campaigns will not be repeated. '
      + (runMode === 'continuous'
        ? 'Fenrir will keep rotating through bounded provider slices until discovery finishes or an error needs attention.'
        : 'Fenrir will run one bounded slice at the selected interval.')
      + ' Discovery remains metadata-only; rights review and acceptance stay separate.';
  } else {
    const sources = Array.from(document.querySelectorAll('.wallpaper-queue-source:checked'))
      .map((input) => input.value);
    const profiles = Array.from(document.querySelectorAll('.wallpaper-queue-profile:checked'))
      .map((input) => input.value);
    if (!sources.length || !profiles.length) {
      toast('Choose at least one source and one search profile for the queue.');
      return;
    }
    const contact = $('wallpaper-contact').value.trim();
    if (sources.includes('wikimedia_commons') && !contact) {
      toast('Enter a contact email or project URL for Wikimedia Commons.');
      $('wallpaper-contact').focus();
      return;
    }
    const queue = [];
    // Profile-major ordering rotates across the selected providers before
    // moving to the next profile, keeping discovery balanced by source.
    profiles.forEach((profile) => sources.forEach((source) => {
      queue.push({
        source,
        profile,
        contact: source === 'wikimedia_commons' ? contact : null
      });
    }));
    payload = { enabled: true, queue, interval_minutes: interval, run_mode: runMode };
    description = 'Start one collection run for ' + queue.length + ' provider/profile campaigns? '
      + (runMode === 'continuous'
        ? 'Fenrir will keep running provider-balanced slices without waiting between turns.'
        : 'Fenrir will run one provider-balanced slice at the selected interval.')
      + ' Every turn is capped at four provider API requests. Discovery records metadata only; it does not download files or decide rights, authorization, duplicates or acceptance.';
  }

  if (!window.confirm(description)) return;
  const button = $('wallpaper-schedule-button');
  button.disabled = true;
  $('wallpaper-schedule-status').textContent = resumableQueue
    ? 'Resuming saved collection run…'
    : (runMode === 'continuous' ? 'Starting continuous collection run…' : 'Starting scheduled discovery…');
  try {
    const result = await api('/api/doctor/wallpapers/schedule', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    state.wallpaperSchedule = result;
    toast(resumableQueue ? 'Wallpaper campaign queue resumed' : 'Wallpaper campaign queue enabled');
    loadWallpapers();
  } catch (error) {
    $('wallpaper-schedule-status').textContent = error.message;
    button.disabled = false;
    toast(error.message);
  }
});

$('wallpaper-public-library-audit-button').addEventListener('click', async () => {
  const button = $('wallpaper-public-library-audit-button');
  button.disabled = true;
  $('wallpaper-public-library-audit-status').textContent = 'Reading the public registry and committed manifests…';
  $('wallpaper-public-library-audit-summary').textContent = 'No image files are downloaded or changed during this audit.';
  try {
    const report = await api('/api/doctor/wallpapers/public-library-audit', {
      method: 'POST', body: JSON.stringify({})
    });
    state.publicLibraryAudit = report;
    const categories = Object.entries(report.category_counts || {})
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([name, count]) => name.replaceAll('-', ' ') + ': ' + Number(count).toLocaleString())
      .join(' · ');
    const palette = report.palette || {};
    const licenses = report.license_counts || {};
    const storage = (report.volumes || []).map((volume) => {
      const status = volume.storage || {};
      const size = status.api_reported_size_bytes === null || status.api_reported_size_bytes === undefined
        ? 'storage unknown'
        : (Number(status.api_reported_size_bytes) / (1024 ** 3)).toFixed(2) + ' GiB';
      return volume.id + ': ' + Number(volume.image_count).toLocaleString()
        + ' images · ' + size + ' · ' + status.status;
    }).join(' | ');
    const categoryBalance = report.category_balance || {};
    $('wallpaper-public-library-audit-summary').textContent =
      Number(report.manifest_records).toLocaleString() + ' manifest records / '
      + Number(report.unique_images).toLocaleString() + ' unique SHA-256 identifiers across '
      + Number(report.active_volume_count).toLocaleString() + ' active volumes. '
      + 'Population: ' + report.population_state + '. No image-count target. '
      + 'Duplicates: ' + Number(report.duplicate_records).toLocaleString()
      + '; hash/path mismatches: ' + Number(report.hash_path_mismatches).toLocaleString()
      + '; invalid dimensions: ' + Number(report.invalid_dimensions).toLocaleString()
      + '; below desktop resolution: ' + Number(report.below_desktop_resolution).toLocaleString()
      + '; missing metadata fields: ' + (report.metadata_fields_with_gaps || []).join(', ')
      + '; invalid source pages: ' + Number(report.source_page_invalid).toLocaleString()
      + '; license review/exclusion: ' + Number(report.license_review_or_exclusion).toLocaleString()
      + '; palette missing/excluded: ' + Number(palette.missing_records || 0).toLocaleString()
      + '/' + Number(palette.excluded_yellow_orange_brown_records || 0).toLocaleString()
      + '. License classes: ' + Object.entries(licenses).map(([name,count]) => name + ' ' + Number(count).toLocaleString()).join(', ')
      + '. Category range: ' + Number(categoryBalance.minimum_images || 0).toLocaleString()
      + '–' + Number(categoryBalance.maximum_images || 0).toLocaleString()
      + ' (observed spread ' + Number(categoryBalance.spread || 0).toLocaleString() + '). '
      + 'Storage: ' + storage + '. Categories: ' + categories + '. '
      + 'Metadata only: local folder and image bytes are not inspected.';
    $('wallpaper-public-library-audit-status').textContent =
      report.audit_status === 'clean' && report.population_state === 'closed'
        ? 'Audit complete: structurally clean; population closed.'
        : 'Audit complete: ' + report.audit_status + '; population ' + report.population_state + '.';
    toast('Public wallpaper library audit complete');
  } catch (error) {
    $('wallpaper-public-library-audit-status').textContent = error.message;
    toast(error.message);
  } finally { button.disabled = false; }
});

$('wallpaper-public-library-plan-button').addEventListener('click', async () => {
  const button = $('wallpaper-public-library-plan-button');
  button.disabled = true;
  $('wallpaper-public-library-plan-status').textContent = 'Reading the hub registry and validating every active volume manifest…';
  $('wallpaper-public-library-sync-button').disabled = true;
  state.publicLibraryPlan = null;
  try {
    const plan = await api('/api/doctor/wallpapers/public-library-plan', {
      method: 'POST',
      body: JSON.stringify({})
    });
    state.publicLibraryPlan = plan;
    $('wallpaper-public-library-summary').textContent =
      Number(plan.unique_images).toLocaleString() + ' globally unique images across '
      + plan.active_volumes.length + ' active volumes. '
      + Number(plan.already_present).toLocaleString() + ' are already present locally.';
    const metrics = $('wallpaper-public-library-metrics');
    metrics.replaceChildren();
    [
      ['Active volumes', plan.active_volumes.join(', '), 'Read from the canonical hub registry.'],
      ['Unique images', Number(plan.unique_images).toLocaleString(), 'Global SHA-256 deduplication across all active manifests.'],
      ['Already present', Number(plan.already_present).toLocaleString(), 'Locally matched by content hash.'],
      ['Missing images', Number(plan.selected_downloads).toLocaleString(), 'Images selected by this complete preview.'],
      ['Estimated transfer', (Number(plan.selected_download_bytes) / (1024 * 1024 * 1024)).toFixed(2) + ' GiB', 'Exact bytes reported by the manifests.'],
      ['Destination', plan.destination, 'The configured wallpaper.directory; existing files are preserved.']
    ].forEach(([title, value, detail]) => {
      const card = document.createElement('article'); card.className = 'metric-card';
      const label = document.createElement('span'); label.className = 'eyebrow'; label.textContent = title;
      const number = document.createElement('strong'); number.textContent = value;
      const help = document.createElement('small'); help.textContent = detail;
      card.append(label, number, help); metrics.append(card);
    });
    $('wallpaper-public-library-plan-status').textContent = plan.read_only
      ? 'Preview complete · no files, folders or private Catalog data were changed.'
      : 'Preview contract could not be verified.';
    $('wallpaper-public-library-sync-button').disabled =
      !plan.read_only || Number(plan.selected_downloads) === 0;
    toast(plan.selected_downloads ? 'Public wallpaper library preview ready' : 'Public wallpaper library already synchronized');
  } catch (error) {
    $('wallpaper-public-library-summary').textContent = error.message;
    $('wallpaper-public-library-plan-status').textContent = 'Preview failed.';
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});

$('wallpaper-public-library-sync-button').addEventListener('click', async () => {
  const plan = state.publicLibraryPlan;
  if (!plan || !plan.read_only || Number(plan.selected_downloads || 0) < 1) {
    toast('Run a fresh public-library preview before synchronizing.');
    return;
  }
  const transferGiB = Number(plan.selected_download_bytes) / (1024 * 1024 * 1024);
  const confirmText = 'Download ' + Number(plan.selected_downloads).toLocaleString()
    + ' missing wallpapers (' + transferGiB.toFixed(2) + ' GiB) from '
    + plan.active_volumes.length + ' active public volumes into ' + plan.destination + '? '
    + 'Files are hash-verified and existing files are never overwritten or deleted. This does not access the private Catalog.';
  if (!window.confirm(confirmText)) return;
  const button = $('wallpaper-public-library-sync-button');
  button.disabled = true;
  $('wallpaper-public-library-status').textContent = 'Starting public-library synchronization…';
  try {
    const result = await api('/api/doctor/wallpapers/public-library-sync', {
      method: 'POST',
      body: JSON.stringify({
        confirm: true,
        expected_downloads: plan.selected_downloads,
        expected_bytes: plan.selected_download_bytes
      })
    });
    state.publicLibraryPlan = null;
    if (result.started) {
      $('wallpaper-public-library-status').textContent =
        'Synchronization started for ' + Number(result.selected_downloads).toLocaleString() + ' images.';
      toast('Public wallpaper library synchronization started');
    } else {
      $('wallpaper-public-library-status').textContent = result.message || 'No missing public images.';
      toast('Public wallpaper library is already synchronized');
    }
    loadWallpapers();
  } catch (error) {
    $('wallpaper-public-library-status').textContent = error.message;
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});

$('wallpaper-sync-plan-button').addEventListener('click', async () => {
  const button = $('wallpaper-sync-plan-button');
  button.disabled = true;
  $('wallpaper-sync-plan-status').textContent = 'Inspecting all eligible accepted metadata and local filename conflicts…';
  state.wallpaperSyncPlan = null;
  $('wallpaper-sync-button').disabled = true;
  try {
    const plan = await api('/api/doctor/wallpapers/sync-plan', {
      method: 'POST', body: JSON.stringify({})
    });
    state.wallpaperSyncPlan = plan;
    $('wallpaper-sync-plan-status').textContent = plan.sync_allowed
      ? 'Preflight ready: ' + Number(plan.planned_new_copies).toLocaleString()
        + ' accepted assets ready to copy; complete metadata scan.'
      : (!plan.plan_complete
        ? 'Preflight incomplete: the technical metadata scan ceiling was reached. Synchronization is blocked.'
        : 'No new accepted assets are ready. Review the Catalog blockers.');
    toast(plan.sync_allowed ? 'Wallpaper sync preflight passed' : 'Wallpaper sync preflight blocked');
    loadWallpapers();
  } catch (error) {
    $('wallpaper-sync-plan-status').textContent = error.message;
    toast(error.message);
  } finally { button.disabled = false; }
});

$('wallpaper-sync-button').addEventListener('click', async () => {
  const plan = state.wallpaperSyncPlan;
  if (!plan || !plan.sync_allowed) {
    toast('Run a fresh read-only preflight before synchronization.');
    return;
  }
  const confirmText = 'Copy all ' + Number(plan.planned_new_copies).toLocaleString()
    + ' currently eligible, accepted, rights-approved and verified assets? '
    + 'The Catalog will revalidate each quarantine file before copying. '
    + 'No provider downloads, rights decisions or acceptance decisions are performed.';
  if (!window.confirm(confirmText)) return;
  try {
    await api('/api/doctor/wallpapers/sync', { method: 'POST', body: JSON.stringify({}) });
    state.wallpaperSyncPlan = null;
    $('wallpaper-sync-plan-status').textContent = 'Synchronization started. Refresh the inventory after it finishes.';
    toast('Wallpaper synchronization started');
    loadWallpapers();
    window.setTimeout(loadWallpapers, 1500);
  } catch (error) { toast(error.message); }
});

$('composer').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (state.sending) return;
  const prompt = $('prompt').value.trim();
  const model = $('model-select').value;
  if (!prompt) return;
  if (!model) { toast('Start Fenrir Doctor and install a local model first.'); return; }
  state.sending = true; $('send').disabled = true;
  if ($('messages').querySelector('.welcome')) $('messages').replaceChildren();
  $('messages').append(createMessage('user', prompt));
  const pending = document.createElement('div'); pending.className = 'pending'; pending.textContent = 'Fenrir Doctor is thinking…'; $('messages').append(pending); $('messages').scrollTop = $('messages').scrollHeight;
  $('prompt').value = '';
  try {
    const data = await api('/api/chat', { method: 'POST', body: JSON.stringify({ conversation_id: state.conversationId, model, message: prompt }) });
    state.conversationId = data.conversation_id;
    pending.remove(); $('messages').append(createMessage('assistant', data.answer, data.model)); $('messages').scrollTop = $('messages').scrollHeight;
    await refreshChats();
  } catch (error) {
    pending.remove(); $('messages').append(createMessage('assistant', `I couldn't complete that request. ${error.message}`));
    $('messages').scrollTop = $('messages').scrollHeight;
  } finally { state.sending = false; $('send').disabled = false; }
});

$('new-chat').addEventListener('click', () => { state.conversationId = null; appendConversation([]); showView('chat'); $('prompt').focus(); });
$('model-select').addEventListener('change', async () => {
  try {
    const settings = await api('/api/settings');
    await api('/api/settings', { method: 'POST', body: JSON.stringify({ default_model: $('model-select').value, location: settings.weather.location || '', latitude: settings.weather.latitude, longitude: settings.weather.longitude }) });
  } catch (error) { toast(error.message); }
});

document.addEventListener('click', async (event) => {
  const nav = event.target.closest('[data-view]');
  if (nav) return showView(nav.dataset.view);
  const prompt = event.target.closest('[data-prompt]');
  if (prompt) { $('prompt').value = prompt.dataset.prompt; $('prompt').focus(); return; }
  const view = event.target.closest('[data-open-view]');
  if (view) showView(view.dataset.openView);
  const restore = event.target.closest('[data-restore-backup]');
  if (restore) {
    if (!window.confirm('Restore backup ' + restore.dataset.restoreBackup + '? Current Fenrir configuration will first be snapshotted.')) return;
    try {
      const result = await api('/api/doctor/recovery', { method: 'POST', body: JSON.stringify({ backup_id: restore.dataset.restoreBackup }) });
      toast('Restored ' + result.restored.length + ' Fenrir configuration paths. Log out and back in to apply session changes.');
      loadDoctor();
    } catch (error) { toast(error.message); }
  }
});

async function loadPalette() {
  try {
    const palette = await api('/api/palette');
    const root = document.documentElement;
    root.style.setProperty('--accent', palette.accent || '#9b87f5');
    root.style.setProperty('--accent-soft', palette.accent_soft || '#51447f');
    root.style.setProperty('--accent-foreground', palette.accent_foreground || '#ffffff');
    root.style.setProperty('--selection-foreground', palette.selection_foreground || '#ffffff');
    root.style.setProperty('--foreground', palette.foreground || '#e8e9f2');
    root.style.setProperty('--muted', palette.muted || '#9699ab');
    root.style.setProperty('--surface-opacity', String(Math.max(.35, Math.min(.85, Number(palette.surface_opacity ?? .60)))));
  } catch (error) { console.warn('Default Fenrir Doctor palette retained:', error); }
}

async function refreshHealth() {
  try {
    const data = await api('/api/health');
    $('service-status').textContent = data.ollama ? (data.models.length ? `${data.models.length} local model${data.models.length === 1 ? '' : 's'} ready` : 'Ollama online · no models') : 'Local model offline';
    $('service-status').parentElement.classList.toggle('offline', !data.ollama);
    if (data.ollama && data.models.length && !state.models.length) loadModels();
  } catch (error) { $('service-status').textContent = 'Local model offline'; }
  loadSystem();
}

(async function boot() {
  renderEmptyChat();
  await loadPalette();
  await Promise.all([loadModels(), refreshChats(), loadWeather(), loadSystem()]);
  window.setInterval(loadPalette, 60000);
  window.setInterval(refreshHealth, 6000);
  window.setInterval(refreshChats, 30000);
  window.setInterval(() => { if (state.view === 'doctor') loadDoctor(); if (state.view === 'wallpapers') loadWallpapers(); }, 30000);
})();
