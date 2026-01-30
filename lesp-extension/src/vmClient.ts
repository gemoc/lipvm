import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';

export interface EnvironmentSnapshot {
    ip: number;
    heap: any;
    globals: any;
    stack: any[];
    currentLine?: number;
}

export interface VMState {
    heap: any;
    position?: number;
    history?: EnvironmentSnapshot[];
    historyLength?: number;
}

export class VMClient {
    private process: ChildProcess | null = null;
    private rpcOutputPanel: vscode.OutputChannel;
    private mainOutputPanel: vscode.OutputChannel | null = null;
    private responseHandlers: Map<number, (response: any) => void> = new Map();
    private requestId = 0;

    constructor(mainOutputPanel?: vscode.OutputChannel) {
        this.rpcOutputPanel = vscode.window.createOutputChannel('LESP RPC');
        this.mainOutputPanel = mainOutputPanel || null;
    }

    private log(message: string, toMain: boolean = true) {
        this.rpcOutputPanel.appendLine(message);
        if (toMain && this.mainOutputPanel) {
            this.mainOutputPanel.appendLine(message);
        }
    }

    async start(lespBinary: string, workspaceRoot: string): Promise<boolean> {
        if (this.process) {
            this.stop();
        }

        this.rpcOutputPanel.clear();
        this.log('='.repeat(60));
        this.log('Starting LESP Server');
        this.log(`LESP Binary: ${lespBinary}`);
        this.log(`Working Directory: ${workspaceRoot}`);
        this.log('='.repeat(60));

        return new Promise((resolve) => {
            // Run lesp binary without arguments (it runs in server mode by default)
            const args: string[] = [];

            this.process = spawn(lespBinary, args, {
                cwd: workspaceRoot,
                env: { ...process.env, PYTHONUNBUFFERED: '1' }
            });

            let buffer = '';

            this.process.stdout?.on('data', (data) => {
                buffer += data.toString();
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.trim()) {
                        this.log(`[RECV] ${line}`);
                        try {
                            const response = JSON.parse(line);

                            const handler = this.responseHandlers.get(response.id || 0);
                            if (handler) {
                                this.log(`[HANDLER] Processing response for request ID ${response.id}`);
                                handler(response);
                                this.responseHandlers.delete(response.id || 0);
                            } else {
                                this.log(`[WARN] No handler found for response ID ${response.id}`);
                            }
                        } catch (e) {
                            this.log(`[ERROR] Failed to parse JSON: ${e}`);
                            this.log(`[ERROR] Raw line: ${line}`);
                        }
                    }
                }
            });

            this.process.stderr?.on('data', (data) => {
                const lines = data.toString().split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        this.log(`[STDERR] ${line}`);
                    }
                }
            });

            this.process.on('error', (error) => {
                this.log(`[PROCESS ERROR] ${error.message}`);
                resolve(false);
            });

            this.process.on('exit', (code) => {
                this.log(`[PROCESS EXIT] Code: ${code}`);
                this.process = null;
            });

            // Give it a moment to start
            setTimeout(() => {
                const started = this.process !== null;
                this.log(`[STATUS] Process started: ${started}`);
                resolve(started);
            }, 100);
        });
    }

    stop() {
        if (this.process) {
            this.log('[STOP] Killing VM process');
            this.process.kill();
            this.process = null;
        }
    }

    private sendRequest(method: string, params: any = {}): Promise<any> {
        return new Promise((resolve, reject) => {
            if (!this.process) {
                reject(new Error('VM process not started'));
                return;
            }

            const id = this.requestId++;
            const request = { id, method, params };

            this.responseHandlers.set(id, (response) => {
                // Check if the response indicates an error
                if (response.success === false) {
                    this.log(`[ERROR] Request failed: ${response.error}`);
                    reject(new Error(response.error || 'Unknown error'));
                } else {
                    resolve(response);
                }
            });

            const requestStr = JSON.stringify(request) + '\n';
            this.log(`[SEND] ${requestStr.trim()}`);
            this.process.stdin?.write(requestStr);

            // Timeout after 5 seconds
            setTimeout(() => {
                if (this.responseHandlers.has(id)) {
                    this.responseHandlers.delete(id);
                    this.log(`[TIMEOUT] Request ID ${id} timed out`);
                    reject(new Error('Request timeout'));
                }
            }, 5000);
        });
    }

    async setLanguageModule(module: string): Promise<any> {
        this.log(`[SET_LANGUAGE_MODULE] Module: ${module}`);
        return this.sendRequest('setLanguageModule', { module });
    }

    async compile(code: string): Promise<any> {
        this.log(`[COMPILE] Code length: ${code.length} bytes`);
        return this.sendRequest('compile', { code });
    }

    async start_execution(): Promise<VMState> {
        this.log('[START] Starting execution');
        return this.sendRequest('start');
    }

    async stepForward(): Promise<VMState> {
        this.log('[STEP] Step forward');
        return this.sendRequest('stepForward');
    }

    async stepBackward(): Promise<VMState> {
        this.log('[STEP] Step backward');
        return this.sendRequest('stepBackward');
    }

    async getState(): Promise<VMState> {
        this.log('[STATE] Getting current state');
        return this.sendRequest('getState');
    }

    dispose() {
        this.stop();
        this.rpcOutputPanel.dispose();
    }
}
