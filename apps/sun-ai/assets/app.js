'use strict';

const $ = (id) => document.getElementById(id);
const state = { view: 'chat', conversationId: null, models: [], chats: [], sending: false, weather: null };
const views = ['chat', 'weather', 'system', 'history', 'settings'];

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
  const titles = { chat: ['YOUR WORKSPACE', 'Chat'], weather: ['YOUR LOCAL FORECAST', 'Weather'], system: ['LIVE HARDWARE TELEMETRY', 'System'], history: ['YOUR PRIVATE ARCHIVE', 'History'], settings: ['PERSONALIZE SUN AI', 'Settings'] };
  $('view-eyebrow').textContent = titles[name][0];
  $('view-title').textContent = titles[name][1];
  if (name === 'weather') loadWeather(true);
  if (name === 'system') loadSystem(true);
  if (name === 'history') renderHistory();
  if (name === 'settings') loadSettings();
}

function createMessage(role, content, model = '') {
  const wrapper = document.createElement('article');
  wrapper.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'YOU' : (model ? `SUN AI · ${model}` : 'SUN AI');
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
  const heading = document.createElement('h2'); heading.textContent = 'Hello. I\'m Sun AI.';
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

$('composer').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (state.sending) return;
  const prompt = $('prompt').value.trim();
  const model = $('model-select').value;
  if (!prompt) return;
  if (!model) { toast('Start Sun AI and install a local model first.'); return; }
  state.sending = true; $('send').disabled = true;
  if ($('messages').querySelector('.welcome')) $('messages').replaceChildren();
  $('messages').append(createMessage('user', prompt));
  const pending = document.createElement('div'); pending.className = 'pending'; pending.textContent = 'Sun AI is thinking…'; $('messages').append(pending); $('messages').scrollTop = $('messages').scrollHeight;
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

document.addEventListener('click', (event) => {
  const nav = event.target.closest('[data-view]');
  if (nav) return showView(nav.dataset.view);
  const prompt = event.target.closest('[data-prompt]');
  if (prompt) { $('prompt').value = prompt.dataset.prompt; $('prompt').focus(); return; }
  const view = event.target.closest('[data-open-view]');
  if (view) showView(view.dataset.openView);
});

async function loadPalette() {
  try {
    const palette = await api('/api/palette');
    const root = document.documentElement;
    root.style.setProperty('--accent', palette.accent || '#9b87f5');
    root.style.setProperty('--accent-soft', palette.accent_soft || '#51447f');
    root.style.setProperty('--foreground', palette.foreground || '#e8e9f2');
    root.style.setProperty('--muted', palette.muted || '#9699ab');
    root.style.setProperty('--surface-opacity', String(Math.max(.35, Math.min(.85, Number(palette.surface_opacity ?? .60)))));
  } catch (error) { console.warn('Default Sun AI palette retained:', error); }
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
})();
