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
        if (!file.name.toLowerCase().endsWith('.3mf')) return alert('Please upload a valid .3mf file.');
        const formData = new FormData(); formData.append('file', file);
        showLoading('Uploading and processing 3MF...');

        try {
            const upRes = await fetch('/api/upload', { method: 'POST', body: formData });
            const upData = await upRes.json();
            if (!upRes.ok) throw new Error(upData.error || 'Upload failed');
            currentSessionId = upData.session_id;

            showLoading('Rendering structural axes previews...');
            const prevRes = await fetch(`/api/preview/${currentSessionId}`, { method: 'POST' });
            const prevData = await prevRes.json();
            if (!prevRes.ok) throw new Error(prevData.error || 'Preview failed');

            renderAxesPreviews(prevData.previews);
            showWorkspace();
        } catch (err) {
            alert(err.message);
            resetUI();
        }
    }

    function renderAxesPreviews(previews) {
        previewGrid.innerHTML = '';
        layerSection.classList.add('hidden'); // hide layer section when new file is loaded
        
        const template = document.getElementById('axis-card-template');
        const labels = { 'x':'Right (X)', '-x':'Left (-X)', 'y':'Back (Y)', '-y':'Front (-Y)', 'z':'Top (Z)', '-z':'Bottom (-Z)' };

        for (const [axis, src] of Object.entries(previews)) {
            const clone = template.content.cloneNode(true);
            const img = clone.querySelector('img');
            const checkbox = clone.querySelector('.axis-checkbox');
            const label = clone.querySelector('.axis-label');

            img.src = src;
            checkbox.value = axis;
            checkbox.id = `chk-${axis}`;
            label.htmlFor = `chk-${axis}`;
            label.textContent = labels[axis] || axis;

            previewGrid.appendChild(clone);
        }
    }

    // New step: Preview Slices
    previewSlicesBtn.addEventListener('click', async () => {
        if (!currentSessionId) return;

        const selectedAxes = Array.from(document.querySelectorAll('.axis-checkbox:checked')).map(cb => cb.value);
        if (selectedAxes.length === 0) return alert('Please select at least one Axis above to preview.');
        
        const split_depths = document.getElementById('split-depths').checked;
        const payload = { axes: selectedAxes, split_depths };
        
        const origText = previewSlicesBtn.textContent;
        previewSlicesBtn.textContent = 'Generating layer previews...';
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
            const img = clone.querySelector('img');
            const checkbox = clone.querySelector('.layer-checkbox');
            const title = clone.querySelector('.layer-title');
            const subtitle = clone.querySelector('.layer-subtitle');

            img.src = layer.src;
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

        const originalText = resolumePreviewBtn.textContent;
        resolumePreviewBtn.textContent = 'Generating Preview Layout...';
        resolumePreviewBtn.disabled = true;

        try {
            const res = await fetch(`/api/resolume_preview/${currentSessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_layers: currentSelectedLayersInfo.map(l => l.id),
                    width: parseInt(width),
                    height: parseInt(height)
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
        svgCanvas.innerHTML = '';
        svgCanvas.setAttribute('viewBox', `0 0 ${width} ${height}`);
        resolumeSidebarLayers.innerHTML = ''; // Clear sidebar
        layerInputSources = {}; // Reset mappings

        polygonData.forEach((polyGroup, idx) => {
            layerInputSources[polyGroup.layer_id] = "0:1"; // Default
            
            const groupColor = `hsl(${(idx * 137.5) % 360}, 75%, 60%)`;
            
            // Build SVG Group
            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', 'preview-poly-group');
            g.style.cursor = 'pointer';
            g.dataset.layerId = polyGroup.layer_id;

            polyGroup.loops.forEach(loop => {
                const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
                const pointsStr = loop.map(pt => `${pt[0]},${pt[1]}`).join(' ');
                polygon.setAttribute('points', pointsStr);
                polygon.setAttribute('fill', groupColor);
                polygon.setAttribute('fill-opacity', '0.2');
                polygon.setAttribute('stroke', groupColor);
                polygon.setAttribute('stroke-width', '2');
                g.appendChild(polygon);
            });
            
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
                    <input type="text" class="sidebar-input" value="0:1" style="background:#000; color:#fff; border:1px solid #444; padding:3px; border-radius:3px; font-size:10px; width:100%;">
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
                Array.from(g.children).forEach(p => p.setAttribute('fill-opacity', '0.6'));
            };
            const unhighlight = () => {
                row.style.background = 'rgba(255,255,255,0.05)';
                Array.from(g.children).forEach(p => p.setAttribute('fill-opacity', '0.2'));
            };

            row.addEventListener('mouseenter', highlight);
            row.addEventListener('mouseleave', unhighlight);
            g.addEventListener('mouseenter', highlight);
            g.addEventListener('mouseleave', unhighlight);

            svgCanvas.appendChild(g);
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
    exportSelectedBtn.addEventListener('click', async () => {
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

        const payload = {
            layer_configs: layer_configs,
            width: parseInt(width),
            height: parseInt(height)
        };

        const originalText = exportSelectedBtn.textContent;
        exportSelectedBtn.textContent = 'Generating High-Res Export...';
        exportSelectedBtn.disabled = true;

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
            let filename = 'masks.zip';
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
            exportSelectedBtn.textContent = originalText;
            exportSelectedBtn.disabled = false;
        }
    });

    function showLoading(text) { uploadSection.classList.add('hidden'); workspaceSection.classList.add('hidden'); loadingSection.classList.remove('hidden'); loadingText.textContent = text; }
    function showWorkspace() { loadingSection.classList.add('hidden'); workspaceSection.classList.remove('hidden'); }
    function resetUI() { loadingSection.classList.add('hidden'); workspaceSection.classList.add('hidden'); uploadSection.classList.remove('hidden'); fileInput.value = ''; layerSection.classList.add('hidden'); resolumePreviewModal.classList.add('hidden'); }
});
