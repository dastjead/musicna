/* musicna 실시간 뷰 — /ws/live 구독, 코드 표시 + 스크롤 피아노 롤 */

"use strict";

const SPAN_S = 30; // 피아노 롤 표시 창
const PITCH_MIN = 24, PITCH_MAX = 96;

const $ = (sel) => document.querySelector(sel);
const state = {
  notes: [], // {pitch, start_s, end_s|null, index}
  chords: [], // {chord, start_s}
  clock_s: 0, // 트랙 기준 최신 시각 (이벤트로 갱신)
  clockUpdatedAt: performance.now(),
};

/* ── WebSocket (자동 재접속) ─────────────── */
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onopen = () => setConn(true);
  ws.onclose = () => {
    setConn(false);
    setTimeout(connect, 2000);
  };
  ws.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
}
function setConn(on) {
  $("#dot").classList.toggle("on", on);
  $("#conn").textContent = on ? "연결됨" : "재연결 중…";
}

function bumpClock(t) {
  if (t > state.clock_s) {
    state.clock_s = t;
    state.clockUpdatedAt = performance.now();
  }
}

function handleEvent(ev) {
  switch (ev.type) {
    case "track_started":
      state.notes = [];
      state.chords = [];
      state.clock_s = 0;
      break;
    case "note_on":
      state.notes.push({ pitch: ev.pitch, start_s: ev.start_s, end_s: null, index: ev.index });
      bumpClock(ev.start_s);
      break;
    case "note_off": {
      const note = state.notes.findLast((n) => n.index === ev.index && n.end_s === null);
      if (note) note.end_s = ev.end_s;
      bumpClock(ev.end_s);
      break;
    }
    case "chord":
      state.chords.push(ev);
      bumpClock(ev.start_s);
      renderChords();
      break;
    case "progress":
      bumpClock(ev.chunk_end_s);
      break;
  }
}

function renderChords() {
  const last = state.chords[state.chords.length - 1];
  const nowEl = $("#chord-now");
  nowEl.textContent = last ? last.chord : "—";
  nowEl.classList.toggle("muted", !last);
  const history = state.chords.slice(-12, -1).map((c) => c.chord);
  $("#chord-history").innerHTML = history.length
    ? history.join('<span class="muted"> → </span>') + '<span class="muted"> → </span>'
    : "";
}

/* ── 피아노 롤 (canvas) ──────────────────── */
const canvas = $("#roll");
const ctx = canvas.getContext("2d");

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w * dpr) {
    canvas.width = w * dpr;
    canvas.height = h * dpr;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // 시계: 마지막 이벤트 이후 벽시계로 보간 (전사 지연만큼 뒤따라감)
  const now = state.clock_s + (performance.now() - state.clockUpdatedAt) / 1000;
  const left = now - SPAN_S;

  ctx.fillStyle = cssVar("--surface");
  ctx.fillRect(0, 0, w, h);

  // 옥타브 가이드라인 (C마다)
  ctx.strokeStyle = cssVar("--grid");
  ctx.lineWidth = 1;
  for (let p = PITCH_MIN; p <= PITCH_MAX; p += 12) {
    const y = h - ((p - PITCH_MIN) / (PITCH_MAX - PITCH_MIN)) * h;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // 노트 — 단일 계열(파랑), 울리는 중인 노트는 현재 시각까지 연장
  ctx.fillStyle = cssVar("--mood-fill");
  let visible = 0;
  for (const n of state.notes) {
    const end = n.end_s ?? now;
    if (end < left || n.pitch < PITCH_MIN || n.pitch > PITCH_MAX) continue;
    visible += 1;
    const x0 = Math.max(((n.start_s - left) / SPAN_S) * w, 0);
    const x1 = Math.min(((end - left) / SPAN_S) * w, w);
    const y = h - ((n.pitch - PITCH_MIN) / (PITCH_MAX - PITCH_MIN)) * h;
    ctx.beginPath();
    ctx.roundRect(x0, y - 2.5, Math.max(x1 - x0, 2), 5, 2);
    ctx.fill();
  }

  // 오래된 노트 정리
  if (state.notes.length > 4000) {
    state.notes = state.notes.filter((n) => (n.end_s ?? now) >= left);
  }

  const mm = Math.floor(now / 60), ss = String(Math.max(0, Math.floor(now % 60))).padStart(2, "0");
  $("#clock").textContent = `${mm}:${ss}`;
  $("#note-count").textContent = `노트 ${visible}`;
  requestAnimationFrame(draw);
}

connect();
requestAnimationFrame(draw);
