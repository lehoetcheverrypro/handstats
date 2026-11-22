import streamlit.components.v1 as components

def afficher_tableau_tactique():
    html_code = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <style>
            * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { margin: 0; padding: 8px; background-color: #0e1117; color: #f8fafc; display: flex; flex-direction: column; align-items: center; }
            .toolbar-container {
                display: flex; flex-direction: column; gap: 6px; width: 100%; max-width: 740px;
                background: #121620; padding: 10px; border-radius: 12px; border: 1px solid #273043;
                box-shadow: 0 4px 12px rgba(0,0,0,0.35); margin-bottom: 10px;
            }
            .toolbar-row {
                display: flex; flex-wrap: wrap; gap: 6px; align-items: center; justify-content: center;
            }
            .toolbar-label {
                font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-right: 4px;
            }
            button {
                padding: 5px 10px; border: 1px solid #273043; border-radius: 7px;
                background: #1a2030; color: #f8fafc; font-weight: 600; font-size: 11px;
                cursor: pointer; transition: all 0.15s;
            }
            button:hover { background: #273043; border-color: #38bdf8; }
            button.active { background: #0284c7; color: #ffffff; border-color: #38bdf8; }
            button.def-btn { background: rgba(220, 38, 38, 0.18); color: #fca5a5; border-color: rgba(248, 113, 113, 0.45); }
            button.def-btn:hover { background: rgba(220, 38, 38, 0.32); color: #ffffff; }
            button.atk-btn { background: rgba(37, 99, 235, 0.22); color: #93c5fd; border-color: rgba(96, 165, 250, 0.45); }
            button.atk-btn:hover { background: rgba(37, 99, 235, 0.36); color: #ffffff; }
            button.danger { background: rgba(239, 68, 68, 0.16); color: #fca5a5; border-color: rgba(248, 113, 113, 0.4); }
            button.danger:hover { background: rgba(239, 68, 68, 0.3); color: #ffffff; }
            .color-dot {
                width: 20px; height: 20px; border-radius: 50%; border: 2px solid #1e293b;
                box-shadow: 0 0 0 1px #64748b; cursor: pointer; display: inline-block; vertical-align: middle;
                transition: transform 0.15s;
            }
            .color-dot.selected { box-shadow: 0 0 0 2px #38bdf8; transform: scale(1.18); }
            canvas {
                background-color: #f8fafc; border: 2px solid #273043; border-radius: 10px;
                touch-action: none; cursor: grab; max-width: 100%; height: auto;
                box-shadow: 0 6px 18px rgba(0,0,0,0.45);
            }
            canvas.drawing-mode { cursor: crosshair; }
        </style>
    </head>
    <body>
        <div class="toolbar-container">
            <!-- Ligne 1 : Défenses Adverses -->
            <div class="toolbar-row">
                <span class="toolbar-label">🛡️ Défense :</span>
                <button class="def-btn" onclick="setDefense('6-0')">6-0</button>
                <button class="def-btn" onclick="setDefense('5-1')">5-1</button>
                <button class="def-btn" onclick="setDefense('4-2')">4-2</button>
                <button class="def-btn" onclick="setDefense('3-2-1')">3-2-1</button>
                <button class="def-btn" onclick="setDefense('3-3')">3-3 (Étagé)</button>
            </div>
            <!-- Ligne 2 : Attaques Équipe -->
            <div class="toolbar-row">
                <span class="toolbar-label">⚔️ Attaque :</span>
                <button class="atk-btn" onclick="setAttack('standard')">Attaque Classique (6 vs 6)</button>
                <button class="atk-btn" onclick="setAttack('attaque-7')">Attaque à 7 (Sans Gardien)</button>
            </div>
            <!-- Ligne 3 : Outils de dessin -->
            <div class="toolbar-row" style="border-top: 1px solid #273043; padding-top: 6px;">
                <button id="btnMove" class="active" onclick="setMode('move')">✋ Bouger pions</button>
                <button id="btnDraw" onclick="setMode('draw')">✏️ Tracer en Flèches</button>
                <span style="border-left: 1px solid #273043; margin: 0 4px; height: 16px;"></span>
                <div style="display:flex; align-items:center; gap:5px;">
                    <span class="color-dot selected" style="background:#0f172a;" onclick="setColor('#0f172a', this)"></span>
                    <span class="color-dot" style="background:#dc2626;" onclick="setColor('#dc2626', this)"></span>
                    <span class="color-dot" style="background:#16a34a;" onclick="setColor('#16a34a', this)"></span>
                    <span class="color-dot" style="background:#2563eb;" onclick="setColor('#2563eb', this)"></span>
                </div>
                <button class="danger" onclick="clearDrawings()">🧹 Effacer flèches</button>
            </div>
        </div>

        <canvas id="courtCanvas" width="740" height="440"></canvas>

        <script>
            const canvas = document.getElementById('courtCanvas');
            const ctx = canvas.getContext('2d');

            let mode = 'move';
            let drawColor = '#0f172a';
            let isDrawing = false;
            let currentStroke = null;
            let strokes = [];
            let draggedToken = null;
            let tokens = [];

            const LEFT_TOUCH = 70;
            const RIGHT_TOUCH = 670;
            const TOP_LINE = 30;
            const BOTTOM_LINE = 410;
            const GOAL_X = 370;

            function initTokens() {
                tokens = [
                    // Attaque (Bleu) - Ailières calées dans les coins de corner
                    { id: 'AG', label: 'AG', x: 95,  y: 75,  color: '#2563eb', text: '#fff', radius: 14, active: true },  
                    { id: 'ARG', label: 'ARG', x: 230, y: 260, color: '#2563eb', text: '#fff', radius: 14, active: true }, 
                    { id: 'DC', label: 'DC', x: 370, y: 290, color: '#2563eb', text: '#fff', radius: 14, active: true },  
                    { id: 'ARD', label: 'ARD', x: 510, y: 260, color: '#2563eb', text: '#fff', radius: 14, active: true }, 
                    { id: 'AD', label: 'AD', x: 645, y: 75,  color: '#2563eb', text: '#fff', radius: 14, active: true },  
                    { id: 'PIV', label: 'PIV', x: 350, y: 165, color: '#2563eb', text: '#fff', radius: 14, active: true }, 
                    { id: 'EXTRA', label: '7', x: 370, y: 350, color: '#2563eb', text: '#fff', radius: 14, active: false }, 

                    // Défense (Rouge) - 6-0 de base
                    { id: 'D1', label: '1', x: 170, y: 120, color: '#dc2626', text: '#fff', radius: 13, active: true },
                    { id: 'D2', label: '2', x: 260, y: 155, color: '#dc2626', text: '#fff', radius: 13, active: true },
                    { id: 'D3', label: '3', x: 325, y: 175, color: '#dc2626', text: '#fff', radius: 13, active: true },
                    { id: 'D4', label: '4', x: 415, y: 175, color: '#dc2626', text: '#fff', radius: 13, active: true },
                    { id: 'D5', label: '5', x: 480, y: 155, color: '#dc2626', text: '#fff', radius: 13, active: true },
                    { id: 'D6', label: '6', x: 570, y: 120, color: '#dc2626', text: '#fff', radius: 13, active: true },

                    // Ballon
                    { id: 'BALL', label: '⚽', x: 370, y: 220, color: '#facc15', text: '#0f172a', radius: 10, active: true }
                ];
            }

            function setDefense(type) {
                if (type === '6-0') {
                    setTokenState('D1', true, 170, 120);  setTokenState('D2', true, 260, 155);
                    setTokenState('D3', true, 325, 175); setTokenState('D4', true, 415, 175);
                    setTokenState('D5', true, 480, 155); setTokenState('D6', true, 570, 120);
                } else if (type === '5-1') {
                    setTokenState('D1', true, 175, 120);  setTokenState('D2', true, 265, 155);
                    setTokenState('D3', true, 370, 235); 
                    setTokenState('D4', true, 370, 175); 
                    setTokenState('D5', true, 475, 155); setTokenState('D6', true, 565, 120);
                } else if (type === '4-2') {
                    setTokenState('D1', true, 185, 115);  
                    setTokenState('D2', true, 275, 205); 
                    setTokenState('D3', true, 465, 205); 
                    setTokenState('D4', true, 555, 115);  
                    setTokenState('D5', true, 325, 175); 
                    setTokenState('D6', true, 415, 175); 
                } else if (type === '3-2-1') {
                    setTokenState('D1', true, 370, 255); 
                    setTokenState('D2', true, 280, 195); setTokenState('D3', true, 460, 195); 
                    setTokenState('D4', true, 170, 120); setTokenState('D5', true, 370, 175); setTokenState('D6', true, 570, 120); 
                } else if (type === '3-3') {
                    setTokenState('D1', true, 230, 210); 
                    setTokenState('D2', true, 370, 225); 
                    setTokenState('D3', true, 510, 210);
                    setTokenState('D4', true, 190, 130); 
                    setTokenState('D5', true, 370, 155);
                    setTokenState('D6', true, 550, 130);
                }
                draw();
            }

            function setAttack(type) {
                if (type === 'standard') {
                    setTokenState('AG', true, 95, 75);
                    setTokenState('ARG', true, 230, 260);
                    setTokenState('DC', true, 370, 290);  
                    setTokenState('ARD', true, 510, 260);
                    setTokenState('AD', true, 645, 75);
                    setTokenState('PIV', true, 350, 165);
                    setTokenState('EXTRA', false, 0, 0);
                    setTokenState('BALL', true, 370, 220);
                } else if (type === 'attaque-7') {
                    setTokenState('AG', true, 95, 75); 
                    setTokenState('ARG', true, 220, 270);
                    setTokenState('DC', true, 370, 305);  
                    setTokenState('ARD', true, 520, 270);
                    setTokenState('AD', true, 645, 75); 
                    setTokenState('PIV', true, 330, 165); 
                    setTokenState('EXTRA', true, 410, 165); 
                    setTokenState('BALL', true, 370, 230);
                }
                draw();
            }

            function setTokenState(id, active, x, y) {
                const t = tokens.find(item => item.id === id);
                if (t) {
                    t.active = active;
                    if (active) { t.x = x; t.y = y; }
                }
            }

            function setMode(newMode) {
                mode = newMode;
                document.getElementById('btnMove').classList.toggle('active', mode === 'move');
                document.getElementById('btnDraw').classList.toggle('active', mode === 'draw');
                canvas.classList.toggle('drawing-mode', mode === 'draw');
            }

            function setColor(color, el) {
                drawColor = color;
                document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('selected'));
                el.classList.add('selected');
                setMode('draw');
            }

            function clearDrawings() {
                strokes = [];
                draw();
            }

            function drawCourt() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '#f8fafc';
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                ctx.lineWidth = 3;
                ctx.strokeStyle = '#0f172a';
                ctx.strokeRect(LEFT_TOUCH, TOP_LINE, RIGHT_TOUCH - LEFT_TOUCH, BOTTOM_LINE - TOP_LINE);

                ctx.fillStyle = '#0f172a';
                ctx.fillRect(GOAL_X - 35, TOP_LINE - 10, 70, 10);
                ctx.strokeStyle = '#ef4444';
                ctx.lineWidth = 2.5;
                ctx.strokeRect(GOAL_X - 35, TOP_LINE - 10, 70, 10);

                ctx.beginPath();
                ctx.fillStyle = '#e2e8f0';
                ctx.arc(GOAL_X, TOP_LINE, 135, 0, Math.PI, false);
                ctx.fill();
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = '#0f172a';
                ctx.stroke();

                ctx.save();
                ctx.beginPath();
                ctx.setLineDash([8, 6]);
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = '#0f172a';
                ctx.arc(GOAL_X, TOP_LINE, 225, 0, Math.PI, false);
                ctx.stroke();
                ctx.restore();

                ctx.beginPath();
                ctx.moveTo(GOAL_X - 15, TOP_LINE + 160);
                ctx.lineTo(GOAL_X + 15, TOP_LINE + 160);
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = '#0f172a';
                ctx.stroke();

                ctx.beginPath();
                ctx.moveTo(GOAL_X - 8, TOP_LINE + 85);
                ctx.lineTo(GOAL_X + 8, TOP_LINE + 85);
                ctx.lineWidth = 2;
                ctx.strokeStyle = '#0f172a';
                ctx.stroke();
            }

            function drawArrowhead(fromX, fromY, toX, toY, color) {
                const headlen = 12;
                const dx = toX - fromX;
                const dy = toY - fromY;
                if (Math.hypot(dx, dy) < 5) return;
                const angle = Math.atan2(dy, dx);
                ctx.beginPath();
                ctx.moveTo(toX, toY);
                ctx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
                ctx.moveTo(toX, toY);
                ctx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.stroke();
            }

            function drawStrokes() {
                strokes.forEach(stroke => {
                    if (stroke.points.length < 2) return;
                    const pStart = stroke.points[0];
                    const pEnd = stroke.points[stroke.points.length - 1];

                    ctx.beginPath();
                    ctx.strokeStyle = stroke.color;
                    ctx.lineWidth = 3;
                    ctx.lineCap = 'round';
                    ctx.moveTo(pStart.x, pStart.y);
                    ctx.lineTo(pEnd.x, pEnd.y);
                    ctx.stroke();

                    drawArrowhead(pStart.x, pStart.y, pEnd.x, pEnd.y, stroke.color);
                });
            }

            function drawTokens() {
                tokens.forEach(t => {
                    if (!t.active) return;
                    ctx.beginPath();
                    ctx.arc(t.x, t.y, t.radius, 0, Math.PI * 2);
                    ctx.fillStyle = t.color;
                    ctx.fill();
                    ctx.lineWidth = 2.5;
                    ctx.strokeStyle = '#ffffff';
                    ctx.stroke();

                    ctx.fillStyle = t.text;
                    ctx.font = 'bold 11px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(t.label, t.x, t.y);
                });
            }

            function draw() {
                drawCourt();
                drawStrokes();
                drawTokens();
            }

            function getPos(e) {
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                return {
                    x: (clientX - rect.left) * scaleX,
                    y: (clientY - rect.top) * scaleY
                };
            }

            function onDown(e) {
                e.preventDefault();
                const pos = getPos(e);

                if (mode === 'move') {
                    for (let i = tokens.length - 1; i >= 0; i--) {
                        const t = tokens[i];
                        if (t.active && Math.hypot(pos.x - t.x, pos.y - t.y) <= t.radius + 6) {
                            draggedToken = t;
                            break;
                        }
                    }
                } else if (mode === 'draw') {
                    isDrawing = true;
                    currentStroke = { color: drawColor, points: [pos, pos] };
                    strokes.push(currentStroke);
                }
            }

            function onMove(e) {
                if (!draggedToken && !isDrawing) return;
                e.preventDefault();
                const pos = getPos(e);

                if (mode === 'move' && draggedToken) {
                    draggedToken.x = Math.max(LEFT_TOUCH + 10, Math.min(RIGHT_TOUCH - 10, pos.x));
                    draggedToken.y = Math.max(TOP_LINE + 10, Math.min(BOTTOM_LINE - 10, pos.y));
                    draw();
                } else if (mode === 'draw' && isDrawing && currentStroke) {
                    currentStroke.points[1] = pos;
                    draw();
                }
            }

            function onUp() {
                draggedToken = null;
                isDrawing = false;
                currentStroke = null;
            }

            canvas.addEventListener('mousedown', onDown);
            canvas.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
            canvas.addEventListener('touchstart', onDown, { passive: false });
            canvas.addEventListener('touchmove', onMove, { passive: false });
            window.addEventListener('touchend', onUp);

            initTokens();
            draw();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=520)
