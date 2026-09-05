// The right-hand Style sidebar: global figure style (font, title, legend,
// gridlines) and per-panel style (x/y limits, tick step) for whichever
// panel is "active" -- selected by clicking its title in the left PANELS
// tree, or from the dropdown here.
const StyleSidebar = (() => {
  const MAX_TICKS = 200;   // a runaway dtick (e.g. 0.1 over a 230 s axis) can hang Plotly's render

  function activePanel(ws) {
    return ws.panels.find(p => p.id === ws.activePanelId) || ws.panels[0];
  }

  function render() {
    const ws = PlotWorkspace.state();
    const box = document.getElementById('style-body');

    if (!ws.panels.length) {
      box.innerHTML = '<div class="empty">Plot &rarr; New arrives here</div>';
      return;
    }

    const panel = activePanel(ws);
    const g = ws.style || {};
    const s = panel.style || {};
    const panelOptions = ws.panels
      .map(p => `<option value="${p.id}" ${p.id === panel.id ? 'selected' : ''}>${p.title}</option>`)
      .join('');

    box.innerHTML = `
      <div class="style-group">
        <div class="style-group-heading">Global</div>
        <div class="style-row">
          <label for="style-font-family">Font</label>
          <input type="text" id="style-font-family" value="${g.fontFamily || ''}" placeholder="default">
        </div>
        <div class="style-row">
          <label for="style-label-size">Label size</label>
          <input type="number" id="style-label-size" value="${g.labelFontSize ?? ''}" placeholder="auto" min="6" max="36">
        </div>
        <div class="style-row">
          <label for="style-legend-size">Legend size</label>
          <input type="number" id="style-legend-size" value="${g.legendFontSize ?? ''}" placeholder="auto" min="6" max="36">
        </div>
        <div class="style-row">
          <label for="style-title">Title</label>
          <input type="text" id="style-title" value="${g.title || ''}" placeholder="none">
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
      </div>

      <div class="style-group">
        <div class="style-group-heading">Panel</div>
        <select id="style-panel-select" class="style-panel-select">${panelOptions}</select>

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
      </div>
    `;

    wire(panel);
  }

  function wire(panel) {
    const global = (patch) => { PlotWorkspace.setGlobalStyle(patch); PlotArea.render(); };
    const numberOrNull = (v) => (v.trim() === '' ? null : parseFloat(v));

    document.getElementById('style-font-family').addEventListener('change', (e) => global({ fontFamily: e.target.value.trim() }));
    document.getElementById('style-label-size').addEventListener('change', (e) => global({ labelFontSize: numberOrNull(e.target.value) }));
    document.getElementById('style-legend-size').addEventListener('change', (e) => global({ legendFontSize: numberOrNull(e.target.value) }));
    document.getElementById('style-title').addEventListener('change', (e) => global({ title: e.target.value.trim() }));
    document.getElementById('style-show-legend').addEventListener('change', (e) => global({ showLegend: e.target.checked }));
    document.getElementById('style-legend-pos').addEventListener('change', (e) => global({ legendPosition: e.target.value }));
    document.getElementById('style-show-grid').addEventListener('change', (e) => global({ showGrid: e.target.checked }));

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
    const idx = PlotWorkspace.state().panels.indexOf(panel);
    wireTick('xtick', 'style-xtick', 'xlim', () => PlotArea.currentXRange(idx));
    wireTick('ytick', 'style-ytick', 'ylim', () => PlotArea.currentYRange(idx));
  }

  return { render };
})();
