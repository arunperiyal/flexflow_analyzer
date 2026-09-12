// Interactive vtk.js viewer, used only inside Field -> Render's
// configuration window (field.js's openRenderConfig) while a mesh's camera,
// color and contour are still being worked out live -- a layout panel
// itself is a static snapshot PNG (Plotly's own layout.images, see plot.js)
// once "Add to Layout" bakes one, not something this ever touches again.
//
// Written generically over an array of "panel-shaped" objects ({id, case,
// meshToken, pane, style}) rather than assuming they come from
// PlotWorkspace, since the configuration window's mesh isn't a workspace
// panel at all until it's finalized -- field.js just hands sync() a
// one-element array built from its own local, un-persisted state.
//
// The one hard rule everything else here follows: an existing entry's
// viewer instance must never be torn down and rebuilt just because sync()
// ran again for an unrelated reason -- that would reset the camera on every
// style tweak. `sync()` diffs against its own previous list and only
// (re)creates what's actually new.
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

  // An entry with no explicit pane fills its whole container instead --
  // which is every entry now, in practice: the configuration window is the
  // only caller left, and it never sets one (a `pane` only ever meant
  // "this panel's spot on the Layout -> Panes canvas", which a still-being-
  // configured mesh doesn't have yet).
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

  // -- Colormaps --------------------------------------------------------
  // Mirrors render.py's color.preset vocabulary (PRESET_CMAP in render.py)
  // so a preset picked here reads as the same map in a `field render` PNG,
  // not necessarily the identical bytes -- vtk.js ships ParaView's preset
  // library, not matplotlib's, so this maps onto the closest ParaView preset
  // for each name. 'small_rainbow' is the one exception: FlexFlow's own map
  // (render.py's _small_rainbow, matching a Tecplot legend exactly), built
  // directly below instead of approximated from vtk.js's library.
  const PRESET_TO_VTK = {
    coolwarm: 'Cool to Warm',
    viridis: 'Viridis (matplotlib)',
    jet: 'Jet',
    turbo: 'Rainbow Desaturated',
    inferno: 'Black-Body Radiation',
  };

  function hsvToRgb(h, s, v) {
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);
    switch (i % 6) {
      case 0: return [v, t, p];
      case 1: return [q, v, p];
      case 2: return [p, v, t];
      case 3: return [p, q, v];
      case 4: return [t, p, v];
      default: return [v, p, q];
    }
  }

  // The 240..0 degree hue arc at full saturation/value -- see render.py's
  // _small_rainbow for the same formula (blue, cyan, green, yellow, red).
  function addSmallRainbow(ctf, lo, hi, n = 32) {
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const [r, g, b] = hsvToRgb((2 / 3) * (1 - t), 1, 1);
      ctf.addRGBPoint(lo + t * (hi - lo), r, g, b);
    }
  }

  // Builds the continuous color transfer function for one panel's current
  // preset/range/log-scale. `null`/unknown preset keeps vtk.js's own default
  // map (whatever a bare setColorByArrayName drew before any of this
  // existed) -- so a panel from before preset support, or one that never
  // asked for a preset, looks exactly as it always did.
  function buildColorTransferFunction(range, presetName, logScale) {
    if (!presetName) return null;
    const ctf = vtk.Rendering.Core.vtkColorTransferFunction.newInstance();
    if (presetName === 'small_rainbow') {
      addSmallRainbow(ctf, range[0], range[1]);
    } else {
      const preset = vtk.Rendering.Core.vtkColorTransferFunction.vtkColorMaps
        .getPresetByName(PRESET_TO_VTK[presetName] || presetName);
      if (preset) ctf.applyColorMap(preset);
    }
    // Scale.LOG10 === 1 (vtk.js's own enum) -- needs range[0] > 0, same
    // requirement matplotlib's LogNorm has; silently no-ops otherwise rather
    // than throwing, since a negative-signed variable (vorticity, say) picking
    // this up by mistake shouldn't break the whole panel.
    if (logScale && range[0] > 0) ctf.setScale(1);
    ctf.setMappingRange(range[0], range[1]);
    ctf.updateRange();
    return ctf;
  }

  // N discrete bands, as Tecplot bands a legend -- see render.py's
  // color.levels (cmap.resampled(N) there). vtk.js's transfer function always
  // interpolates between nodes, so a hard step is built from two points an
  // epsilon apart at each band edge, sampling the continuous function this
  // replaces for each band's own color first.
  function quantize(ctf, range, levels) {
    if (!ctf || !levels || levels < 2) return ctf;
    const [lo, hi] = range;
    const span = hi - lo;
    if (span <= 0) return ctf;
    const eps = span * 1e-6;
    const bandColor = (i) => {
      const rgb = [];
      ctf.getColor(lo + (i + 0.5) * span / levels, rgb);
      return rgb;
    };
    const colors = Array.from({ length: levels }, (_, i) => bandColor(i));
    const out = vtk.Rendering.Core.vtkColorTransferFunction.newInstance();
    out.addRGBPoint(lo, ...colors[0]);
    for (let i = 1; i < levels; i++) {
      const edge = lo + (i * span) / levels;
      out.addRGBPoint(edge - eps, ...colors[i - 1]);
      out.addRGBPoint(edge, ...colors[i]);
    }
    out.addRGBPoint(hi, ...colors[levels - 1]);
    out.setMappingRange(lo, hi);
    out.updateRange();
    return out;
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
      let ctf = buildColorTransferFunction(range, style.preset, style.logScale);
      ctf = quantize(ctf, range, style.levels);
      // Falls back to the mapper's own original lookup table (captured in
      // createInstance) when no preset is set -- otherwise turning a preset
      // back off would leave the previous preset's table applied.
      inst.mapper.setLookupTable(ctf || inst.defaultLookupTable);
    } else {
      inst.mapper.setScalarVisibility(false);
    }

    // Surface appearance -- render.py's surface: block. `lighting: false`
    // there means flat (no shading at all, exactly the legend's colours);
    // vtk.js's own default is lighting on, matching surface.lighting's
    // default of null/true.
    const prop = inst.actor.getProperty();
    prop.setOpacity(style.opacity == null ? 1 : style.opacity);
    prop.setEdgeVisibility(!!style.showEdges);
    prop.setLighting(style.lighting !== false);
    if (style.ambient != null) prop.setAmbient(style.ambient);
    if (style.diffuse != null) prop.setDiffuse(style.diffuse);
    if (style.specular != null) prop.setSpecular(style.specular);
    if (style.specularPower != null) prop.setSpecularPower(style.specularPower);

    inst.container.classList.toggle('mesh-panel-border', !!style.showBorder);

    inst.renderWindow.render();
  }

  // vtkInteractorStyleTrackballCamera (the obvious default) has no public API
  // to add or inspect its mouse bindings on this vtk.js build -- its own
  // middle/right-button handling is wired up somewhere inside its closure
  // where it can't be reached, and left/middle/right all being hardcoded
  // there means what it does bind can't be extended either. Built explicitly
  // from vtkInteractorStyleManipulator instead, so every binding is one this
  // file actually declares: left drag rotates, middle drag OR shift+left
  // pans (shift+left kept for anyone used to trackball-camera's own gesture,
  // and for a mouse with no usable middle button), right drag or the wheel
  // zooms.
  function buildInteractorStyle() {
    const M = vtk.Interaction.Manipulators;
    const style = vtk.Interaction.Style.vtkInteractorStyleManipulator.newInstance();
    style.addMouseManipulator(M.vtkMouseCameraTrackballRotateManipulator.newInstance());
    style.addMouseManipulator(M.vtkMouseCameraTrackballPanManipulator.newInstance({ button: 2 }));
    style.addMouseManipulator(M.vtkMouseCameraTrackballPanManipulator.newInstance({ button: 1, shift: true }));
    style.addMouseManipulator(M.vtkMouseCameraTrackballZoomManipulator.newInstance({ button: 3 }));
    style.addMouseManipulator(
      M.vtkMouseCameraTrackballZoomManipulator.newInstance({ scrollEnabled: true, dragEnabled: false }));
    return style;
  }

  async function loadPolydata(caseName, meshToken) {
    const reader = vtk.IO.XML.vtkXMLPolyDataReader.newInstance();
    const url = `/api/cases/${encodeURIComponent(caseName)}/field/render-file/${meshToken}`;
    await reader.setUrl(url);
    return reader.getOutputData(0);
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
    interactor.setInteractorStyle(buildInteractorStyle());

    const polydata = await loadPolydata(panel.case, panel.meshToken);

    const mapper = vtk.Rendering.Core.vtkMapper.newInstance();
    mapper.setInputData(polydata);
    // Captured before any preset is ever applied, so turning a preset back
    // off (style.preset: null) has something to restore the mapper's lookup
    // table to -- getLookupTable() lazily creates one on first call and
    // returns that same instance every time after, so this is stable.
    const defaultLookupTable = mapper.getLookupTable();
    const actor = vtk.Rendering.Core.vtkActor.newInstance();
    actor.setMapper(mapper);
    renderer.addActor(actor);
    renderer.resetCamera();
    fitTight(renderer, container);

    // vtk.js's renderer.resetCamera() only re-fits the CURRENT view direction
    // to the actors' bounds -- it does not restore a rotated camera's original
    // orientation (confirmed against the vtk.js source: it moves the camera
    // along its existing view vector, never touching azimuth/elevation/viewUp).
    // So "Reset camera" has to remember this initial pose itself and restore
    // it exactly, rather than calling resetCamera() again -- see resetCamera()
    // below.
    const camera = renderer.getActiveCamera();
    const initialCamera = {
      position: camera.getPosition(),
      focalPoint: camera.getFocalPoint(),
      viewUp: camera.getViewUp(),
    };

    const inst = { container, genericRW, renderer, renderWindow, mapper, actor, polydata,
                   initialCamera, defaultLookupTable };
    instances.set(panel.id, inst);
    applyStyle(inst, panel.style);
    return inst;
  }

  function destroyInstance(inst) {
    inst.genericRW.delete();
    inst.container.remove();
  }

  // renderer.resetCamera() (vtk.js/classic VTK) fits the actors' bounding
  // SPHERE, not the actual 2-D silhouette from the current view direction --
  // for anything elongated or thin (most meshes here) that wastes most of
  // the frame, and worse, it doesn't refit at all when only the viewport's
  // aspect ratio changes (it moves the camera along the existing view
  // vector by the same sphere radius regardless of aspect, so widening a
  // pane just stretches empty space instead of using it). This computes a
  // tight fit instead: project the bounds' 8 corners onto the camera's own
  // right/up basis to get the true half-width/half-height for this exact
  // view angle, then solve the distance that makes *both* dimensions touch
  // the viewport edges, given the camera's vertical field of view and the
  // container's current aspect ratio. Keeps the camera's current forward
  // direction and viewUp -- only position and focal point move -- so it
  // never undoes a rotation the way resetCamera-then-restore-pose would.
  function fitTight(renderer, container) {
    const M = vtk.Common.Core.vtkMath;
    const camera = renderer.getActiveCamera();
    const actors = renderer.getActors();
    let b = null;
    for (const a of actors) {
      const ab = a.getBounds();
      if (!ab || ab[1] < ab[0]) continue;
      if (!b) {
        b = ab.slice();
      } else {
        b[0] = Math.min(b[0], ab[0]); b[1] = Math.max(b[1], ab[1]);
        b[2] = Math.min(b[2], ab[2]); b[3] = Math.max(b[3], ab[3]);
        b[4] = Math.min(b[4], ab[4]); b[5] = Math.max(b[5], ab[5]);
      }
    }
    if (!b) return;

    const center = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2];
    const forward = M.subtract(camera.getFocalPoint(), camera.getPosition(), [0, 0, 0]);
    M.normalize(forward);
    const viewUp = camera.getViewUp();
    const right = [0, 0, 0];
    M.cross(forward, viewUp, right);
    M.normalize(right);
    const up = [0, 0, 0];
    M.cross(right, forward, up);
    M.normalize(up);

    let halfW = 1e-6;
    let halfH = 1e-6;
    for (const x of [b[0], b[1]]) {
      for (const y of [b[2], b[3]]) {
        for (const z of [b[4], b[5]]) {
          const rel = M.subtract([x, y, z], center, [0, 0, 0]);
          halfW = Math.max(halfW, Math.abs(M.dot(rel, right)));
          halfH = Math.max(halfH, Math.abs(M.dot(rel, up)));
        }
      }
    }

    const rect = container.getBoundingClientRect();
    const aspect = (rect.width && rect.height) ? rect.width / rect.height : 1;
    const halfVAngle = (camera.getViewAngle() * Math.PI) / 360;
    const distV = halfH / Math.tan(halfVAngle);
    const distH = halfW / (Math.tan(halfVAngle) * aspect);
    const distance = Math.max(distV, distH) * 1.02; // small margin so edges aren't clipped

    camera.setFocalPoint(center[0], center[1], center[2]);
    camera.setPosition(
      center[0] - forward[0] * distance,
      center[1] - forward[1] * distance,
      center[2] - forward[2] * distance
    );
    camera.setViewUp(viewUp[0], viewUp[1], viewUp[2]);
    renderer.resetCameraClippingRange();
  }

  // panels: panel-shaped objects to keep a live viewport for -- in practice
  // always field.js's own single-element array for whatever the
  // configuration window currently holds ([] to tear it down on
  // Cancel/Add-to-Layout/teardownRenderConfigIfOpen). overlayEl: where a
  // newly created instance's container div is appended -- only needed when
  // actually creating one, so it's fine to omit when `panels` is empty.
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
  // unlike everything applyStyle handles. Restores the exact pose captured
  // when the mesh first loaded, rather than calling renderer.resetCamera()
  // (which only re-fits the CURRENT, possibly rotated, view direction to the
  // bounds -- so after any rotation it leaves the camera looking exactly the
  // way it already was).
  function resetCamera(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return;
    const camera = inst.renderer.getActiveCamera();
    const init = inst.initialCamera;
    camera.setPosition(...init.position);
    camera.setFocalPoint(...init.focalPoint);
    camera.setViewUp(...init.viewUp);
    inst.renderer.resetCameraClippingRange();
    inst.renderWindow.render();
  }

  // The configuration window's "Panel size" fields (field.js) call this
  // after resizing the viewport -- unlike resetCamera above, this re-fits
  // the CURRENT view direction to the bounds (via fitTight, see above),
  // which is exactly what's needed here and NOT what "Reset camera" does:
  // changing the viewport's aspect ratio without refitting leaves the old
  // zoom looking right only for the old shape, so a pane widened to cut
  // down on empty space around a long, thin mesh only made it a tiny dot in
  // the middle of a much wider frame instead. Keeps whatever rotation the
  // user already applied (fitTight never touches forward/viewUp) and
  // updates initialCamera so "Reset camera" returns to *this* fit rather
  // than the stale one sized for the old aspect ratio.
  function fitCamera(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return;
    fitTight(inst.renderer, inst.container);
    const camera = inst.renderer.getActiveCamera();
    inst.initialCamera = {
      position: camera.getPosition(),
      focalPoint: camera.getFocalPoint(),
      viewUp: camera.getViewUp(),
    };
    inst.renderWindow.render();
  }

  // Save Camera (Field menu) -- the live pose, in the same shape
  // resetCamera/reloadMesh already keep as initialCamera, for field.js to
  // write out as YAML. null when there's no instance to read (the
  // configuration window isn't open, or already closed).
  function getCamera(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return null;
    const camera = inst.renderer.getActiveCamera();
    return {
      position: camera.getPosition(),
      focalPoint: camera.getFocalPoint(),
      viewUp: camera.getViewUp(),
    };
  }

  // Load Camera (the configuration window's sidebar) -- applies an
  // externally supplied pose (parsed from a saved camera YAML) to the live
  // view. Deliberately does NOT touch initialCamera: "Reset camera" should
  // still return to how the mesh first framed itself, not to a loaded
  // camera that may not even suit this mesh's bounds.
  function setCamera(panelId, camera) {
    const inst = instances.get(panelId);
    if (!inst || !camera) return;
    const activeCamera = inst.renderer.getActiveCamera();
    activeCamera.setPosition(...camera.position);
    activeCamera.setFocalPoint(...camera.focalPoint);
    activeCamera.setViewUp(...camera.viewUp);
    inst.renderer.resetCameraClippingRange();
    inst.renderWindow.render();
  }

  // Style sidebar's editable contour variable/value (a `render` panel is
  // otherwise never re-extracted after creation): swaps the mapper's input
  // for a freshly re-extracted mesh in place, rather than tearing the
  // instance down and rebuilding it the way a brand new panel would --
  // that would also mean a fresh WebGL context and losing every unrelated
  // style already applied for no reason. The panel's own style (color,
  // surface appearance) is reapplied against the new geometry since its
  // scalar arrays -- and their ranges -- can differ from the old surface's;
  // the camera is refit to the new bounds (surfaces at very different
  // isovalues can occupy very different regions) but keeps its current
  // *orientation*, and that refit becomes the new "Reset camera" pose --
  // unless preserveCamera is set (field.js's cfg.cameraCustom, once a
  // camera has been explicitly loaded), in which case the loaded pose is
  // left completely alone: the whole point of loading a saved camera is
  // often to compare several contours from the exact same viewpoint, which
  // an unconditional refit here would silently undo on the first Apply.
  async function reloadMesh(panel, preserveCamera) {
    const inst = instances.get(panel.id);
    if (!inst) return;
    const polydata = await loadPolydata(panel.case, panel.meshToken);
    inst.polydata = polydata;
    inst.mapper.setInputData(polydata);
    if (!preserveCamera) fitTight(inst.renderer, inst.container);
    const camera = inst.renderer.getActiveCamera();
    inst.initialCamera = {
      position: camera.getPosition(),
      focalPoint: camera.getFocalPoint(),
      viewUp: camera.getViewUp(),
    };
    applyStyle(inst, panel.style);
  }

  // Layout -> Export: whatever camera angle the user currently has it
  // rotated to becomes the exported image (there's no fixed camera to
  // re-render server-side -- see export.py's own 'render' branch).
  // canvas.toDataURL() reads back whatever the WebGL drawing buffer holds --
  // which, without the context having been created with
  // preserveDrawingBuffer:true (it wasn't; vtk.js's default is false, and
  // nothing here can override that after the fact), the browser is free to
  // have already cleared by the time this runs, well after the render that
  // drew it. That's what made every exported render panel come out blank.
  // captureNextImage() is vtk.js's own answer to exactly this: it hands back
  // a promise that resolves with the *next* frame's pixels, read via
  // gl.readPixels during that frame's own render rather than the canvas
  // afterward -- so the render below has to happen after the promise is
  // requested, not before.
  async function captureImage(panelId) {
    const inst = instances.get(panelId);
    if (!inst) return null;
    const apiWindow = inst.genericRW.getApiSpecificRenderWindow();
    const promise = apiWindow.captureNextImage();
    inst.renderWindow.render();
    return promise;
  }

  return { sync, resetCamera, fitCamera, getCamera, setCamera, reloadMesh, captureImage };
})();
