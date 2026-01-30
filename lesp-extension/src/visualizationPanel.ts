import * as vscode from 'vscode';
import { VMState, EnvironmentSnapshot } from './vmClient';

export type ViewMode = 'trace' | 'canvas' | 'both';

export class VisualizationPanel {
    private panel: vscode.WebviewPanel | undefined;
    private viewMode: ViewMode = 'both';
    private history: VMState[] = [];

    constructor(private context: vscode.ExtensionContext) { }

    public setViewMode(mode: ViewMode) {
        this.viewMode = mode;
        if (this.panel) {
            this.updateView();
        }
    }

    public getViewMode(): ViewMode {
        return this.viewMode;
    }

    public show() {
        if (this.panel) {
            this.panel.reveal();
        } else {
            this.panel = vscode.window.createWebviewPanel(
                'lespVisualization',
                'LESP Visualization',
                vscode.ViewColumn.Two,
                {
                    enableScripts: true,
                    retainContextWhenHidden: true
                }
            );

            this.panel.onDidDispose(() => {
                this.panel = undefined;
            });

            this.updateView();
        }
    }

    public updateState(state: VMState) {
        // Add to history
        this.history.push(state);

        // Keep last 100 states
        if (this.history.length > 100) {
            this.history.shift();
        }

        if (this.panel) {
            this.panel.webview.postMessage({
                type: 'updateState',
                state: state,
                history: this.history
            });
        }
    }

    public clear() {
        this.history = [];
        if (this.panel) {
            this.panel.webview.postMessage({
                type: 'clear'
            });
        }
    }

    private updateView() {
        if (!this.panel) return;

        this.panel.webview.html = this.getHtmlContent();

        // Send current state
        if (this.history.length > 0) {
            this.panel.webview.postMessage({
                type: 'updateState',
                state: this.history[this.history.length - 1],
                history: this.history
            });
        }
    }

    private getHtmlContent(): string {
        const showTrace = this.viewMode === 'trace' || this.viewMode === 'both';
        const showCanvas = this.viewMode === 'canvas' || this.viewMode === 'both';

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LESP Visualization</title>
    <style>
        body {
            margin: 0;
            padding: 10px;
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
        }
        .container {
            display: flex;
            flex-direction: ${this.viewMode === 'both' ? 'row' : 'column'};
            gap: 10px;
            height: calc(100vh - 20px);
        }
        .view {
            flex: 1;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .view-header {
            background-color: var(--vscode-editor-background);
            padding: 8px 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
            font-weight: bold;
            font-size: 12px;
            text-transform: uppercase;
        }
        .view-content {
            flex: 1;
            overflow: auto;
            padding: 10px;
        }
        #canvas {
            background-color: white;
            border: 1px solid #ccc;
            display: block;
            margin: 0 auto;
        }
        .trace-item {
            padding: 6px 10px;
            margin: 4px 0;
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            border-left: 3px solid var(--vscode-textLink-foreground);
            border-radius: 2px;
            font-size: 12px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .trace-item:hover {
            background-color: var(--vscode-list-hoverBackground);
        }
        .trace-item.current {
            background-color: var(--vscode-editor-selectionBackground);
            border-left-color: var(--vscode-textLink-activeForeground);
            font-weight: bold;
        }
        .trace-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .trace-position {
            color: var(--vscode-descriptionForeground);
            font-size: 11px;
        }
        .trace-toggle {
            color: var(--vscode-descriptionForeground);
            font-size: 10px;
            user-select: none;
        }
        .trace-details {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid var(--vscode-panel-border);
            display: none;
        }
        .trace-details.expanded {
            display: block;
        }
        .trace-section {
            margin-bottom: 8px;
        }
        .trace-section-title {
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
            font-size: 11px;
            margin-bottom: 4px;
        }
        .trace-heap {
            font-family: var(--vscode-editor-font-family);
            font-size: 11px;
            color: var(--vscode-editor-foreground);
            white-space: pre-wrap;
            word-break: break-all;
            background-color: var(--vscode-textCodeBlock-background);
            padding: 6px;
            border-radius: 3px;
            max-height: 200px;
            overflow-y: auto;
        }
        .stats {
            padding: 10px;
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 12px;
        }
        .stats-item {
            display: inline-block;
            margin-right: 20px;
        }
        .stats-label {
            color: var(--vscode-descriptionForeground);
        }
        .stats-value {
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
    </style>
</head>
<body>
    <div class="container">
        ${showTrace ? `
        <div class="view" id="trace-view">
            <div class="view-header">📜 Execution Trace</div>
            <div class="view-content">
                <div class="stats" id="stats">
                    <span class="stats-item">
                        <span class="stats-label">Position:</span>
                        <span class="stats-value" id="position">-</span>
                    </span>
                    <span class="stats-item">
                        <span class="stats-label">History:</span>
                        <span class="stats-value" id="history-length">0</span>
                    </span>
                </div>
                <div id="trace-content"></div>
            </div>
        </div>
        ` : ''}
        
        ${showCanvas ? `
        <div class="view" id="canvas-view">
            <div class="view-header">🎨 Canvas Output</div>
            <div class="view-content">
                <canvas id="canvas" width="600" height="600"></canvas>
            </div>
        </div>
        ` : ''}
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentState = null;
        let history = [];

        window.addEventListener('message', event => {
            const message = event.data;
            
            if (message.type === 'updateState') {
                currentState = message.state;
                history = message.history || [];
                updateVisualization();
            } else if (message.type === 'clear') {
                currentState = null;
                history = [];
                updateVisualization();
            }
        });

        function updateVisualization() {
            ${showTrace ? 'updateTrace();' : ''}
            ${showCanvas ? 'updateCanvas();' : ''}
        }

        ${showTrace ? `
        function updateTrace() {
            const traceContent = document.getElementById('trace-content');
            const positionEl = document.getElementById('position');
            const historyLengthEl = document.getElementById('history-length');
            
            if (!currentState) {
                traceContent.innerHTML = '<div style="color: var(--vscode-descriptionForeground); text-align: center; padding: 20px;">No execution data</div>';
                positionEl.textContent = '-';
                historyLengthEl.textContent = '0';
                return;
            }

            positionEl.textContent = currentState.position !== undefined ? currentState.position : '-';
            
            // Use history array from state if available, otherwise fall back to accumulated history
            const historyToDisplay = currentState.history || history;
            historyLengthEl.textContent = historyToDisplay.length;

            let html = '';
            
            // Display snapshots from history array
            if (currentState.history && currentState.history.length > 0) {
                // Show most recent snapshots first (reverse order)
                for (let i = currentState.history.length - 1; i >= Math.max(0, currentState.history.length - 20); i--) {
                    const snapshot = currentState.history[i];
                    const isCurrent = i === currentState.history.length - 1;
                    
                    html += \`
                        <div class="trace-item \${isCurrent ? 'current' : ''}" onclick="toggleSnapshot(\${i})">
                            <div class="trace-header">
                                <div class="trace-position">
                                    Snapshot \${i + 1} - IP: \${snapshot.ip !== undefined ? snapshot.ip : 'N/A'}
                                    \${snapshot.currentLine !== undefined ? ' | Line: ' + snapshot.currentLine : ''}
                                    \${isCurrent ? ' (Current)' : ''}
                                </div>
                                <div class="trace-toggle" id="toggle-\${i}">▼ Expand</div>
                            </div>
                            <div class="trace-details" id="details-\${i}">
                                <div class="trace-section">
                                    <div class="trace-section-title">Heap:</div>
                                    <div class="trace-heap">\${escapeHtml(JSON.stringify(snapshot.heap, null, 2))}</div>
                                </div>
                                <div class="trace-section">
                                    <div class="trace-section-title">Globals:</div>
                                    <div class="trace-heap">\${escapeHtml(JSON.stringify(snapshot.globals, null, 2))}</div>
                                </div>
                                <div class="trace-section">
                                    <div class="trace-section-title">Stack:</div>
                                    <div class="trace-heap">\${escapeHtml(JSON.stringify(snapshot.stack, null, 2))}</div>
                                </div>
                            </div>
                        </div>
                    \`;
                }
            } else {
                // Fallback to old format (accumulated history)
                for (let i = history.length - 1; i >= Math.max(0, history.length - 20); i--) {
                    const state = history[i];
                    const isCurrent = i === history.length - 1;
                    const heapStr = JSON.stringify(state.heap, null, 2);
                    
                    html += \`
                        <div class="trace-item \${isCurrent ? 'current' : ''}" onclick="toggleSnapshot(\${i})">
                            <div class="trace-header">
                                <div class="trace-position">
                                    Step \${i + 1}\${state.position !== undefined ? ' (Position: ' + state.position + ')' : ''}
                                    \${isCurrent ? ' (Current)' : ''}
                                </div>
                                <div class="trace-toggle" id="toggle-\${i}">▼ Expand</div>
                            </div>
                            <div class="trace-details" id="details-\${i}">
                                <div class="trace-section">
                                    <div class="trace-section-title">Heap:</div>
                                    <div class="trace-heap">\${escapeHtml(heapStr)}</div>
                                </div>
                            </div>
                        </div>
                    \`;
                }
            }
            
            traceContent.innerHTML = html || '<div style="color: var(--vscode-descriptionForeground);">No trace data</div>';
        }

        function toggleSnapshot(index) {
            const details = document.getElementById('details-' + index);
            const toggle = document.getElementById('toggle-' + index);
            
            if (details && toggle) {
                if (details.classList.contains('expanded')) {
                    details.classList.remove('expanded');
                    toggle.textContent = '▼ Expand';
                } else {
                    details.classList.add('expanded');
                    toggle.textContent = '▲ Collapse';
                }
            }
        }
        ` : ''}

        ${showCanvas ? `
        function updateCanvas() {
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            
            // Clear canvas
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            if (!currentState || !currentState.heap) {
                ctx.fillStyle = '#999';
                ctx.font = '14px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('No canvas data', canvas.width / 2, canvas.height / 2);
                return;
            }

            // Draw lines from heap
            const heap = currentState.heap;
            
            if (heap.lines && Array.isArray(heap.lines)) {
                heap.lines.forEach(line => {
                    if (line.length >= 3) {
                        const [start, end, color] = line;
                        
                        ctx.strokeStyle = color || '#000000';
                        ctx.lineWidth = 4;
                        ctx.lineCap = 'round';
                        
                        ctx.beginPath();
                        ctx.moveTo(start[0], start[1]);
                        ctx.lineTo(end[0], end[1]);
                        ctx.stroke();
                    }
                });
            }

            // Draw other heap properties as text
            ctx.fillStyle = '#333';
            ctx.font = '12px monospace';
            ctx.textAlign = 'left';
            let y = 20;
            
            for (const [key, value] of Object.entries(heap)) {
                if (key !== 'lines') {
                    ctx.fillText(\`\${key}: \${JSON.stringify(value)}\`, 10, y);
                    y += 16;
                }
            }
        }
        ` : ''}

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Initial render
        updateVisualization();
    </script>
</body>
</html>`;
    }

    public dispose() {
        if (this.panel) {
            this.panel.dispose();
        }
    }
}
