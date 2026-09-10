// Interactive vtk.js viewer for `render`-kind panels (Field -> Render).
//
// Unlike every other panel kind, a render panel isn't a data recipe Plotly
// (or matplotlib, for export) can redraw on demand -- it's a live 3-D scene
// the user rotates/pans/zooms themselves. So this owns the whole life of
// each one's viewport: mounting a vtk.js render window into its own
// container div, positioned in the HTML overlay plot.js keeps beside its
// Plotly figure (#mesh-panels-overlay, a sibling of #plotly-panels inside
// #plot-canvas-wrapper -- see PlotArea.render).
//
// The one hard rule everything else here follows: an existing panel's
// viewer instance must never be torn down and rebuilt just because
// PlotArea.render() ran again (a style tweak on an unrelated panel, a
// window resize, ...) -- that would reset the user's camera angle on every
// unrelated change. `sync()` diffs against its own previous panel list and
// only (re)creates what's actually new.
const MeshViewer = (() => {
  const DPI = 96;   // matches plot.js's own SCREEN_DPI and export.py's _SCREEN_DPI

  let vtkPromise = null;
  function ensureVtkJs() {
    if (vtkPromise) return vtkPromise;
    vtkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/vendor/vtkjs/vtk.min.js';
      script.onload = resolve;
      script.onerror = () => { vtkPromise = null; reject(new Error('could not load the 3-D mesh viewer')); };
      document.head.appendChild(script);
    });
    return vtkPromise;
  }

  // panelId -> { container, genericRW, renderer, renderWindow, mapper, actor, polydata }
  const instances = new Map();

  function isFreeformPane(p) {
    return !!p && typeof p.x === 'number' && typeof p.y === 'number'
      && typeof p.w === 'number' && typeof p.h === 'number';
  }

  // A panel with no explicit pane (never touched in Layout -> Panes) fills
  // the whole canvas -- expressed here as 100%/0 rather than needing the
  // canvas's own inches size, since #mesh-panels-overlay already exactly
  // matches #plotly-panels' pixel box (see plot.js).
  function applyPosition(container, pane) {
    if (isFreeformPane(pane)) {
      container.style.left = `${pane.x * DPI}px`;
      container.style.top = `${pane.y * DPI}px`;
      container.style.width = `${pane.w * DPI}px`;
      container.style.height = `${pane.h * DPI}px`;
    } else {
      container.style.left = '0';
      container.style.top = '0';
      container.style.width = '100%';
      container.style.height = '100%';
    }
  }

  function colorRangeFor(inst, colorVar, colorRange) {
    if (Array.isArray(colorRange) && colorRange.length === 2) return colorRange;
    const arr = inst.polydata.getPointData().getArrayByName(colorVar);
    return arr ? arr.getRange() : [0, 1];
  }

  function applyStyle(inst, style) {
    style = style || {};

    const bg = style.background || [1, 1, 1];
    inst.renderer.setBackground(bg[0], bg[1], bg[2]);

    const colorVar = style.colorVar;
    if (colorVar && inst.polydata.getPointData().getArrayByName(colorVar)) {
      inst.mapper.setScalarVisibility(true);
      inst.mapper.setScalarModeToUsePointFieldData();
      inst.mapper.setColorByArrayName(colorVar);
      const range = colorRangeFor(inst, colorVar, style.colorRange);
      inst.mapper.setScalarRange(range[0], range[1]);
    } else {
      inst.mapper.setScalarVisibility(false);
    }

    inst.container.classList.toggle('mesh-panel-border', !!style.showBorder);
    inst.container.style.opacity = style.opacity == null ? 1 : style.opacity;

    inst.renderWindow.render();
  }

  async function createInstance(panel, overlayEl) {
    await ensureVtkJs();

    const container = document.createElement('div');
    container.className = 'mesh-panel';
    container.dataset.panelId = panel.id;
    overlayEl.appendChild(container);
    applyPosition(container, panel.pane);

    const genericRW = vtk.Rendering.Misc.vtkGenericRenderWindow.newInstance();
    genericRW.setContainer(container);
    genericRW.resize();
    const renderer = genericRW.getRenderer();
    const renderWindow = genericRW.getRenderWindow();
    const interactor = genericRW.getInteractor();
    const style = vtk.Interaction.Style.vtkInteractorStyleTrackballCamera.newInstance();
    interactor.setInteractorStyle(style);

    const reader = vtk.IO.XML.vtkXMLPolyDataReader.newInstance();
    const url = `/api/cases/${encodeURIComponent(panel.case)}/field/render-file/${panel.meshToken}`;
    await reader.setUrl(url);
    const polydata = reader.getOutputData(0);

    const mapper = vtk.Rendering.Core.vtkMapper.newInstance();
    mapper.setInputData(polydata);
    const actor = vtk.Rendering.Core.vtkActor.newInstance();
    actor.setMapper(mapper);
    renderer.addActor(actor);
    renderer.resetCamera();

    const inst = { container, genericRW, renderer, renderWindow, mapper, actor, polydata };
    instances.set(panel.id, inst);
    applyStyle(inst, panel.style);
    return inst;
  }

  function destroyInstance(inst) {
    inst.genericRW.delete();
    inst.container.remove();
  }

  // panels: the current render-kind panels (plot.js already filters
  // ws.panels down to these). overlayEl: #mesh-panels-overlay -- only
  // needed when actually creating a new instance, so it's fine to omit when
  // `panels` is empty (see plot.js's placeholder()).
  async function sync(panels, overlayEl) {
    const seen = new Set();
    for (const panel of panels) {
      seen.add(panel.id);
      let inst = instances.get(panel.id);
      if (!inst) {
        inst = await createInstance(panel, overlayEl);
      } else {
        applyPosition(inst.container, panel.pane);
        applyStyle(inst, panel.style);
      }
      inst.genericRW.resize();
    }
    for (const [id, inst] of instances) {
      if (!seen.has(id)) {
        destroyInstance(inst);
        instances.delete(id);
      }
    }
  }

  // "Reset camera" (Style sidebar) -- view-only, not persisted panel state,
  // unlike everything applyStyle handles.
  function resetCamera(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return;
    inst.renderer.resetCamera();
    inst.renderWindow.render();
  }

  // Layout -> Export: whatever camera angle the user currently has it
  // rotated to becomes the exported image (there's no fixed camera to
  // re-render server-side -- see export.py's own 'render' branch).
  function captureImage(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return null;
    const canvas = inst.genericRW.getContainer().querySelector('canvas');
    return canvas ? canvas.toDataURL('image/png') : null;
  }

  return { sync, resetCamera, captureImage };
})();
