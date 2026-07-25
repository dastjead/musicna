/* musicna 웹 UI — /tracks API(AnalysisResult[])만 사용하는 순수 클라이언트 */

"use strict";

const SECTION_SLOTS = {
  verse: "--sec-verse",
  chorus: "--sec-chorus",
  bridge: "--sec-bridge",
  intro: "--sec-intro",
  outro: "--sec-outro",
  solo: "--sec-solo",
  inst: "--sec-inst",
  break: "--sec-break",
};
const sectionColor = (label) => `var(${SECTION_SLOTS[label] ?? "--sec-other"})`;

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const fmtTime = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const KEY_MODE = { major: "장조", minor: "단조" };

function trackDuration(t) {
  const ends = [t.track.duration_s ?? 0]
    .concat(t.sections.map((s) => s.end_s))
    .concat(t.chords.map((c) => c.end_s));
  return Math.max(...ends, 1);
}

/* ── 툴팁 ─────────────────────────────────── */
const tooltip = $("#tooltip");
function bindTooltip(node, html) {
  node.addEventListener("mousemove", (e) => {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    const pad = 12;
    const x = Math.min(e.clientX + pad, window.innerWidth - tooltip.offsetWidth - pad);
    const y = Math.min(e.clientY + pad, window.innerHeight - tooltip.offsetHeight - pad);
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
  });
  node.addEventListener("mouseleave", () => (tooltip.hidden = true));
}

/* ── 타임라인 ─────────────────────────────── */
function renderAxis(duration) {
  const axis = el("div", "axis");
  const step = [5, 10, 15, 30, 60, 120, 300].find((s) => duration / s <= 8) ?? 600;
  for (let t = 0; t <= duration; t += step) {
    const tick = el("span", "tick", fmtTime(t));
    tick.style.left = `${(t / duration) * 100}%`;
    axis.appendChild(tick);
  }
  return axis;
}

function renderSectionLane(track, duration) {
  const lane = el("div", "lane");
  for (const s of track.sections) {
    const seg = el("div", "seg", s.label); // 직접 라벨 — 대비 완화 규칙
    seg.style.left = `${(s.start_s / duration) * 100}%`;
    seg.style.width = `${((s.end_s - s.start_s) / duration) * 100}%`;
    seg.style.background = sectionColor(s.label);
    bindTooltip(
      seg,
      `<div class="t-title">${s.label}</div>
       <div class="t-sub">${fmtTime(s.start_s)}–${fmtTime(s.end_s)} (${(s.end_s - s.start_s).toFixed(1)}초)</div>`
    );
    lane.appendChild(seg);
  }
  return lane;
}

function renderChordLane(track, duration) {
  const lane = el("div", "lane");
  for (const c of track.chords) {
    const seg = el("div", "seg chord", c.chord);
    seg.style.left = `${(c.start_s / duration) * 100}%`;
    seg.style.width = `${((c.end_s - c.start_s) / duration) * 100}%`;
    const conf = c.confidence != null ? ` · 신뢰도 ${(c.confidence * 100).toFixed(0)}%` : "";
    bindTooltip(
      seg,
      `<div class="t-title">${c.chord}</div>
       <div class="t-sub">${fmtTime(c.start_s)}–${fmtTime(c.end_s)} · ${c.source}${conf}</div>`
    );
    lane.appendChild(seg);
  }
  return lane;
}

/* ── 상세 패널 ────────────────────────────── */
function renderDetail(t) {
  const detail = $("#detail");
  detail.replaceChildren();

  const meta = t.track;
  detail.appendChild(el("h2", null, meta.title));
  const line = el("p", "meta-line");
  const parts = [meta.artist, meta.album, meta.source, meta.captured_at?.replace("T", " ").slice(0, 16)];
  line.append(...parts.filter(Boolean).flatMap((p, i) => (i ? [el("span", "sep", "·"), p] : [p])));
  detail.appendChild(line);

  // 스탯 타일
  const stats = el("div", "stat-row");
  const tile = (label, value, sub) => {
    const d = el("div", "stat-tile");
    d.appendChild(el("div", "label", label));
    const v = el("div", "value", value);
    if (sub) {
      const s = el("small", null, ` ${sub}`);
      v.appendChild(s);
    }
    d.appendChild(v);
    return d;
  };
  stats.appendChild(tile("BPM", t.bpm != null ? String(Math.round(t.bpm)) : "—"));
  stats.appendChild(tile("키", t.key ?? "—", t.mode ? KEY_MODE[t.mode] ?? t.mode : ""));
  stats.appendChild(tile("길이", fmtTime(trackDuration(t))));
  stats.appendChild(tile("코드 수", String(t.chords.length)));
  detail.appendChild(stats);

  const duration = trackDuration(t);

  // 곡 구조
  const secPanel = el("section", "panel");
  secPanel.appendChild(el("h3", null, "곡 구조"));
  if (t.sections.length) {
    secPanel.appendChild(renderSectionLane(t, duration));
    secPanel.appendChild(renderAxis(duration));
    const legend = el("div", "legend");
    for (const label of [...new Set(t.sections.map((s) => s.label))]) {
      const key = el("span", "key");
      const sw = el("span", "swatch");
      sw.style.background = sectionColor(label);
      key.append(sw, label);
      legend.appendChild(key);
    }
    secPanel.appendChild(legend);
    secPanel.appendChild(tableView("구간 표 보기", ["구간", "시작", "끝"],
      t.sections.map((s) => [s.label, fmtTime(s.start_s), fmtTime(s.end_s)])));
  } else {
    secPanel.appendChild(el("p", "muted", "구조 분석 없음 (allin1 extra 필요)"));
  }
  detail.appendChild(secPanel);

  // 코드 진행
  const chordPanel = el("section", "panel");
  chordPanel.appendChild(el("h3", null, "코드 진행"));
  if (t.chords.length) {
    chordPanel.appendChild(renderChordLane(t, duration));
    chordPanel.appendChild(renderAxis(duration));
    const strip = el("p", "chord-strip");
    strip.innerHTML = t.chords
      .map((c) => `<b>${c.chord}</b>`)
      .join('<span class="muted"> → </span>');
    chordPanel.appendChild(strip);
    chordPanel.appendChild(tableView("코드 표 보기", ["코드", "시작", "끝", "출처", "신뢰도"],
      t.chords.map((c) => [c.chord, fmtTime(c.start_s), fmtTime(c.end_s), c.source,
        c.confidence != null ? c.confidence.toFixed(2) : "—"])));
  } else {
    chordPanel.appendChild(el("p", "muted", "코드 없음 (MIDI 전사 필요)"));
  }
  detail.appendChild(chordPanel);

  // 무드
  const moodPanel = el("section", "panel");
  moodPanel.appendChild(el("h3", null, "무드"));
  if (t.moods.length) {
    for (const m of [...t.moods].sort((a, b) => b.score - a.score)) {
      const row = el("div", "mood-row");
      row.appendChild(el("span", "name", m.tag));
      const bar = el("div", "bar");
      const fill = el("div", "fill");
      fill.style.width = `${(m.score * 100).toFixed(0)}%`;
      bar.appendChild(fill);
      row.appendChild(bar);
      row.appendChild(el("span", "score", m.score.toFixed(2)));
      moodPanel.appendChild(row);
    }
  } else {
    moodPanel.appendChild(el("p", "muted", "무드 분석 없음 (mood extra 필요)"));
  }
  detail.appendChild(moodPanel);

  // 엔진 버전
  const engines = Object.entries(t.engine_versions ?? {});
  if (engines.length) {
    const p = el("p", "muted");
    p.style.fontSize = "11px";
    p.textContent = `분석 엔진: ${engines.map(([k, v]) => `${k} ${v}`).join(", ")}` +
      (t.analyzed_at ? ` · 분석 시각 ${t.analyzed_at.replace("T", " ").slice(0, 16)}` : "");
    detail.appendChild(p);
  }
}

function tableView(summary, headers, rows) {
  const details = el("details", "table-view");
  details.appendChild(el("summary", null, summary));
  const table = el("table");
  const thead = el("thead");
  const hr = el("tr");
  headers.forEach((h) => hr.appendChild(el("th", null, h)));
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    row.forEach((cell) => tr.appendChild(el("td", null, cell)));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  details.appendChild(table);
  return details;
}

/* ── 트랙 목록 ────────────────────────────── */
function renderList(tracks) {
  const list = $("#track-list");
  list.replaceChildren();
  $("#track-count").textContent = tracks.length ? `${tracks.length}곡` : "";

  if (!tracks.length) {
    const hint = el("div", "empty-hint muted");
    hint.style.padding = "24px 16px";
    hint.innerHTML =
      "아직 분석된 곡이 없습니다.<br><br>" +
      "<code>uv run musicna-session --source spotify</code>로 캡처 후<br>" +
      "<code>uv run musicna-analyze</code>를 실행하세요.";
    list.appendChild(hint);
    $("#detail").replaceChildren(el("p", "muted empty-hint", "트랙을 선택하세요."));
    return;
  }

  tracks.forEach((t, i) => {
    const item = el("button", "track-item");
    item.type = "button";
    item.appendChild(el("div", "title", t.track.title));
    item.appendChild(el("div", "sub", t.track.artist ?? ""));
    const badges = el("div", "badges");
    if (t.key) badges.appendChild(el("span", "badge", `${t.key} ${KEY_MODE[t.mode] ?? ""}`.trim()));
    if (t.bpm != null) badges.appendChild(el("span", "badge", `${Math.round(t.bpm)} BPM`));
    const topMood = [...t.moods].sort((a, b) => b.score - a.score)[0];
    if (topMood) badges.appendChild(el("span", "badge", topMood.tag));
    item.appendChild(badges);
    item.addEventListener("click", () => {
      list.querySelectorAll(".selected").forEach((n) => n.classList.remove("selected"));
      item.classList.add("selected");
      renderDetail(t);
    });
    list.appendChild(item);
    if (i === 0) item.click();
  });
}

async function load() {
  try {
    const res = await fetch("/tracks");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderList(await res.json());
  } catch (err) {
    $("#detail").replaceChildren(el("p", "muted empty-hint", `트랙을 불러오지 못했습니다: ${err.message}`));
  }
}

$("#refresh").addEventListener("click", load);
load();
