'use strict';

const $ = (id) => document.getElementById(id);
const state = { view: 'chat', conversationId: null, models: [], chats: [], sending: false, weather: null, wallpaperTarget: 5000, wallpaperSchedule: null };
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
      ['Selected target', Number(data.target_count).toLocaleString(), data.target_reached ? 'Target reached' : Number(data.remaining).toLocaleString() + ' more images to reach target.']
    ].forEach(([title, value, detail]) => {
      const card = document.createElement('article'); card.className = 'metric-card';
      const label = document.createElement('span'); label.className = 'eyebrow'; label.textContent = title;
      const number = document.createElement('strong'); number.textContent = value;
      const help = document.createElement('small'); help.textContent = detail;
      card.append(label, number, help); metrics.append(card);
    });
    state.wallpaperTarget = data.target_count || state.wallpaperTarget;
    $('wallpaper-target').value = String(state.wallpaperTarget);
    const sync = data.sync || {};
    $('wallpaper-sync-button').disabled = Boolean(sync.running) || !data.catalog_available || !data.sync_destination_allowed;
    $('wallpaper-sync-button').textContent = sync.running ? 'Synchronization running…' : 'Sync accepted wallpapers';
    $('wallpaper-sync-status').textContent = sync.running ? 'Copying verified local assets…' : (sync.returncode === 0 ? 'Last synchronization completed.' : (sync.returncode ? 'Synchronization stopped (exit ' + sync.returncode + ').' : 'Ready'));
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
    $('wallpaper-schedule-interval').disabled = Boolean(schedule.enabled);
    $('wallpaper-source').disabled = Boolean(schedule.enabled);
    $('wallpaper-profile').disabled = Boolean(schedule.enabled);
    $('wallpaper-contact').disabled = Boolean(schedule.enabled);
    const scheduleButton = $('wallpaper-schedule-button');
    scheduleButton.textContent = schedule.enabled ? 'Pause automatic discovery' : 'Enable automatic discovery';
    scheduleButton.disabled = !schedule.enabled && !data.catalog_available;
    if (schedule.enabled) {
      const next = schedule.next_run_at
        ? new Date(schedule.next_run_at * 1000).toLocaleString()
        : 'when the current slice finishes';
      $('wallpaper-schedule-status').textContent = 'Automatic discovery active · next slice ' + next;
    } else if (schedule.last_status === 'needs_review') {
      $('wallpaper-schedule-status').textContent = 'Paused for human rights review and acceptance.';
    } else if (schedule.last_status === 'paused_error' || schedule.last_status === 'invalid') {
      $('wallpaper-schedule-status').textContent = 'Stopped safely: ' + (schedule.last_error || schedule.pause_reason || 'inspect scheduler status');
    } else if (schedule.last_status === 'paused') {
      $('wallpaper-schedule-status').textContent = 'Automatic discovery paused. A running slice is allowed to finish.';
    } else {
      $('wallpaper-schedule-status').textContent = 'Automatic discovery is off.';
    }
    if (schedule.enabled) $('wallpaper-discover-button').disabled = true;
    updateCommonsContactVisibility();
  } catch (error) { if (showError) toast(error.message); }
}

async function loadSettings() {
  try {
    const data = await api('/api/settings');
    $('settings-model').value = data.default_model || $('model-select').value;
    $('weather-location').value = data.weather.location || '';
    $('weather-latitude').value = data.weather.latitude ?? '';
    $('weather-longitude').value = data.weather.longitude ?? '';
    state.wallpaperTarget = data.wallpaper_target_count || 5000;
    if ($('wallpaper-target')) $('wallpaper-target').value = String(state.wallpaperTarget);
  } catch (error) { toast(error.message); }
}

$('settings-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    default_model: $('settings-model').value,
    location: $('weather-location').value,
    latitude: $('weather-latitude').value,
    longitude: $('weather-longitude').value,
    wallpaper_target_count: state.wallpaperTarget,
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

$('wallpaper-target').addEventListener('change', async () => {
  state.wallpaperTarget = Number($('wallpaper-target').value);
  try {
    const settings = await api('/api/settings');
    await api('/api/settings', { method: 'POST', body: JSON.stringify({
      default_model: settings.default_model || '',
      location: settings.weather.location || '',
      latitude: settings.weather.latitude,
      longitude: settings.weather.longitude,
      wallpaper_target_count: state.wallpaperTarget
    })});
    toast('Wallpaper target saved');
    loadWallpapers();
  } catch (error) { toast(error.message); }
});

function updateCommonsContactVisibility() {
  const group = $('commons-contact-group');
  if (group) group.classList.toggle('hidden', $('wallpaper-source').value !== 'wikimedia_commons');
}

$('wallpaper-source').addEventListener('change', updateCommonsContactVisibility);

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
      : 'Run the full bounded Wikimedia Commons metadata profile using this contact identifier? It may take several minutes. No image files will be downloaded or accepted.');
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

  const source = $('wallpaper-source').value;
  const profile = $('wallpaper-profile').value;
  const contact = $('wallpaper-contact').value.trim();
  if (source === 'wikimedia_commons' && !contact) {
    toast('Enter a contact email or project URL for Wikimedia Commons.');
    $('wallpaper-contact').focus();
    return;
  }
  const interval = Number($('wallpaper-schedule-interval').value);
  if (!window.confirm('Enable automatic ' + source + ' metadata discovery every '
      + (interval / 60) + ' hour(s)? Each run is sequential and bounded. No image files will be downloaded, licensed, accepted or synchronized. The scheduler stops for human review when discovery is complete.')) return;

  const button = $('wallpaper-schedule-button');
  button.disabled = true;
  $('wallpaper-schedule-status').textContent = 'Starting the first bounded metadata slice…';
  try {
    const result = await api('/api/doctor/wallpapers/schedule', {
      method: 'POST',
      body: JSON.stringify({
        enabled: true,
        source,
        profile,
        contact: source === 'wikimedia_commons' ? contact : null,
        interval_minutes: interval
      })
    });
    state.wallpaperSchedule = result;
    toast('Automatic wallpaper discovery enabled');
    loadWallpapers();
  } catch (error) {
    $('wallpaper-schedule-status').textContent = error.message;
    button.disabled = false;
    toast(error.message);
  }
});

$('wallpaper-sync-button').addEventListener('click', async () => {
  if (!window.confirm('Copy catalog-approved wallpapers into your local folder until the ' + Number(state.wallpaperTarget).toLocaleString() + ' image target is reached? This does not publish or upload images.')) return;
  try {
    await api('/api/doctor/wallpapers/sync', { method: 'POST', body: JSON.stringify({ target_count: state.wallpaperTarget }) });
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
    await api('/api/settings', { method: 'POST', body: JSON.stringify({ default_model: $('model-select').value, location: settings.weather.location || '', latitude: settings.weather.latitude, longitude: settings.weather.longitude, wallpaper_target_count: state.wallpaperTarget }) });
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
