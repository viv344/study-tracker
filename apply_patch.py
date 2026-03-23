#!/usr/bin/env python3
"""Applies the next pending patch to index.html."""
import os, sys

TRACKER = os.path.join(os.path.dirname(__file__), 'patch_idx.txt')
HTML    = os.path.join(os.path.dirname(__file__), 'index.html')

# Each patch: (commit_message, old_string, new_string)
PATCHES = [
    (
        "add streak counter to header",
        '<span id="exam-pill" class="pill"></span>',
        '<span id="exam-pill" class="pill"></span>\n      <span id="streak-pill" class="pill" style="background:#0ea5e9"></span>',
    ),
    (
        "show streak count in header",
        'function updatePill() {',
        '''function getStreak() {
  const sorted = Object.keys(data.schedule).sort().reverse();
  const today  = todayStr();
  let streak   = 0;
  for (const ds of sorted) {
    if (ds > today) continue;
    const day = data.schedule[ds];
    if (!day || day._rest) continue;
    const hasTime = Object.values(day).some(e => e && elapsedMs(e) > 0);
    if (!hasTime) break;
    streak++;
  }
  return streak;
}
function updatePill() {''',
    ),
    (
        "wire streak pill display",
        "pill.textContent  = 'Exams!';",
        "pill.textContent  = 'Exams!';\n  const sp = document.getElementById('streak-pill');\n  if (sp) { const st = getStreak(); sp.textContent = st > 0 ? `🔥 ${st}d streak` : ''; sp.style.display = st > 0 ? '' : 'none'; }",
    ),
    (
        "add keyboard shortcut s to start/stop timer",
        "render();\nsetInterval(tickTimers, 1000);",
        """render();
setInterval(tickTimers, 1000);
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA') return;
  if (e.key === 's') {
    const today = todayStr();
    const running = BLOCK_DEFS.find(b => getEntry(today, b.id)?.running);
    if (running) doStopTimer(today, running.id);
    else { const first = BLOCK_DEFS.find(b => getEntry(today, b.id)); if (first) doStartTimer(today, first.id); }
  }
});""",
    ),
    (
        "highlight overdue sessions in today view",
        "const color= s.color || '#6b7280';",
        "const color= s.color || '#6b7280';\n    const ms2 = elapsedMs(e);\n    const overdue = ms2 === 0;",
    ),
    (
        "add total hours logged to header",
        '<h1>Study Tracker</h1>',
        '<h1>Study Tracker</h1>\n      <span id="total-pill" class="pill" style="background:var(--surface2);color:var(--muted);border:1px solid var(--border)"></span>',
    ),
    (
        "wire total hours pill",
        "if (sp) { const st = getStreak();",
        "const tp = document.getElementById('total-pill'); if (tp) { const tot = Object.values(data.schedule).flatMap(d=>Object.values(d)).reduce((a,e)=>a+(e&&e.timeMs?e.timeMs:0),0); tp.textContent = tot>0?fmtHours(tot)+' logged':''; }\n  if (sp) { const st = getStreak();",
    ),
    (
        "add focus tip below module name in today view",
        "${mod ? `<div style=\"margin-top:4px;font-size:0.8rem;font-weight:600;color:${color}\">${mod}</div>` : ''}",
        "${mod ? `<div style=\"margin-top:4px;font-size:0.8rem;font-weight:600;color:${color}\">${mod}</div><div style=\"font-size:0.72rem;color:var(--muted);margin-top:2px\">Close tabs. 25 min on, 5 min off.</div>` : ''}",
    ),
    (
        "soften card border radius",
        '--radius:   12px;',
        '--radius:   14px;',
    ),
    (
        "add subtle gradient to header",
        'background: var(--surface);',
        'background: linear-gradient(135deg, var(--surface) 0%, #1a2540 100%);',
    ),
    (
        "increase timer font size slightly",
        'font-size: 2rem;',
        'font-size: 2.2rem;',
    ),
    (
        "add placeholder hint to notes textarea",
        'placeholder="What did you cover?"',
        'placeholder="What did you cover? Key formulas, weak spots, questions for review..."',
    ),
    (
        "add days studied count to stats view",
        'let html = `<div style="font-size:1.1rem;font-weight:700;margin-bottom:1.25rem">Subject Progress</div>`;',
        '''const studiedDays = Object.entries(data.schedule).filter(([ds,day])=>!day._rest&&Object.values(day).some(e=>e&&elapsedMs(e)>0)).length;
  let html = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem"><div style="font-size:1.1rem;font-weight:700">Subject Progress</div><div style="font-size:0.85rem;color:var(--muted)">${studiedDays} day${studiedDays!==1?'s':''} studied</div></div>`;''',
    ),
    (
        "add rest day toggle button to today view",
        "let html = `<div style=\"font-size:1.1rem;font-weight:700;margin-bottom:1.25rem\">${label}${termBadge}</div>`;",
        """const isRest = isRestDay(today);
  let html = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem">
    <div style="font-size:1.1rem;font-weight:700">${label}${termBadge}</div>
    <button class="btn btn-ghost btn-sm" onclick="toggleRest('${today}')">${isRest?'Resume day':'Mark as rest day'}</button>
  </div>`;""",
    ),
    (
        "add toggleRest function",
        "function resetData() {",
        """function toggleRest(ds) {
  if (!data.schedule[ds]) return;
  if (data.schedule[ds]._rest) {
    delete data.schedule[ds]._rest;
    // re-generate blocks for this day
    const d   = parseDate(ds);
    const subj = DAY_CYCLE[Object.keys(data.schedule).sort().indexOf(ds) % DAY_CYCLE.length] || 'B14';
    BLOCK_DEFS.forEach(blk => { if (!data.schedule[ds][blk.id]) data.schedule[ds][blk.id] = newEntry(subj); });
  } else {
    data.schedule[ds] = { _rest: true };
  }
  save(); render();
}
function resetData() {""",
    ),
    (
        "add exam countdown bar below header",
        '<main class="main" id="main"></main>',
        '''<main class="main" id="main"></main>
  <div id="exam-bar" style="position:fixed;bottom:0;left:0;right:0;height:3px;background:var(--surface2);z-index:100">
    <div id="exam-bar-fill" style="height:100%;background:var(--accent);transition:width 0.5s"></div>
  </div>''',
    ),
    (
        "wire exam progress bar",
        "updatePill();",
        """updatePill();
  const total = (parseDate(EXAM_START) - parseDate(HOLIDAY_START)) / 86400000;
  const done  = (parseDate(todayStr()) - parseDate(HOLIDAY_START)) / 86400000;
  const pct   = Math.min(100, Math.max(0, (done / total) * 100));
  const fill  = document.getElementById('exam-bar-fill');
  if (fill) fill.style.width = pct + '%';""",
    ),
    (
        "add motivational quote below date in today view",
        "for (const blk of blocks) {",
        """const QUOTES = [
    'The secret of getting ahead is getting started.',
    'Push yourself, because no one else is going to do it for you.',
    'Great things never come from comfort zones.',
    'Stay focused and never give up.',
    'Believe you can and you\'re halfway there.',
  ];
  html += `<div style="font-size:0.8rem;color:var(--muted);margin-bottom:1.25rem;font-style:italic">"${QUOTES[new Date().getDay() % QUOTES.length]}"</div>`;
  for (const blk of blocks) {""",
    ),
    (
        "tweak muted colour for better contrast",
        '--muted:    #94a3b8;',
        '--muted:    #a0aec0;',
    ),
    (
        "add block completion checkmark when time logged",
        '${e.running ? `<div class="wg-running-dot"></div>` : \'\'}',
        '${e.running ? `<div class="wg-running-dot"></div>` : (ms>3600000 ? `<div style="position:absolute;top:3px;right:5px;color:var(--green);font-size:0.7rem">✓</div>` : \'\')}',
    ),
]

def main():
    idx = 0
    if os.path.exists(TRACKER):
        with open(TRACKER) as f:
            try: idx = int(f.read().strip())
            except: idx = 0

    if idx >= len(PATCHES):
        print("All patches applied.")
        sys.exit(1)

    msg, old, new = PATCHES[idx]

    with open(HTML, 'r') as f:
        content = f.read()

    if old not in content:
        print(f"Patch {idx} old string not found, skipping.")
        with open(TRACKER, 'w') as f:
            f.write(str(idx + 1))
        sys.exit(1)

    with open(HTML, 'w') as f:
        f.write(content.replace(old, new, 1))

    with open(TRACKER, 'w') as f:
        f.write(str(idx + 1))

    print(msg)

if __name__ == '__main__':
    main()
