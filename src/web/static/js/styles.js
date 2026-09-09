// The right-hand Style sidebar: global figure style (font, title, legend,
// gridlines) and per-panel style (x/y limits, tick step) for whichever
// panel is "active" -- selected by clicking its title in the left PANELS
// tree, or from the dropdown here.
const StyleSidebar = (() => {
  const MAX_TICKS = 200;   // a runaway dtick (e.g. 0.1 over a 230 s axis) can hang Plotly's render
  const COLLAPSE_KEY = 'flexflow.styleSidebar.collapsed';

  // Purely a UI preference (which sections are open), not plot data -- kept
  // out of the workspace object and in its own localStorage entry instead.
  function loadCollapsed() {
    try {
      const raw = localStorage.getItem(COLLAPSE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* private mode, cleared storage, etc. */ }
    return {};
  }
  let collapsed = loadCollapsed();

  function toggleGroup(name) {
    collapsed[name] = !collapsed[name];
    try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed)); } catch (e) { /* ignore */ }
    render();
  }

  function group(name, heading, bodyHtml) {
    const isCollapsed = !!collapsed[name];
    return `
      <div class="style-group">
        <div class="style-group-heading" data-group="${name}">
          <span class="style-group-arrow">${isCollapsed ? '&#9656;' : '&#9662;'}</span> ${heading}
        </div>
        <div class="style-group-body" ${isCollapsed ? 'hidden' : ''}>${bodyHtml}</div>
      </div>
    `;
  }

  const FONTS = [
    ['', 'Default'],
    ['Arial, sans-serif', 'Arial'],
    ['Helvetica, Arial, sans-serif', 'Helvetica'],
    ['Georgia, serif', 'Georgia'],
    ['"Times New Roman", Times, serif', 'Times New Roman'],
    ['"Courier New", Courier, monospace', 'Courier New'],
    ['Verdana, sans-serif', 'Verdana'],
    ['"Trebuchet MS", sans-serif', 'Trebuchet MS'],
    ['"Segoe UI", Roboto, sans-serif', 'Segoe UI'],
    ['"DejaVu Sans Mono", monospace', 'Monospace'],
  ];
  const LINE_STYLES = [
    ['', 'Solid'], ['dash', 'Dashed'], ['dot', 'Dotted'], ['dashdot', 'Dash-dot'],
  ];
  const MARKERS = [
    ['', 'Default'], ['none', 'None'], ['circle', 'Circle'], ['square', 'Square'],
    ['diamond', 'Diamond'], ['cross', 'Cross'], ['x', 'X'], ['triangle-up', 'Triangle'],
  ];

  function activePanel(ws) {
    return ws.panels.find(p => p.id === ws.activePanelId) || ws.panels[0];
  }

  // Escapes a value for use inside an HTML attribute -- FONTS' CSS
  // font-family stacks carry embedded double quotes ('"Times New Roman",
  // Times, serif'), which unescaped terminate the value="..." attribute
  // right there: the browser reads value="" (empty, same as Default) and
  // the rest of the string as bogus trailing attributes, so every font
  // whose stack quotes its name was silently unselectable -- picking
  // "Times New Roman" always saved '' regardless, no error anywhere.
  function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  }

  function options(pairs, current) {
    return pairs.map(([value, label]) =>
      `<option value="${escapeAttr(value)}" ${value === (current || '') ? 'selected' : ''}>${label}</option>`
    ).join('');
  }

  const numberOrNull = (v) => (v.trim() === '' ? null : parseFloat(v));

  function render() {
    const ws = PlotWorkspace.state();
    const box = document.getElementById('style-body');
    const g = ws.style || {};

    const globalBody = `
      <div class="style-row">
        <label for="style-font-family">Font</label>
        <select id="style-font-family">${options(FONTS, g.fontFamily)}</select>
      </div>
      <div class="style-row">
        <label for="style-label-size">Label size</label>
        <input type="number" id="style-label-size" value="${g.labelFontSize ?? ''}" placeholder="auto" min="6" max="36">
      </div>
      <div class="style-row">
        <label for="style-tick-size">Tick size</label>
        <input type="number" id="style-tick-size" value="${g.tickFontSize ?? ''}" placeholder="auto" min="6" max="36">
      </div>
      <div class="style-row">
        <label for="style-legend-size">Legend size</label>
        <input type="number" id="style-legend-size" value="${g.legendFontSize ?? ''}" placeholder="auto" min="6" max="36">
      </div>
      <div class="style-row">
        <label for="style-marker-size">Marker size</label>
        <input type="number" id="style-marker-size" value="${g.markerSize ?? ''}" placeholder="auto" min="1" max="30">
      </div>
      <div class="style-row">
        <label for="style-marker-step">Marker step</label>
        <input type="number" id="style-marker-step" value="${g.markerStep ?? ''}" placeholder="every point" min="1" step="1">
      </div>
      <div class="style-row">
        <label for="style-line-width">Line width</label>
        <input type="number" id="style-line-width" value="${g.lineWidth ?? ''}" placeholder="auto" min="0.1" step="0.1">
      </div>
      <div class="style-row">
        <label for="style-title">Title</label>
        <input type="text" id="style-title" value="${escapeAttr(g.title || '')}" placeholder="none">
      </div>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-legend" ${g.showLegend ? 'checked' : ''}> Show legend
      </label>
      <div class="style-row">
        <label for="style-legend-pos">Legend position</label>
        <select id="style-legend-pos">
          <option value="top-right" ${g.legendPosition === 'top-right' ? 'selected' : ''}>Top right</option>
          <option value="top" ${g.legendPosition === 'top' ? 'selected' : ''}>Top</option>
          <option value="bottom" ${g.legendPosition === 'bottom' ? 'selected' : ''}>Bottom</option>
        </select>
      </div>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-grid" ${g.showGrid !== false ? 'checked' : ''}> Show gridlines
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-latex" ${g.latex ? 'checked' : ''}> LaTeX text ($...$)
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-panel-border" ${g.showPanelBorder ? 'checked' : ''}> Box around each panel
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-ticks-inside" ${g.ticksInside ? 'checked' : ''}> Tick marks inside
      </label>
      <label>Margins (px)</label>
      <div class="style-limit-row">
        <input type="number" id="style-margin-top" placeholder="top" min="0" value="${g.marginTop ?? ''}">
        <input type="number" id="style-margin-right" placeholder="right" min="0" value="${g.marginRight ?? ''}">
      </div>
      <div class="style-limit-row">
        <input type="number" id="style-margin-bottom" placeholder="bottom" min="0" value="${g.marginBottom ?? ''}">
        <input type="number" id="style-margin-left" placeholder="left" min="0" value="${g.marginLeft ?? ''}">
      </div>
    `;

    // Global figure style (spacing/margins/box included) is meaningful
    // before any panel exists -- a fresh layout tab shouldn't hide it all
    // behind an empty-state placeholder just because nothing has been
    // plotted into it yet.
    if (!ws.panels.length) {
      box.innerHTML = group('global', 'Global', globalBody);
      document.querySelectorAll('.style-group-heading').forEach(el => {
        el.addEventListener('click', () => toggleGroup(el.dataset.group));
      });
      wireGlobal();
      return;
    }

    const panel = activePanel(ws);
    const s = panel.style || {};
    const panelOptions = ws.panels
      .map(p => `<option value="${p.id}" ${p.id === panel.id ? 'selected' : ''}>${p.title}</option>`)
      .join('');

    // Pane position/size lives in Layout -> Panes now (a to-scale preview
    // alongside the numbers), not here.
    const panelBody = `
      <select id="style-panel-select" class="style-panel-select">${panelOptions}</select>

      <div class="style-row">
        <label for="style-xlabel">X label</label>
        <input type="text" id="style-xlabel" placeholder="auto" value="${escapeAttr(s.xlabel || '')}">
      </div>
      <div class="style-row">
        <label for="style-ylabel">Y label</label>
        <input type="text" id="style-ylabel" placeholder="auto" value="${escapeAttr(s.ylabel || '')}">
      </div>
      <label>X limits</label>
      <div class="style-limit-row">
        <input type="number" id="style-xlim-min" placeholder="min" value="${s.xlim ? s.xlim[0] : ''}">
        <input type="number" id="style-xlim-max" placeholder="max" value="${s.xlim ? s.xlim[1] : ''}">
      </div>
      <label>Y limits</label>
      <div class="style-limit-row">
        <input type="number" id="style-ylim-min" placeholder="min" value="${s.ylim ? s.ylim[0] : ''}">
        <input type="number" id="style-ylim-max" placeholder="max" value="${s.ylim ? s.ylim[1] : ''}">
      </div>
      <div class="style-row">
        <label for="style-xtick">X tick step</label>
        <input type="number" id="style-xtick" placeholder="auto" value="${s.xtick ?? ''}">
      </div>
      <div class="style-row">
        <label for="style-ytick">Y tick step</label>
        <input type="number" id="style-ytick" placeholder="auto" value="${s.ytick ?? ''}">
      </div>
      <div class="style-row">
        <label for="style-xtickangle">X tick angle</label>
        <input type="number" id="style-xtickangle" placeholder="auto" value="${s.xtickangle ?? ''}" min="-90" max="90">
      </div>
      <div class="style-row">
        <label for="style-ytickangle">Y tick angle</label>
        <input type="number" id="style-ytickangle" placeholder="auto" value="${s.ytickangle ?? ''}" min="-90" max="90">
      </div>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-swap-axes" ${s.swapAxes ? 'checked' : ''}> Swap X/Y axes
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-x-ticks" ${s.showXTicks === false ? '' : 'checked'}> Show X ticks
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-y-ticks" ${s.showYTicks === false ? '' : 'checked'}> Show Y ticks
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-x-label" ${s.showXLabel === false ? '' : 'checked'}> Show X label
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-y-label" ${s.showYLabel === false ? '' : 'checked'}> Show Y label
      </label>
      ${y2Body(panel, s)}
    `;

    box.innerHTML = group('global', 'Global', globalBody)
      + group('panel', 'Panel', panelBody)
      + group('traces', 'Traces', tracesHtml(panel));

    document.querySelectorAll('.style-group-heading').forEach(el => {
      el.addEventListener('click', () => toggleGroup(el.dataset.group));
    });
    wireGlobal();
    wire(panel);
  }

  // Shown only once at least one trace here actually uses the secondary
  // axis (TraceEditor's Axis tab) -- a panel that doesn't would otherwise
  // carry style controls for an axis it never draws.
  // Shown only once a panel actually has a secondary-axis trace -- before
  // that there is only one Y axis, and coloring it apart from itself means
  // nothing. Y1's own color lives here too rather than up with the rest of
  // the (always-shown) primary Y fields, for the same reason: pointless
  // until there is a second axis to tell it apart from.
  function y2Body(panel, s) {
    if (!panel.traces.some(t => t.secondaryAxis)) return '';
    return `
      <label class="style-subheading">Axis colors</label>
      <div class="style-row">
        <label for="style-ycolor">Y1 (primary)</label>
        <input type="color" id="style-ycolor" value="${s.ycolor || '#000000'}">
      </div>
      <div class="style-row">
        <label for="style-y2color">Y2 (secondary)</label>
        <input type="color" id="style-y2color" value="${s.y2color || '#444444'}">
      </div>
      <label class="style-subheading">Y2 (secondary axis)</label>
      <div class="style-row">
        <label for="style-y2label">Y2 label</label>
        <input type="text" id="style-y2label" placeholder="auto" value="${escapeAttr(s.y2label || '')}">
      </div>
      <label>Y2 limits</label>
      <div class="style-limit-row">
        <input type="number" id="style-y2lim-min" placeholder="min" value="${s.y2lim ? s.y2lim[0] : ''}">
        <input type="number" id="style-y2lim-max" placeholder="max" value="${s.y2lim ? s.y2lim[1] : ''}">
      </div>
      <div class="style-row">
        <label for="style-y2tick">Y2 tick step</label>
        <input type="number" id="style-y2tick" placeholder="auto" value="${s.y2tick ?? ''}">
      </div>
      <div class="style-row">
        <label for="style-y2tickangle">Y2 tick angle</label>
        <input type="number" id="style-y2tickangle" placeholder="auto" value="${s.y2tickangle ?? ''}" min="-90" max="90">
      </div>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-y2-ticks" ${s.showY2Ticks === false ? '' : 'checked'}> Show Y2 ticks
      </label>
      <label class="style-row checkbox">
        <input type="checkbox" id="style-show-y2-label" ${s.showY2Label === false ? '' : 'checked'}> Show Y2 label
      </label>
    `;
  }

  function tracesHtml(panel) {
    if (!panel.traces.length) return '<div class="empty">No traces in this panel</div>';
    return panel.traces.map((t, idx) => `
      <div class="trace-style-block">
        <div class="trace-style-label" title="${PanelTree.traceLabel(t)}">${PanelTree.traceLabel(t)}</div>
        <div class="trace-style-row">
          <input type="color" class="trace-style-color" data-idx="${idx}" value="${t.color || '#000000'}">
          <select class="trace-style-line" data-idx="${idx}">${options(LINE_STYLES, t.lineStyle)}</select>
          <select class="trace-style-marker" data-idx="${idx}">${options(MARKERS, t.marker)}</select>
        </div>
      </div>
    `).join('');
  }

  // Global-only controls -- wired independently of wire(panel) since the
  // Global group renders (and needs its listeners attached) even when
  // there are no panels yet to make a "panel" argument meaningful for.
  function wireGlobal() {
    const global = (patch) => { PlotWorkspace.setGlobalStyle(patch); PlotArea.render(); };

    document.getElementById('style-font-family').addEventListener('change', (e) => global({ fontFamily: e.target.value }));
    document.getElementById('style-label-size').addEventListener('change', (e) => global({ labelFontSize: numberOrNull(e.target.value) }));
    document.getElementById('style-tick-size').addEventListener('change', (e) => global({ tickFontSize: numberOrNull(e.target.value) }));
    document.getElementById('style-legend-size').addEventListener('change', (e) => global({ legendFontSize: numberOrNull(e.target.value) }));
    document.getElementById('style-marker-size').addEventListener('change', (e) => global({ markerSize: numberOrNull(e.target.value) }));
    document.getElementById('style-marker-step').addEventListener('change', (e) => {
      const v = e.target.value.trim();
      global({ markerStep: v === '' ? null : Math.max(1, Math.round(parseFloat(v))) });
    });
    document.getElementById('style-line-width').addEventListener('change', (e) => {
      const v = e.target.value.trim();
      global({ lineWidth: v === '' ? null : Math.max(0.1, parseFloat(v)) });
    });
    document.getElementById('style-title').addEventListener('change', (e) => global({ title: e.target.value.trim() }));
    document.getElementById('style-show-legend').addEventListener('change', (e) => global({ showLegend: e.target.checked }));
    document.getElementById('style-legend-pos').addEventListener('change', (e) => global({ legendPosition: e.target.value }));
    document.getElementById('style-show-grid').addEventListener('change', (e) => global({ showGrid: e.target.checked }));
    // PlotArea.render() itself notices style.latex and loads MathJax if
    // needed (also covers a page reload restoring latex:true, which never
    // fires this change event at all), so this just flips the flag.
    document.getElementById('style-latex').addEventListener('change', (e) => global({ latex: e.target.checked }));
    document.getElementById('style-panel-border').addEventListener('change', (e) => global({ showPanelBorder: e.target.checked }));
    document.getElementById('style-ticks-inside').addEventListener('change', (e) => global({ ticksInside: e.target.checked }));
    document.getElementById('style-margin-top').addEventListener('change', (e) => global({ marginTop: numberOrNull(e.target.value) }));
    document.getElementById('style-margin-right').addEventListener('change', (e) => global({ marginRight: numberOrNull(e.target.value) }));
    document.getElementById('style-margin-bottom').addEventListener('change', (e) => global({ marginBottom: numberOrNull(e.target.value) }));
    document.getElementById('style-margin-left').addEventListener('change', (e) => global({ marginLeft: numberOrNull(e.target.value) }));
  }

  function wire(panel) {
    document.getElementById('style-panel-select').addEventListener('change', (e) => {
      PlotWorkspace.setActivePanel(e.target.value);
      refreshWorkspace();
    });

    // Both ends must be given or the limit doesn't apply -- a Plotly range
    // needs a numeric max as much as a numeric min, so "just a floor" isn't
    // representable and is silently treated as "no limit" instead.
    function wireLimit(key, minId, maxId) {
      const minEl = document.getElementById(minId);
      const maxEl = document.getElementById(maxId);
      const commit = () => {
        const minV = minEl.value.trim();
        const maxV = maxEl.value.trim();
        const value = (minV === '' || maxV === '') ? null : [parseFloat(minV), parseFloat(maxV)];
        PlotWorkspace.setPanelStyle(panel.id, { [key]: value });
        PlotArea.render();
        PanelTree.render();   // the lock icon mirrors ylim
      };
      minEl.addEventListener('change', commit);
      maxEl.addEventListener('change', commit);
    }
    wireLimit('xlim', 'style-xlim-min', 'style-xlim-max');
    wireLimit('ylim', 'style-ylim-min', 'style-ylim-max');

    // A step that is tiny relative to the axis's own range asks Plotly to
    // draw hundreds of gridlines and can hang the render for several
    // seconds -- rejected up front rather than applied and discovered the
    // hard way (found by actually trying it: 0.1 over a ~230 s time axis).
    function wireTick(key, id, panelLimitKey, rangeFn) {
      const input = document.getElementById(id);
      input.addEventListener('change', (e) => {
        const raw = e.target.value.trim();
        input.setCustomValidity('');
        if (raw === '') {
          PlotWorkspace.setPanelStyle(panel.id, { [key]: null });
          PlotArea.render();
          return;
        }
        const step = parseFloat(raw);
        const lim = (panel.style && panel.style[panelLimitKey]) || rangeFn();
        if (step > 0 && lim) {
          const count = Math.abs(lim[1] - lim[0]) / step;
          if (count > MAX_TICKS) {
            const minStep = (Math.abs(lim[1] - lim[0]) / MAX_TICKS);
            input.setCustomValidity(`Too fine: about ${Math.round(count)} ticks over this axis. Try at least ${minStep.toPrecision(2)}.`);
            input.reportValidity();
            return;
          }
        }
        PlotWorkspace.setPanelStyle(panel.id, { [key]: step });
        PlotArea.render();
      });
    }
    const isSwapped = () => !!(panel.style && panel.style.swapAxes);
    wireTick('xtick', 'style-xtick', 'xlim', () => PlotArea.currentXRange(panel.id, isSwapped()));
    wireTick('ytick', 'style-ytick', 'ylim', () => PlotArea.currentYRange(panel.id, isSwapped()));

    document.getElementById('style-xlabel').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { xlabel: e.target.value.trim() });
      PlotArea.render();
    });
    document.getElementById('style-ylabel').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { ylabel: e.target.value.trim() });
      PlotArea.render();
    });
    document.getElementById('style-xtickangle').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { xtickangle: numberOrNull(e.target.value) });
      PlotArea.render();
    });
    document.getElementById('style-ytickangle').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { ytickangle: numberOrNull(e.target.value) });
      PlotArea.render();
    });
    document.getElementById('style-swap-axes').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { swapAxes: e.target.checked });
      PlotArea.render();
    });
    document.getElementById('style-show-x-ticks').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { showXTicks: e.target.checked });
      PlotArea.render();
    });
    document.getElementById('style-show-y-ticks').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { showYTicks: e.target.checked });
      PlotArea.render();
    });
    document.getElementById('style-show-x-label').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { showXLabel: e.target.checked });
      PlotArea.render();
    });
    document.getElementById('style-show-y-label').addEventListener('change', (e) => {
      PlotWorkspace.setPanelStyle(panel.id, { showYLabel: e.target.checked });
      PlotArea.render();
    });

    // Only rendered (y2Body) once a trace here actually uses the secondary
    // axis, so only wired then -- the elements simply don't exist otherwise.
    if (panel.traces.some(t => t.secondaryAxis)) {
      wireLimit('y2lim', 'style-y2lim-min', 'style-y2lim-max');
      wireTick('y2tick', 'style-y2tick', 'y2lim', () => PlotArea.currentY2Range(panel.id, isSwapped()));
      document.getElementById('style-y2label').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { y2label: e.target.value.trim() });
        PlotArea.render();
      });
      document.getElementById('style-y2tickangle').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { y2tickangle: numberOrNull(e.target.value) });
        PlotArea.render();
      });
      document.getElementById('style-show-y2-ticks').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { showY2Ticks: e.target.checked });
        PlotArea.render();
      });
      document.getElementById('style-show-y2-label').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { showY2Label: e.target.checked });
        PlotArea.render();
      });
      document.getElementById('style-y2color').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { y2color: e.target.value });
        PlotArea.render();
      });
      document.getElementById('style-ycolor').addEventListener('change', (e) => {
        PlotWorkspace.setPanelStyle(panel.id, { ycolor: e.target.value });
        PlotArea.render();
      });
    }

    // 'change' (fires once, on commit), not 'input' -- PlotArea.render() is
    // a network round-trip, and 'input' fires continuously while dragging
    // inside the native color picker.
    document.querySelectorAll('.trace-style-color').forEach(el => el.addEventListener('change', (e) => {
      PlotWorkspace.setTraceStyle(panel.id, Number(e.target.dataset.idx), { color: e.target.value });
      PlotArea.render();
      PanelTree.render();   // the trace-row swatch mirrors this trace's color
    }));
    document.querySelectorAll('.trace-style-line').forEach(el => el.addEventListener('change', (e) => {
      PlotWorkspace.setTraceStyle(panel.id, Number(e.target.dataset.idx), { lineStyle: e.target.value });
      PlotArea.render();
    }));
    document.querySelectorAll('.trace-style-marker').forEach(el => el.addEventListener('change', (e) => {
      PlotWorkspace.setTraceStyle(panel.id, Number(e.target.dataset.idx), { marker: e.target.value });
      PlotArea.render();
    }));
  }

  // LINE_STYLES/MARKERS/options are also what TraceEditor's Line/Marker tabs
  // offer, so a trace styled from the tree's popup and one styled from this
  // sidebar's own Traces group agree on exactly the same set of choices.
  return { render, LINE_STYLES, MARKERS, options };
})();
