document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    
    const uploadSection = document.getElementById('upload-section');
    const loadingSection = document.getElementById('loading-section');
    const workspaceSection = document.getElementById('workspace-section');
    const layerSection = document.getElementById('layer-selection-section');
    const loadingText = document.getElementById('loading-text');
    
    const previewGrid = document.getElementById('preview-grid');
    const layerGrid = document.getElementById('layer-grid');
    
    const previewSlicesBtn = document.getElementById('preview-slices-btn');
    const exportSelectedBtn = document.getElementById('export-selected-btn');
    
    let currentSessionId = null;

    // Drag and drop events
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); if(e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); });
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => { if (e.target.files.length) handleFile(e.target.files[0]); });

    async function handleFile(file) {
        if (!file.name.toLowerCase().endsWith('.step') && !file.name.toLowerCase().endsWith('.stp') && !file.name.toLowerCase().endsWith('.obj') && !file.name.toLowerCase().endsWith('.3mf')) return alert('Please upload a valid .step, .obj, or .3mf file.');
        const formData = new FormData(); formData.append('file', file);
        showLoading('Uploading and processing file...');

        try {
            const upRes = await fetch('/api/upload', { method: 'POST', body: formData });
            const upData = await upRes.json();
            if (!upRes.ok) throw new Error(upData.error || 'Upload failed');
            currentSessionId = upData.session_id;

            // Render Hierarchy
            renderHierarchy(upData.hierarchy);

            layerSection.classList.add('hidden'); // hide layer section when new file is loaded
            showWorkspace();
        } catch (err) {
            alert(err.message);
            resetUI();
        }
    }

    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const exampleId = btn.dataset.example;
            showLoading(`Loading example ${exampleId}...`);
            try {
                const res = await fetch(`/api/load_example/${exampleId}`, { method: 'POST' });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to load example');
                
                currentSessionId = data.session_id;
                renderHierarchy(data.hierarchy);
                layerSection.classList.add('hidden');
                showWorkspace();
            } catch (err) {
                alert(err.message);
                resetUI();
            }
        });
    });

    const chooseNewFileBtn = document.getElementById('choose-new-file-btn');
    if (chooseNewFileBtn) {
        chooseNewFileBtn.addEventListener('click', () => {
            currentSessionId = null;
            document.getElementById('hierarchy-container').innerHTML = '';
            document.getElementById('resolume-sidebar-layers').innerHTML = '';
            document.getElementById('layer-grid').innerHTML = '';
            layerInputSources = {};
            resetUI();
        });
    }

    function renderHierarchy(hierarchy) {
        const container = document.getElementById('hierarchy-container');
        container.innerHTML = '';
        if (!hierarchy) {
            container.innerHTML = '<p style="color: #888;">No hierarchy found.</p>';
            return;
        }

        function createNode(node) {
            const div = document.createElement('div');
            div.style.marginBottom = '2px';
            
            const header = document.createElement('div');
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '5px';
            
            const expandBtn = document.createElement('span');
            expandBtn.style.cursor = 'pointer';
            expandBtn.style.width = '12px';
            expandBtn.style.display = 'inline-block';
            
            const hasChildren = node.children && node.children.length > 0;
            expandBtn.innerHTML = hasChildren ? '▼' : '';
            
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = true;
            cb.className = 'node-checkbox';
            cb.dataset.node = node.id;
            
            const label = document.createElement('span');
            label.textContent = node.name;
            if (node.geom) {
                const badge = document.createElement('span');
                badge.textContent = ' ⚙';
                badge.style.color = '#fca311';
                label.appendChild(badge);
            }
            
            header.appendChild(expandBtn);
            header.appendChild(cb);
            header.appendChild(label);
            div.appendChild(header);
            
            if (hasChildren) {
                const childrenDiv = document.createElement('div');
                childrenDiv.style.marginLeft = '15px';
                
                node.children.forEach(child => {
                    childrenDiv.appendChild(createNode(child));
                });
                
                expandBtn.addEventListener('click', () => {
                    const isHidden = childrenDiv.style.display === 'none';
                    childrenDiv.style.display = isHidden ? 'block' : 'none';
                    expandBtn.innerHTML = isHidden ? '▼' : '▶';
                });
                
                cb.addEventListener('change', (e) => {
                    const childCbs = childrenDiv.querySelectorAll('.node-checkbox');
                    childCbs.forEach(c => c.checked = e.target.checked);
                });
                
                div.appendChild(childrenDiv);
            }
            
            return div;
        }

        container.appendChild(createNode(hierarchy));
    }

    // Perspective Controls
    const usePerspectiveCb = document.getElementById('use-perspective');
    const cameraSettingsDiv = document.getElementById('camera-settings');
    usePerspectiveCb.addEventListener('change', (e) => {
        if (e.target.checked) cameraSettingsDiv.classList.remove('hidden');
        else cameraSettingsDiv.classList.add('hidden');
    });

    function getVisibilityState() {
        const hidden_groups = [];
        const hidden_bodies = [];
        document.querySelectorAll('.group-checkbox').forEach(cb => {
            if (!cb.checked) hidden_groups.push(cb.dataset.group);
        });
        document.querySelectorAll('.body-checkbox').forEach(cb => {
            if (!cb.checked) hidden_bodies.push(cb.dataset.body);
        });
        return { hidden_groups, hidden_bodies };
    }

    function getCameraSettings() {
        if (!usePerspectiveCb.checked) return null;
        return {
            pos: [
                parseFloat(document.getElementById('cam-eye-x').value),
                parseFloat(document.getElementById('cam-eye-y').value),
                parseFloat(document.getElementById('cam-eye-z').value)
            ],
            target: [
                parseFloat(document.getElementById('cam-tgt-x').value),
                parseFloat(document.getElementById('cam-tgt-y').value),
                parseFloat(document.getElementById('cam-tgt-z').value)
            ],
            fov: parseFloat(document.getElementById('cam-fov').value)
        };
    }

    function getOrthoSettings() {
        return {
            eye: [
                parseFloat(document.getElementById('ortho-eye-x').value),
                parseFloat(document.getElementById('ortho-eye-y').value),
                parseFloat(document.getElementById('ortho-eye-z').value)
            ],
            target: [
                parseFloat(document.getElementById('ortho-tgt-x').value),
                parseFloat(document.getElementById('ortho-tgt-y').value),
                parseFloat(document.getElementById('ortho-tgt-z').value)
            ]
        };
    }

    const camFovSlider = document.getElementById('cam-fov');
    const camFovDisplay = document.getElementById('cam-fov-display');
    const modalCamFovSlider = document.getElementById('modal-cam-fov');
    const modalCamFovDisplay = document.getElementById('modal-cam-fov-display');
    let fovDebounceTimer;

    function syncFovAndPreview(value) {
        if(camFovSlider) camFovSlider.value = value;
        if(modalCamFovSlider) modalCamFovSlider.value = value;
        if(camFovDisplay) camFovDisplay.textContent = `${value}°`;
        if(modalCamFovDisplay) modalCamFovDisplay.textContent = `${value}°`;
        
        clearTimeout(fovDebounceTimer);
        fovDebounceTimer = setTimeout(() => {
            if (currentSessionId) {
                const resolumePreviewModal = document.getElementById('resolume-preview-modal');
                if (resolumePreviewModal && !resolumePreviewModal.classList.contains('hidden') && currentSelectedLayersInfo.length > 0) {
                    const resolumePreviewBtn = document.getElementById('preview-resolume-btn');
                    if(resolumePreviewBtn) resolumePreviewBtn.click();
                } else if (document.querySelectorAll('.node-checkbox:checked').length > 0) {
                    previewSlicesBtn.click();
                }
            }
        }, 300);
    }

    if(camFovSlider) {
        camFovSlider.addEventListener('input', (e) => syncFovAndPreview(e.target.value));
    }
    if(modalCamFovSlider) {
        modalCamFovSlider.addEventListener('input', (e) => syncFovAndPreview(e.target.value));
    }

    // New step: Preview Slices
    previewSlicesBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const selected_nodes = Array.from(document.querySelectorAll('.node-checkbox:checked')).map(cb => cb.dataset.node);
        
        if (selected_nodes.length === 0) return alert('Please select at least one component from the Scene Hierarchy.');
        
        const camera_settings = getCameraSettings();
        const ortho_settings = getOrthoSettings();
        
        const payload = { 
            selected_nodes,
            camera_settings,
            ortho_settings
        };
        
        const origText = previewSlicesBtn.textContent;
        previewSlicesBtn.textContent = 'Generating component previews...';
        previewSlicesBtn.disabled = true;

        try {
            const res = await fetch(`/api/preview_export/${currentSessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Layer preview failed');

            renderLayerPreviews(data.layers);
            layerSection.classList.remove('hidden');
            // Scroll to the layer section
            layerSection.scrollIntoView({ behavior: 'smooth' });
        } catch (err) {
            alert(err.message);
        } finally {
            previewSlicesBtn.textContent = origText;
            previewSlicesBtn.disabled = false;
        }
    });

    function renderLayerPreviews(layers) {
        layerGrid.innerHTML = '';
        const template = document.getElementById('layer-card-template');
        const axisLabels = { 'x':'X-Axis', '-x':'-X-Axis', 'y':'Y-Axis', '-y':'-Y-Axis', 'z':'Z-Axis', '-z':'-Z-Axis' };

        layers.forEach(layer => {
            const clone = template.content.cloneNode(true);
            const imgInput = clone.querySelector('.img-input');
            const imgOutput = clone.querySelector('.img-output');
            const checkbox = clone.querySelector('.layer-checkbox');
            const title = clone.querySelector('.layer-title');
            const subtitle = clone.querySelector('.layer-subtitle');

            imgInput.src = layer.src_input;
            imgOutput.src = layer.src_output;
            checkbox.value = layer.id;
            checkbox.id = `layer-chk-${layer.id}`;
            
            // Format labels cleanly
            title.textContent = layer.label;
            subtitle.textContent = axisLabels[layer.axis] || layer.axis;
            
            // Link checkbox label behavior
            const controlDiv = clone.querySelector('.layer-controls div');
            controlDiv.style.cursor = 'pointer';
            controlDiv.addEventListener('click', () => { checkbox.checked = !checkbox.checked; });

            layerGrid.appendChild(clone);
        });
    }

    const resolumePreviewBtn = document.getElementById('preview-resolume-btn');
    const resolumePreviewModal = document.getElementById('resolume-preview-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const svgCanvas = document.getElementById('resolume-svg-canvas');
    
    const resolumeSidebarLayers = document.getElementById('resolume-sidebar-layers');

    let currentSelectedLayersInfo = [];
    let layerInputSources = {}; // Maps layer_id -> "0:1"

    function getVisibilityState() {
        const hidden_nodes = [];
        document.querySelectorAll('.node-checkbox').forEach(cb => {
            if (!cb.checked) hidden_nodes.push(cb.dataset.node);
        });
        return { hidden_groups: hidden_nodes, hidden_bodies: [] };
    }

    resolumePreviewBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const layerCheckboxes = Array.from(document.querySelectorAll('.layer-checkbox:checked'));
        if (layerCheckboxes.length === 0) return alert('Please select at least one layer to export.');

        // Extract custom names
        currentSelectedLayersInfo = layerCheckboxes.map(cb => {
            const card = cb.closest('.axis-card');
            const customNameInput = card.querySelector('.layer-custom-name');
            return {
                id: cb.value,
                name: customNameInput.value.trim() || cb.value
            };
        });

        const width = document.getElementById('out-width').value;
        const height = document.getElementById('out-height').value;
        
        const visState = getVisibilityState();
        const camera_settings = getCameraSettings();

        const originalText = resolumePreviewBtn.textContent;
        resolumePreviewBtn.textContent = 'Generating Preview Layout...';
        resolumePreviewBtn.disabled = true;

        try {
            const res = await fetch(`/api/resolume_preview/${currentSessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_nodes: currentSelectedLayersInfo.map(l => l.id),
                    width: parseInt(width),
                    height: parseInt(height),
                    hidden_groups: visState.hidden_groups,
                    hidden_bodies: visState.hidden_bodies,
                    camera_settings,
                    ortho_settings: getOrthoSettings(),
                    cull_backfaces: document.getElementById('cull-backfaces').checked
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Preview failed');
            }

            const data = await res.json();
            renderSVGPreview(data.polygons, width, height);
            resolumePreviewModal.classList.remove('hidden');
        } catch (err) {
            alert(err.message);
        } finally {
            resolumePreviewBtn.textContent = originalText;
            resolumePreviewBtn.disabled = false;
        }
    });

    closeModalBtn.addEventListener('click', () => {
        resolumePreviewModal.classList.add('hidden');
    });

    function renderSVGPreview(polygonData, width, height) {
        const svgCanvasInput = document.getElementById('resolume-svg-canvas-input');
        const svgCanvasOutput = document.getElementById('resolume-svg-canvas-output');
        
        svgCanvasInput.innerHTML = '';
        svgCanvasOutput.innerHTML = '';
        
        svgCanvasInput.setAttribute('viewBox', `0 0 ${width} ${height}`);
        svgCanvasOutput.setAttribute('viewBox', `0 0 ${width} ${height}`);
        
        const previousInputSources = { ...layerInputSources };
        resolumeSidebarLayers.innerHTML = ''; // Clear sidebar
        layerInputSources = {}; // Reset mappings

        polygonData.forEach((polyGroup, idx) => {
            layerInputSources[polyGroup.layer_id] = previousInputSources[polyGroup.layer_id] || "0:1"; // Restore previous or default
            
            const groupColor = `hsl(${(idx * 137.5) % 360}, 75%, 60%)`;
            
            // Build Input SVG Group
            const gIn = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            gIn.setAttribute('class', 'preview-poly-group');
            gIn.style.cursor = 'pointer';
            gIn.dataset.layerId = polyGroup.layer_id;

            // Build Output SVG Group
            const gOut = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            gOut.setAttribute('class', 'preview-poly-group');
            gOut.style.cursor = 'pointer';
            gOut.dataset.layerId = polyGroup.layer_id;

            if (polyGroup.resolume_loops) {
                polyGroup.resolume_loops.forEach(rLoop => {
                    // Draw Input Loop
                    if (rLoop.input && rLoop.input.length > 0) {
                        const polyIn = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
                        const pointsIn = rLoop.input.map(pt => `${pt[0]},${pt[1]}`).join(' ');
                        polyIn.setAttribute('points', pointsIn);
                        polyIn.setAttribute('fill', groupColor);
                        polyIn.setAttribute('fill-opacity', '0.2');
                        polyIn.setAttribute('stroke', groupColor);
                        polyIn.setAttribute('stroke-width', '2');
                        gIn.appendChild(polyIn);
                    }
                    
                    // Draw Output Loop
                    if (rLoop.output && rLoop.output.length > 0) {
                        const polyOut = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
                        const pointsOut = rLoop.output.map(pt => `${pt[0]},${pt[1]}`).join(' ');
                        polyOut.setAttribute('points', pointsOut);
                        polyOut.setAttribute('fill', groupColor);
                        polyOut.setAttribute('fill-opacity', '0.2');
                        polyOut.setAttribute('stroke', groupColor);
                        polyOut.setAttribute('stroke-width', '2');
                        gOut.appendChild(polyOut);
                    }
                });
            }
            
            // Build Sidebar Row
            const row = document.createElement('div');
            row.style.background = 'rgba(255,255,255,0.05)';
            row.style.padding = '8px';
            row.style.marginBottom = '5px';
            row.style.borderRadius = '4px';
            row.style.display = 'flex';
            row.style.justifyContent = 'space-between';
            row.style.alignItems = 'center';
            row.style.cursor = 'pointer';
            row.style.borderLeft = `3px solid ${groupColor}`;
            row.dataset.layerId = polyGroup.layer_id;
            
            // Re-map name using original custom name if exists
            const mappedInfo = currentSelectedLayersInfo.find(l => l.id === polyGroup.layer_id);
            const titleStr = mappedInfo ? mappedInfo.name : polyGroup.layer_id;
            
            row.innerHTML = `
                <div style="font-size: 11px; font-weight: bold; color: #fff; width: 100px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${titleStr}">${titleStr}</div>
                <div style="display:flex; flex-direction:column; gap:4px; max-width:140px;">
                    <select class="sidebar-select hidden" style="background:#000; color:#fff; border:1px solid #444; padding:3px; border-radius:3px; font-size:10px; width:100%;"></select>
                    <input type="text" class="sidebar-input" value="${layerInputSources[polyGroup.layer_id]}" style="background:#000; color:#fff; border:1px solid #444; padding:3px; border-radius:3px; font-size:10px; width:100%;">
                </div>
            `;
            
            resolumeSidebarLayers.appendChild(row);
            
            // Sync logic
            const selectInput = row.querySelector('.sidebar-select');
            const textInput = row.querySelector('.sidebar-input');
            
            // Hydrate select with existing options if they were fetched already
            if (availableResolumeLayerOptions.length > 1) { // More than just composition
                availableResolumeLayerOptions.forEach(opt => {
                    const optionEl = document.createElement('option');
                    optionEl.value = opt.value;
                    optionEl.textContent = opt.name;
                    selectInput.appendChild(optionEl);
                });
                selectInput.value = layerInputSources[polyGroup.layer_id];
                selectInput.classList.remove('hidden');
            }
            
            selectInput.addEventListener('change', (e) => {
                textInput.value = e.target.value;
                layerInputSources[polyGroup.layer_id] = e.target.value;
            });
            textInput.addEventListener('input', (e) => {
                layerInputSources[polyGroup.layer_id] = e.target.value;
            });

            // Hover two-way binds
            const highlight = () => {
                row.style.background = 'rgba(255,255,255,0.15)';
                Array.from(gIn.children).forEach(p => p.setAttribute('fill-opacity', '0.6'));
                Array.from(gOut.children).forEach(p => p.setAttribute('fill-opacity', '0.6'));
            };
            const unhighlight = () => {
                row.style.background = 'rgba(255,255,255,0.05)';
                Array.from(gIn.children).forEach(p => p.setAttribute('fill-opacity', '0.2'));
                Array.from(gOut.children).forEach(p => p.setAttribute('fill-opacity', '0.2'));
            };

            row.addEventListener('mouseenter', highlight);
            row.addEventListener('mouseleave', unhighlight);
            gIn.addEventListener('mouseenter', highlight);
            gIn.addEventListener('mouseleave', unhighlight);
            gOut.addEventListener('mouseenter', highlight);
            gOut.addEventListener('mouseleave', unhighlight);

            svgCanvasInput.appendChild(gIn);
            svgCanvasOutput.appendChild(gOut);
        });
    }

    const fetchLayersBtn = document.getElementById('fetch-layers-btn');
    const apiStatusText = document.getElementById('api-status-text');
    const resolumeApiUrl = document.getElementById('resolume-api-url');
    const popoverSelect = document.getElementById('popover-select-source');

    let availableResolumeLayerOptions = [
        {name: "Composition", value: "0:1"}
    ];

    fetchLayersBtn.addEventListener('click', async () => {
        const urlStr = resolumeApiUrl.value.trim();
        if (!urlStr) return;

        apiStatusText.textContent = "Connecting...";
        apiStatusText.style.color = "#888";
        fetchLayersBtn.disabled = true;

        let compData = null;

        try {
            // First attempt: Direct fetch from browser (Best for resolving Windows localhost in WSL environments)
            try {
                const directRes = await fetch(urlStr);
                if (directRes.ok) {
                    compData = await directRes.json();
                }
            } catch (err) {
                console.warn("Direct fetch failed (likely CORS or WSL network). Falling back to Python local proxy...", err);
            }

            // Second attempt: Proxy via Python backend
            if (!compData) {
                const res = await fetch('/api/resolume_proxy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: urlStr })
                });

                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.error || 'Proxy connection failed');
                }
                compData = await res.json();
            }
            
            // Build options array
            let options = [];
            options.push({name: compData.name?.value || "Composition", value: "0:1"});
            
            // Extract layers
            if (compData.layers) {
                compData.layers.forEach((layer, idx) => {
                    options.push({
                        name: layer.name?.value || `Layer ${idx+1}`,
                        value: `1:${idx+1}` // Wild guess, will check when outputting
                    });
                });
            }
            
            availableResolumeLayerOptions = options;
            
            // Re-populate all sidebar selects
            document.querySelectorAll('#resolume-sidebar-layers .sidebar-select').forEach(selectInput => {
                selectInput.innerHTML = '';
                availableResolumeLayerOptions.forEach(opt => {
                    const optionEl = document.createElement('option');
                    optionEl.value = opt.value;
                    optionEl.textContent = opt.name;
                    selectInput.appendChild(optionEl);
                });
                selectInput.classList.remove('hidden');
                
                // Try selecting existing mapped val
                const layerId = selectInput.closest('[data-layer-id]')?.dataset?.layerId;
                if (layerId && layerInputSources[layerId]) {
                    // if current text val matches an option, select it
                    selectInput.value = layerInputSources[layerId];
                }
            });
            
            apiStatusText.textContent = `Found ${options.length} source(s)!`;
            apiStatusText.style.color = "#4CAF50";

        } catch (err) {
            console.error(err);
            apiStatusText.textContent = err.message.substring(0, 40);
            apiStatusText.style.color = "#f44336";
        } finally {
            fetchLayersBtn.disabled = false;
        }
    });

    // Final export functionality 
    const exportXmlBtn = document.getElementById('export-xml-btn');
    const exportPngBtn = document.getElementById('export-png-btn');

    async function handleExport(exportType, buttonElement) {
        if (!currentSessionId) return;

        const width = document.getElementById('out-width').value;
        const height = document.getElementById('out-height').value;

        // Build Payload
        const layer_configs = currentSelectedLayersInfo.map(info => {
            return {
                id: info.id,
                name: info.name,
                input_source: layerInputSources[info.id] || "0:1"
            };
        });
        
        const visState = getVisibilityState();
        const camera_settings = getCameraSettings();
        const ortho_settings = getOrthoSettings();
        const cullBackfaces = document.getElementById('cull-backfaces').checked;

        const payload = {
            layer_configs: layer_configs,
            width: parseInt(width),
            height: parseInt(height),
            hidden_groups: visState.hidden_groups,
            hidden_bodies: visState.hidden_bodies,
            camera_settings,
            ortho_settings,
            cull_backfaces: cullBackfaces,
            export_type: exportType
        };

        const originalText = buttonElement.textContent;
        buttonElement.textContent = 'Generating...';
        buttonElement.disabled = true;

        try {
            const res = await fetch(`/api/export/${currentSessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Export failed');
            }

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.style.display = 'none'; a.href = url;
            
            const disposition = res.headers.get('Content-Disposition');
            let filename = `export_${exportType}.zip`;
            if (disposition && disposition.indexOf('attachment') !== -1) {
                const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
                if (matches != null && matches[1]) filename = matches[1].replace(/['"]/g, '');
            }
            
            a.download = filename; document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url);
            
            resolumePreviewModal.classList.add('hidden');
        } catch (err) {
            alert(err.message);
        } finally {
            buttonElement.textContent = originalText;
            buttonElement.disabled = false;
        }
    }

    exportSelectedBtn.addEventListener('click', () => handleExport('all', exportSelectedBtn));
    exportXmlBtn.addEventListener('click', () => handleExport('xml', exportXmlBtn));
    exportPngBtn.addEventListener('click', () => handleExport('png', exportPngBtn));

    function showLoading(text) { uploadSection.classList.add('hidden'); workspaceSection.classList.add('hidden'); loadingSection.classList.remove('hidden'); loadingText.textContent = text; }
    function showWorkspace() { loadingSection.classList.add('hidden'); workspaceSection.classList.remove('hidden'); }
    function resetUI() { loadingSection.classList.add('hidden'); workspaceSection.classList.add('hidden'); uploadSection.classList.remove('hidden'); fileInput.value = ''; layerSection.classList.add('hidden'); resolumePreviewModal.classList.add('hidden'); }
});
