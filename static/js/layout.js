/* ============================================================
   Layout editor - drag & drop grid arrangement for the matrix
   ============================================================ */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var dataEl = document.getElementById('layout-data');
        if (!dataEl) {
            return;
        }

        var data = JSON.parse(dataEl.textContent);
        var layout = data.layout || {};
        layout.grid = layout.grid || {};
        layout.widgets = Array.isArray(layout.widgets) ? layout.widgets : [];
        var widgets = layout.widgets;

        var csrfToken = data.csrfToken;
        var matrixWidth = parseInt(data.matrixWidth, 10) || 64;
        var matrixHeight = parseInt(data.matrixHeight, 10) || 32;
        // Grid geometry comes from the server (derived from settings.json) so
        // the editor can never disagree with the renderer.
        var gridCols = Math.max(1, parseInt(data.cols, 10) || 1);
        var gridRows = Math.max(1, parseInt(data.rows, 10) || 1);
        var gridCellW = Math.max(1, parseInt(data.cellW, 10) || 32);
        var gridCellH = Math.max(1, parseInt(data.cellH, 10) || 32);
        var pictures = data.pictures || [];
        var widgetDefaults = data.widgetDefaults || {};
        var widgetTypes = data.widgetTypes || [];

        var TYPE_LABELS = {
            clock: 'Clock',
            days_until: 'Days until',
            api_text: 'API text',
            static_text: 'Static text',
            image: 'Image'
        };
        var DEFAULT_SIZE = {
            clock: [3, 1],
            days_until: [3, 1],
            api_text: [3, 1],
            static_text: [3, 1],
            image: [1, 1]
        };

        var board = document.getElementById('matrix-board');
        var widgetsLayer = document.getElementById('matrix-widgets');
        var inspector = document.getElementById('widget-inspector');
        var palette = document.getElementById('widget-palette');
        var statusEl = document.getElementById('layout-status');
        var dimsLabel = document.getElementById('grid-dims-label');

        var selectedId = null;
        var scale = 1;

        // --- helpers ------------------------------------------------------
        function clone(object) {
            return JSON.parse(JSON.stringify(object));
        }

        function clamp(value, min, max) {
            return Math.max(min, Math.min(max, value));
        }

        function cellW() {
            return gridCellW;
        }

        function cellH() {
            return gridCellH;
        }

        function cols() {
            return gridCols;
        }

        function rows() {
            return gridRows;
        }

        function toHex(rgb) {
            if (!Array.isArray(rgb) || rgb.length < 3) {
                rgb = [255, 255, 255];
            }
            return '#' + rgb.slice(0, 3).map(function (c) {
                var v = clamp(parseInt(c, 10) || 0, 0, 255).toString(16);
                return v.length === 1 ? '0' + v : v;
            }).join('');
        }

        function fromHex(hex) {
            var value = (hex || '#ffffff').replace('#', '');
            if (value.length === 3) {
                value = value.split('').map(function (c) { return c + c; }).join('');
            }
            return [
                parseInt(value.substring(0, 2), 16) || 0,
                parseInt(value.substring(2, 4), 16) || 0,
                parseInt(value.substring(4, 6), 16) || 0
            ];
        }

        function generateId() {
            return 'w' + Math.random().toString(16).slice(2, 10);
        }

        function styleOf(widget) {
            widget.style = widget.style || {};
            return widget.style;
        }

        function configOf(widget) {
            widget.config = widget.config || {};
            return widget.config;
        }

        function overlaps(a, b) {
            return a.col < b.col + b.w && b.col < a.col + a.w &&
                a.row < b.row + b.h && b.row < a.row + a.h;
        }

        function overlapsAny(candidate, list) {
            return list.some(function (other) { return overlaps(candidate, other); });
        }

        function inBounds(candidate) {
            return candidate.col >= 0 && candidate.row >= 0 &&
                candidate.col + candidate.w <= cols() &&
                candidate.row + candidate.h <= rows();
        }

        function fits(candidate, ignoreId) {
            if (!inBounds(candidate)) {
                return false;
            }
            var others = widgets.filter(function (w) { return w.id !== ignoreId; });
            return !overlapsAny(candidate, others);
        }

        function findSpot(width, height, list) {
            list = list || [];
            for (var row = 0; row <= rows() - height; row++) {
                for (var col = 0; col <= cols() - width; col++) {
                    var candidate = { col: col, row: row, w: width, h: height };
                    if (!overlapsAny(candidate, list)) {
                        return candidate;
                    }
                }
            }
            return null;
        }

        function describe(widget) {
            var config = widget.config || {};
            switch (widget.type) {
                case 'clock':
                    return 'Clock';
                case 'days_until':
                    return config.label || 'Countdown';
                case 'api_text':
                    if (config.url) {
                        try {
                            return new URL(config.url).hostname;
                        } catch (e) {
                            return 'API';
                        }
                    }
                    return 'API';
                case 'static_text':
                    return config.text || 'Text';
                case 'image':
                    return config.filename || 'Image';
                default:
                    return widget.type;
            }
        }

        function setStatus(message, kind) {
            if (!statusEl) {
                return;
            }
            statusEl.textContent = message || '';
            statusEl.className = 'layout-status' + (kind ? ' layout-status--' + kind : '');
            if (message) {
                window.clearTimeout(setStatus._timer);
                setStatus._timer = window.setTimeout(function () {
                    statusEl.textContent = '';
                    statusEl.className = 'layout-status';
                }, 5000);
            }
        }

        // --- rendering ----------------------------------------------------
        function applyBoardSize() {
            var wrap = board.parentElement;
            var available = Math.max(240, wrap.clientWidth - 8);
            scale = Math.min(available / matrixWidth, 4);
            board.style.width = (matrixWidth * scale) + 'px';
            board.style.height = (matrixHeight * scale) + 'px';
            board.style.backgroundSize =
                (cellW() * scale) + 'px ' + (cellH() * scale) + 'px';
            if (dimsLabel) {
                dimsLabel.textContent = cols() + ' × ' + rows();
            }
        }

        function renderBlocks() {
            widgetsLayer.innerHTML = '';
            widgets.forEach(function (widget) {
                var el = document.createElement('div');
                el.className = 'widget-block widget-block--' + widget.type;
                if (widget.id === selectedId) {
                    el.classList.add('widget-block--selected');
                }
                el.style.left = (widget.col * cellW() * scale) + 'px';
                el.style.top = (widget.row * cellH() * scale) + 'px';
                el.style.width = Math.max(8, widget.w * cellW() * scale - 1) + 'px';
                el.style.height = Math.max(8, widget.h * cellH() * scale - 1) + 'px';
                el.style.color = toHex((widget.style || {}).color);

                var label = document.createElement('span');
                label.className = 'widget-block__label';
                label.textContent = describe(widget);
                el.appendChild(label);

                var handle = document.createElement('div');
                handle.className = 'widget-block__resize';
                el.appendChild(handle);

                el.addEventListener('pointerdown', function (event) {
                    if (event.target === handle) {
                        return;
                    }
                    startDrag(event, widget, 'move');
                });
                handle.addEventListener('pointerdown', function (event) {
                    event.stopPropagation();
                    startDrag(event, widget, 'resize');
                });

                widgetsLayer.appendChild(el);
            });
        }

        function startDrag(event, widget, mode) {
            event.preventDefault();
            selectWidget(widget.id);

            var startX = event.clientX;
            var startY = event.clientY;
            var origin = { col: widget.col, row: widget.row, w: widget.w, h: widget.h };
            var stepX = cellW() * scale;
            var stepY = cellH() * scale;

            document.body.classList.add('is-dragging');

            function onMove(moveEvent) {
                var dCol = Math.round((moveEvent.clientX - startX) / stepX);
                var dRow = Math.round((moveEvent.clientY - startY) / stepY);
                var candidate = {
                    col: origin.col,
                    row: origin.row,
                    w: origin.w,
                    h: origin.h
                };

                if (mode === 'move') {
                    candidate.col = clamp(origin.col + dCol, 0, cols() - origin.w);
                    candidate.row = clamp(origin.row + dRow, 0, rows() - origin.h);
                } else {
                    candidate.w = clamp(origin.w + dCol, 1, cols() - origin.col);
                    candidate.h = clamp(origin.h + dRow, 1, rows() - origin.row);
                }

                if (fits(candidate, widget.id)) {
                    widget.col = candidate.col;
                    widget.row = candidate.row;
                    widget.w = candidate.w;
                    widget.h = candidate.h;
                    renderBlocks();
                }
            }

            function onUp() {
                document.removeEventListener('pointermove', onMove);
                document.removeEventListener('pointerup', onUp);
                document.body.classList.remove('is-dragging');
            }

            document.addEventListener('pointermove', onMove);
            document.addEventListener('pointerup', onUp);
        }

        // --- inspector ----------------------------------------------------
        function fieldWrap(labelText) {
            var wrapper = document.createElement('div');
            wrapper.className = 'inspector__field';
            var label = document.createElement('label');
            label.className = 'field__label';
            label.textContent = labelText;
            wrapper.appendChild(label);
            return wrapper;
        }

        function addText(parent, labelText, value, onChange) {
            var wrapper = fieldWrap(labelText);
            var input = document.createElement('input');
            input.className = 'field__input';
            input.type = 'text';
            input.value = value == null ? '' : value;
            input.addEventListener('input', function () { onChange(input.value); });
            wrapper.appendChild(input);
            parent.appendChild(wrapper);
        }

        function addNumber(parent, labelText, value, onChange, min, max) {
            var wrapper = fieldWrap(labelText);
            var input = document.createElement('input');
            input.className = 'field__input';
            input.type = 'number';
            if (min != null) { input.min = min; }
            if (max != null) { input.max = max; }
            input.value = value == null ? '' : value;
            input.addEventListener('input', function () {
                var parsed = parseInt(input.value, 10);
                onChange(isNaN(parsed) ? 0 : parsed);
            });
            wrapper.appendChild(input);
            parent.appendChild(wrapper);
        }

        function addSelect(parent, labelText, value, options, onChange) {
            var wrapper = fieldWrap(labelText);
            var select = document.createElement('select');
            select.className = 'field__input';
            options.forEach(function (option) {
                var el = document.createElement('option');
                el.value = option[0];
                el.textContent = option[1];
                if (option[0] === value) {
                    el.selected = true;
                }
                select.appendChild(el);
            });
            select.addEventListener('change', function () { onChange(select.value); });
            wrapper.appendChild(select);
            parent.appendChild(wrapper);
        }

        function addCheckbox(parent, labelText, checked, onChange) {
            var label = document.createElement('label');
            label.className = 'checkbox inspector__checkbox';
            var input = document.createElement('input');
            input.type = 'checkbox';
            input.className = 'checkbox__input';
            input.checked = !!checked;
            input.addEventListener('change', function () { onChange(input.checked); });
            var span = document.createElement('span');
            span.className = 'checkbox__label';
            span.textContent = labelText;
            label.appendChild(input);
            label.appendChild(span);
            parent.appendChild(label);
        }

        function renderInspector() {
            inspector.innerHTML = '';
            var widget = widgets.filter(function (w) { return w.id === selectedId; })[0];
            if (!widget) {
                var hint = document.createElement('p');
                hint.className = 'layout-editor__hint';
                hint.textContent = 'Select a block to edit it.';
                inspector.appendChild(hint);
                return;
            }

            var header = document.createElement('div');
            header.className = 'inspector__header';
            var title = document.createElement('strong');
            title.textContent = TYPE_LABELS[widget.type] || widget.type;
            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn btn--ghost btn--icon';
            remove.innerHTML = '<i class="material-icons" style="font-size:18px;">delete</i>';
            remove.title = 'Delete block';
            remove.addEventListener('click', function () {
                widgets = widgets.filter(function (w) { return w.id !== widget.id; });
                layout.widgets = widgets;
                selectedId = null;
                renderBlocks();
                renderInspector();
            });
            header.appendChild(title);
            header.appendChild(remove);
            inspector.appendChild(header);

            var style = styleOf(widget);
            var config = configOf(widget);

            var colorWrap = fieldWrap('Colour');
            var colorInput = document.createElement('input');
            colorInput.type = 'color';
            colorInput.className = 'field__input inspector__color';
            colorInput.value = toHex(style.color);
            colorInput.addEventListener('input', function () {
                style.color = fromHex(colorInput.value);
                renderBlocks();
            });
            colorWrap.appendChild(colorInput);
            inspector.appendChild(colorWrap);

            addSelect(inspector, 'Align', style.align || 'center', [
                ['left', 'Left'], ['center', 'Center'], ['right', 'Right']
            ], function (value) {
                style.align = value;
                renderBlocks();
            });

            if (widget.type === 'clock') {
                addText(inspector, 'Time format (strftime)', config.timeFormat || '', function (v) {
                    config.timeFormat = v;
                });
                addText(inspector, 'Date format (strftime)', config.dateFormat || '', function (v) {
                    config.dateFormat = v;
                });
            } else if (widget.type === 'days_until') {
                addNumber(inspector, 'Month', config.month || 12, function (v) { config.month = v; }, 1, 12);
                addNumber(inspector, 'Day', config.day || 25, function (v) { config.day = v; }, 1, 31);
                addText(inspector, 'Year (blank = recurring)', config.year || '', function (v) {
                    config.year = v === '' ? null : parseInt(v, 10);
                });
                addCheckbox(inspector, 'Recurring yearly', config.recurring !== false, function (v) {
                    config.recurring = v;
                });
                addText(inspector, 'Label', config.label || '', function (v) {
                    config.label = v;
                    renderBlocks();
                });
                addText(inspector, 'Template ({days} {label})', config.template || '{days}d {label}', function (v) {
                    config.template = v;
                });
                addText(inspector, 'On the day', config.finishedText || '', function (v) {
                    config.finishedText = v;
                });
            } else if (widget.type === 'api_text') {
                addText(inspector, 'URL', config.url || '', function (v) {
                    config.url = v;
                    renderBlocks();
                });
                addText(inspector, 'JSON path (e.g. main.temp)', config.jsonPath || '', function (v) {
                    config.jsonPath = v;
                });
                addText(inspector, 'Regex fallback', config.regex || '', function (v) {
                    config.regex = v;
                });
                addNumber(inspector, 'Refresh interval (s)', config.interval || 300, function (v) {
                    config.interval = v;
                }, 5, 86400);
                addText(inspector, 'Prefix', config.prefix || '', function (v) {
                    config.prefix = v;
                });
                addText(inspector, 'Suffix', config.suffix || '', function (v) {
                    config.suffix = v;
                });
                addNumber(inspector, 'Decimals', config.decimals || 0, function (v) {
                    config.decimals = v;
                }, 0, 4);
                addText(inspector, 'Error text', config.errorText || 'N/A', function (v) {
                    config.errorText = v;
                });
            } else if (widget.type === 'static_text') {
                addText(inspector, 'Text', config.text || '', function (v) {
                    config.text = v;
                    renderBlocks();
                });
                addCheckbox(inspector, 'Scroll text', config.scroll, function (v) {
                    config.scroll = v;
                });
                addNumber(inspector, 'Scroll speed (px/s)', config.speed || 20, function (v) {
                    config.speed = v;
                }, 1, 200);
            } else if (widget.type === 'image') {
                var wrapper = fieldWrap('Picture');
                var select = document.createElement('select');
                select.className = 'field__input';
                var empty = document.createElement('option');
                empty.value = '';
                empty.textContent = '— select —';
                select.appendChild(empty);
                pictures.forEach(function (name) {
                    var option = document.createElement('option');
                    option.value = name;
                    option.textContent = name;
                    if (name === config.filename) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
                select.addEventListener('change', function () {
                    config.filename = select.value;
                    renderBlocks();
                });
                wrapper.appendChild(select);
                inspector.appendChild(wrapper);

                addSelect(inspector, 'Fit', style.fit || 'cover', [
                    ['cover', 'Cover (crop)'], ['contain', 'Contain (letterbox)']
                ], function (value) {
                    style.fit = value;
                });
            }
        }

        function selectWidget(id) {
            selectedId = id;
            renderBlocks();
            renderInspector();
        }

        // --- palette / adding widgets -------------------------------------
        function addWidget(type) {
            var size = DEFAULT_SIZE[type] || [1, 1];
            var width = Math.min(size[0], cols());
            var height = Math.min(size[1], rows());
            var spot = findSpot(width, height, widgets);
            if (!spot) {
                setStatus('No free space for another block. Resize or remove one first.', 'error');
                return;
            }

            var base = widgetDefaults[type] ? clone(widgetDefaults[type]) : {
                type: type, style: {}, config: {}
            };
            base.id = generateId();
            base.type = type;
            base.col = spot.col;
            base.row = spot.row;
            base.w = width;
            base.h = height;
            widgets.push(base);
            layout.widgets = widgets;
            selectWidget(base.id);
        }

        function buildPalette() {
            palette.innerHTML = '';
            widgetTypes.forEach(function (type) {
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'palette__btn';
                button.textContent = TYPE_LABELS[type] || type;
                button.addEventListener('click', function () { addWidget(type); });
                palette.appendChild(button);
            });
        }

        // --- grid settings ------------------------------------------------
        function clampWidgets() {
            var placed = [];
            widgets.forEach(function (widget) {
                widget.w = clamp(widget.w, 1, cols());
                widget.h = clamp(widget.h, 1, rows());
                widget.col = clamp(widget.col, 0, cols() - widget.w);
                widget.row = clamp(widget.row, 0, rows() - widget.h);
                if (overlapsAny(widget, placed)) {
                    var spot = findSpot(widget.w, widget.h, placed);
                    if (spot) {
                        widget.col = spot.col;
                        widget.row = spot.row;
                    }
                }
                placed.push(widget);
            });
        }

        function bindGridSettings() {
            var bordersInput = document.getElementById('showBorders');
            if (bordersInput) {
                bordersInput.addEventListener('change', function () {
                    layout.grid.showBorders = bordersInput.checked;
                });
            }
        }

        // --- save ---------------------------------------------------------
        function saveLayout() {
            layout.widgets = widgets;
            setStatus('Saving…', '');
            fetch('/save_layout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify(layout)
            }).then(function (response) {
                return response.json().then(function (body) {
                    return { status: response.status, body: body };
                }).catch(function () {
                    return { status: response.status, body: null };
                });
            }).then(function (result) {
                if (result.status === 200 && result.body && result.body.ok) {
                    layout = result.body.layout;
                    layout.grid = layout.grid || {};
                    widgets = layout.widgets;
                    clampWidgets();
                    renderBlocks();
                    renderInspector();
                    setStatus('Layout saved. A running display updates automatically.', 'ok');
                } else {
                    var errors = (result.body && result.body.errors) || ['Saving the layout failed.'];
                    setStatus(errors.join(' '), 'error');
                }
            }).catch(function () {
                setStatus('Network error while saving the layout.', 'error');
            });
        }

        // --- init ---------------------------------------------------------
        board.style.backgroundImage =
            'linear-gradient(to right, rgba(255,255,255,0.10) 1px, transparent 1px),' +
            'linear-gradient(to bottom, rgba(255,255,255,0.10) 1px, transparent 1px)';

        buildPalette();
        bindGridSettings();
        applyBoardSize();
        clampWidgets();
        renderBlocks();
        renderInspector();

        var saveBtn = document.getElementById('save-layout-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', saveLayout);
        }

        var resizeTimer = null;
        window.addEventListener('resize', function () {
            window.clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(function () {
                applyBoardSize();
                renderBlocks();
            }, 120);
        });
    });
})();
