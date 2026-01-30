import * as vscode from 'vscode';
import { VMClient, VMState } from './vmClient';
import { VisualizationPanel } from './visualizationPanel';
import * as path from 'path';

interface DebugConfig {
    language: string;
    fileExtension: string;
    file: string;
    languageModule: string;
    lespBinary: string;
}

interface ExtensionSettings {
    [fileExtension: string]: {
        language: string;
        languageModule: string;
        lespBinary: string;
    };
}

let currentConfig: DebugConfig | undefined;
let vmClient: VMClient | undefined;
let outputPanel: vscode.OutputChannel;
let visualizationPanel: VisualizationPanel;
let treeDataProvider: ConfigTreeDataProvider;
let isVMStarted = false;
let currentLineDecoration: vscode.TextEditorDecorationType | undefined;
let compilationError: string | undefined;

class ConfigTreeDataProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<vscode.TreeItem | undefined | null | void> = new vscode.EventEmitter<vscode.TreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(): vscode.TreeItem[] {
        const items: vscode.TreeItem[] = [];

        if (currentConfig) {
            // Show current file info
            const fileName = path.basename(currentConfig.file);
            const fileDir = path.dirname(currentConfig.file);

            const fileInfo = new vscode.TreeItem(`📄 ${fileName}`);
            fileInfo.description = fileDir;
            fileInfo.tooltip = `File: ${currentConfig.file}\nLanguage: ${currentConfig.language}\nModule: ${currentConfig.languageModule}\nBinary: ${currentConfig.lespBinary}`;
            fileInfo.iconPath = new vscode.ThemeIcon('file-code');
            items.push(fileInfo);

            // Show language info
            const langInfo = new vscode.TreeItem(`${currentConfig.language} (${currentConfig.fileExtension})`);
            langInfo.description = currentConfig.languageModule;
            langInfo.iconPath = new vscode.ThemeIcon('symbol-namespace');
            items.push(langInfo);

            // Add separator
            const separator = new vscode.TreeItem('');
            separator.iconPath = new vscode.ThemeIcon('dash');
            items.push(separator);
        }

        // Show compilation error if present
        if (compilationError) {
            const errorItem = new vscode.TreeItem('⚠️ Compilation Error');
            errorItem.description = compilationError;
            errorItem.tooltip = `Compilation failed: ${compilationError}`;
            errorItem.iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
            errorItem.contextValue = 'error';
            items.push(errorItem);

            const separator = new vscode.TreeItem('');
            separator.iconPath = new vscode.ThemeIcon('dash');
            items.push(separator);
        }

        // Add control buttons
        items.push(createButton('Configure', 'lesp.configure', 'gear'));

        // Only show Run, Step Forward, and Step Backward if there's no compilation error
        if (!compilationError) {
            items.push(createButton('Run', 'lesp.run', 'play'));
            items.push(createButton('Step Forward', 'lesp.stepForward', 'debug-step-over'));
            items.push(createButton('Step Backward', 'lesp.stepBackward', 'debug-step-back'));
        }

        // Add view mode buttons
        const separator2 = new vscode.TreeItem('');
        separator2.iconPath = new vscode.ThemeIcon('dash');
        items.push(separator2);

        const viewModeLabel = new vscode.TreeItem('View Mode');
        viewModeLabel.iconPath = new vscode.ThemeIcon('eye');
        items.push(viewModeLabel);

        items.push(createButton('Trace View', 'lesp.viewTrace', 'list-tree'));
        items.push(createButton('Canvas View', 'lesp.viewCanvas', 'symbol-color'));
        items.push(createButton('Both Views', 'lesp.viewBoth', 'split-horizontal'));

        return items;
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('LESP Runner extension activated');

    outputPanel = vscode.window.createOutputChannel('LESP Runner');
    vmClient = new VMClient(outputPanel);
    visualizationPanel = new VisualizationPanel(context);
    treeDataProvider = new ConfigTreeDataProvider();

    // Create decoration type for current line highlighting
    currentLineDecoration = vscode.window.createTextEditorDecorationType({
        backgroundColor: new vscode.ThemeColor('editor.lineHighlightBackground'),
        border: '1px solid',
        borderColor: new vscode.ThemeColor('editorLineNumber.activeForeground'),
        isWholeLine: false,
        overviewRulerColor: new vscode.ThemeColor('editorOverviewRuler.errorForeground'),
        overviewRulerLane: vscode.OverviewRulerLane.Full
    });

    // Load saved configuration for current file if available
    const editor = vscode.window.activeTextEditor;
    if (editor) {
        loadConfigForFile(editor.document.uri.fsPath);
    }

    // Watch for active editor changes to load config automatically
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(async (editor) => {
            if (editor) {
                const previousFile = currentConfig?.file;
                loadConfigForFile(editor.document.uri.fsPath);

                // Auto-compile if VM is started and file changed
                if (currentConfig && isVMStarted && currentConfig.file !== previousFile) {
                    outputPanel.appendLine(`\n[AUTO-COMPILE] Switched to file: ${currentConfig.file}`);
                    try {
                        const code = editor.document.getText();

                        // Compile the code
                        await vmClient!.compile(code);
                        outputPanel.appendLine('[AUTO-COMPILE] Compilation successful');

                        // Clear compilation error on successful compilation
                        compilationError = undefined;
                        treeDataProvider.refresh();

                        // Start execution
                        outputPanel.appendLine('[AUTO-COMPILE] Starting execution...');
                        const state = await vmClient!.start_execution();
                        displayState(state);

                        outputPanel.appendLine('[AUTO-COMPILE] Execution started successfully');
                    } catch (error: any) {
                        // Set compilation error
                        compilationError = error.message;
                        treeDataProvider.refresh();

                        outputPanel.appendLine(`[AUTO-COMPILE] Compilation Error: ${error.message}`);
                        vscode.window.showErrorMessage(`Compilation Error: ${error.message}`);
                    }
                }
            }
        })
    );

    // Watch for file changes and auto-run
    const fileWatcher = vscode.workspace.onDidSaveTextDocument(async (document) => {
        if (!currentConfig || !isVMStarted) return;

        // Only run if the saved file is the configured file
        if (document.uri.fsPath === currentConfig.file) {
            outputPanel.appendLine(`\n[AUTO-RUN] File saved: ${document.uri.fsPath}`);
            try {
                const code = document.getText();

                // Compile the code
                await vmClient!.compile(code);
                outputPanel.appendLine('[AUTO-RUN] Compilation successful');

                // Clear compilation error on successful compilation
                compilationError = undefined;
                treeDataProvider.refresh();

                // Start execution
                outputPanel.appendLine('[AUTO-RUN] Starting execution...');
                const state = await vmClient!.start_execution();
                displayState(state);

                outputPanel.appendLine('[AUTO-RUN] Execution started successfully');
            } catch (error: any) {
                // Set compilation error
                compilationError = error.message;
                treeDataProvider.refresh();

                outputPanel.appendLine(`[AUTO-RUN] Compilation Error: ${error.message}`);
                vscode.window.showErrorMessage(`Compilation Error: ${error.message}`);
            }
        }
    });

    // Configure command
    const configureCommand = vscode.commands.registerCommand('lesp.configure', async () => {
        const editor = vscode.window.activeTextEditor;
        const currentFile = editor?.document.uri.fsPath || '';

        const language = await vscode.window.showInputBox({
            prompt: 'Language',
            value: currentConfig?.language || 'logo',
            placeHolder: 'e.g., logo, python, javascript'
        });
        if (!language) return;

        const fileExtension = await vscode.window.showInputBox({
            prompt: 'File extension',
            value: currentConfig?.fileExtension || '.logo',
            placeHolder: 'e.g., .logo, .py, .js'
        });
        if (!fileExtension) return;

        const languageModule = await vscode.window.showInputBox({
            prompt: 'Language module (Python package path)',
            value: currentConfig?.languageModule || 'languages.minilogo',
            placeHolder: 'e.g., languages.minilogo, languages.mylang'
        });
        if (!languageModule) return;

        const lespBinary = await vscode.window.showInputBox({
            prompt: 'LESP binary path (required)',
            value: currentConfig?.lespBinary || '',
            placeHolder: 'e.g., /path/to/.venv/bin/lesp or /usr/local/bin/lesp',
            validateInput: (value) => {
                if (!value || value.trim() === '') {
                    return 'LESP binary path is required';
                }
                return null;
            }
        });
        if (!lespBinary) return;

        // Use existing configured file if available, otherwise try to find one
        let file = currentConfig?.file || '';

        // If no existing config, try current file or search for matching extension
        if (!file) {
            if (currentFile && currentFile.endsWith(fileExtension)) {
                file = currentFile;
            } else {
                const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
                if (workspaceFolder) {
                    const files = await vscode.workspace.findFiles(`**/*${fileExtension}`, '**/node_modules/**', 1);
                    if (files.length > 0) {
                        file = files[0].fsPath;
                    }
                }
            }
        }

        const selectedFile = await vscode.window.showInputBox({
            prompt: 'File to run',
            value: file,
            placeHolder: `Path to ${fileExtension} file`
        });
        if (!selectedFile) return;

        currentConfig = { language, fileExtension, languageModule, file: selectedFile, lespBinary };

        // Save extension association to workspace settings
        await saveExtensionAssociation(fileExtension, language, languageModule, lespBinary);

        treeDataProvider.refresh();
        vscode.window.showInformationMessage(`Configured: ${language} (${fileExtension}) [${languageModule}] [${lespBinary}] on ${selectedFile}`);
    });

    // Run command - starts VM and compiles code
    const runCommand = vscode.commands.registerCommand('lesp.run', async () => {
        if (!currentConfig) {
            vscode.window.showWarningMessage('Please configure debugger first (Ctrl+Shift+C)');
            return;
        }

        // Check if compilation error exists
        if (compilationError) {
            vscode.window.showErrorMessage('Cannot run: Fix compilation errors first');
            return;
        }

        try {
            // Start VM if not already started
            if (!isVMStarted) {
                outputPanel.clear();
                visualizationPanel.clear();
                outputPanel.show();
                outputPanel.appendLine('[RUN] Starting VM...');

                const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || path.dirname(currentConfig.file);
                const started = await vmClient!.start(currentConfig.lespBinary, workspaceRoot);

                if (!started) {
                    vscode.window.showErrorMessage('Failed to start VM process');
                    return;
                }
                isVMStarted = true;
            }

            // Set language module
            outputPanel.appendLine(`[RUN] Setting language module: ${currentConfig.languageModule}`);
            await vmClient!.setLanguageModule(currentConfig.languageModule);

            // Compile code
            outputPanel.appendLine('[RUN] Compiling code...');
            const code = await vscode.workspace.fs.readFile(vscode.Uri.file(currentConfig.file));
            const codeStr = Buffer.from(code).toString('utf8');

            await vmClient!.compile(codeStr);

            // Clear compilation error on successful compilation
            compilationError = undefined;
            treeDataProvider.refresh();

            // Start execution
            outputPanel.appendLine('[RUN] Starting execution...');
            const state = await vmClient!.start_execution();
            displayState(state);

            // Show visualization panel
            visualizationPanel.show();
        } catch (error: any) {
            // Set compilation error
            compilationError = error.message;
            treeDataProvider.refresh();

            vscode.window.showErrorMessage(`Compilation Error: ${error.message}`);
            outputPanel.appendLine(`[ERROR] ${error.message}`);
        }
    });

    // Step Forward command
    const stepForwardCommand = vscode.commands.registerCommand('lesp.stepForward', async () => {
        if (!currentConfig) {
            vscode.window.showWarningMessage('Please configure debugger first (Ctrl+Shift+C)');
            return;
        }

        if (compilationError) {
            vscode.window.showErrorMessage('Cannot step: Fix compilation errors first');
            return;
        }

        if (!isVMStarted) {
            vscode.window.showWarningMessage('Please run the program first (Ctrl+Shift+R)');
            return;
        }

        try {
            outputPanel.appendLine('[STEP FORWARD] Sending command...');
            const state = await vmClient!.stepForward();
            displayState(state);
        } catch (error: any) {
            vscode.window.showErrorMessage(`Error: ${error.message}`);
            outputPanel.appendLine(`[ERROR] ${error.message}`);
        }
    });

    // Step Backward command
    const stepBackwardCommand = vscode.commands.registerCommand('lesp.stepBackward', async () => {
        if (!currentConfig) {
            vscode.window.showWarningMessage('Please configure debugger first (Ctrl+Shift+C)');
            return;
        }

        if (compilationError) {
            vscode.window.showErrorMessage('Cannot step: Fix compilation errors first');
            return;
        }

        if (!isVMStarted) {
            vscode.window.showWarningMessage('Please run the program first (Ctrl+Shift+R)');
            return;
        }

        try {
            outputPanel.appendLine('[STEP BACKWARD] Sending command...');
            const state = await vmClient!.stepBackward();
            displayState(state);
        } catch (error: any) {
            vscode.window.showErrorMessage(`Error: ${error.message}`);
            outputPanel.appendLine(`[ERROR] ${error.message}`);
        }
    });

    const treeView = vscode.window.createTreeView('lespControls', { treeDataProvider });

    // View mode commands
    const viewTraceCommand = vscode.commands.registerCommand('lesp.viewTrace', () => {
        visualizationPanel.setViewMode('trace');
        visualizationPanel.show();
        vscode.window.showInformationMessage('View mode: Trace');
    });

    const viewCanvasCommand = vscode.commands.registerCommand('lesp.viewCanvas', () => {
        visualizationPanel.setViewMode('canvas');
        visualizationPanel.show();
        vscode.window.showInformationMessage('View mode: Canvas');
    });

    const viewBothCommand = vscode.commands.registerCommand('lesp.viewBoth', () => {
        visualizationPanel.setViewMode('both');
        visualizationPanel.show();
        vscode.window.showInformationMessage('View mode: Both (Trace + Canvas)');
    });

    context.subscriptions.push(
        configureCommand,
        runCommand,
        stepForwardCommand,
        stepBackwardCommand,
        viewTraceCommand,
        viewCanvasCommand,
        viewBothCommand,
        treeView,
        outputPanel,
        visualizationPanel,
        fileWatcher
    );
}

function displayState(state: VMState) {
    // Highlight current line in editor
    highlightCurrentLine(state);

    // Update visualization panel
    visualizationPanel.updateState(state);
}

function highlightCurrentLine(state: VMState) {
    if (!currentConfig || !currentLineDecoration) {
        return;
    }

    // Get current line from the latest snapshot in history
    let currentLine: number | undefined;

    if (state.history && state.history.length > 0) {
        const latestSnapshot = state.history[state.history.length - 1];
        currentLine = latestSnapshot.currentLine;
    }

    if (currentLine === undefined) {
        // Clear any existing highlights
        vscode.window.visibleTextEditors.forEach(editor => {
            editor.setDecorations(currentLineDecoration!, []);
        });
        return;
    }

    // Find the editor with the configured file
    const editor = vscode.window.visibleTextEditors.find(
        e => e.document.uri.fsPath === currentConfig!.file
    );

    if (!editor) {
        // If file is not open, try to open it
        vscode.workspace.openTextDocument(currentConfig.file).then(doc => {
            vscode.window.showTextDocument(doc, { preview: false, preserveFocus: true }).then(newEditor => {
                applyLineHighlight(newEditor, currentLine!);
            });
        });
    } else {
        applyLineHighlight(editor, currentLine);
    }
}

function applyLineHighlight(editor: vscode.TextEditor, lineNumber: number) {
    if (!currentLineDecoration) {
        return;
    }

    // Convert to 0-based line number (assuming currentLine is 1-based)
    const line = Math.max(0, lineNumber - 1);

    // Ensure line is within document bounds
    if (line >= editor.document.lineCount) {
        return;
    }

    const range = editor.document.lineAt(line).range;
    editor.setDecorations(currentLineDecoration, [range]);

    // Scroll to the line
    editor.revealRange(range, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
}

function createButton(label: string, command: string, icon: string): vscode.TreeItem {
    const item = new vscode.TreeItem(label);
    item.command = { command, title: label };
    item.iconPath = new vscode.ThemeIcon(icon);
    return item;
}

export function deactivate() {
    if (vmClient) {
        vmClient.dispose();
    }
    if (currentLineDecoration) {
        currentLineDecoration.dispose();
    }
    isVMStarted = false;
}

// Helper function to save extension association
async function saveExtensionAssociation(
    fileExtension: string,
    language: string,
    languageModule: string,
    lespBinary: string
) {
    const config = vscode.workspace.getConfiguration('lespRunner');
    const associations = config.get<ExtensionSettings>('extensionAssociations') || {};

    associations[fileExtension] = { language, languageModule, lespBinary };

    await config.update('extensionAssociations', associations, vscode.ConfigurationTarget.Workspace);
    outputPanel.appendLine(`[CONFIG] Saved association: ${fileExtension} → ${language} [${languageModule}] [${lespBinary}]`);
}

// Helper function to load config for a file
function loadConfigForFile(filePath: string) {
    const fileExtension = path.extname(filePath);
    if (!fileExtension) return;

    const config = vscode.workspace.getConfiguration('lespRunner');
    const associations = config.get<ExtensionSettings>('extensionAssociations') || {};

    const association = associations[fileExtension];
    if (association) {
        // Auto-load configuration for this file extension
        // Update the file path even if extension is the same
        const configChanged = !currentConfig || currentConfig.fileExtension !== fileExtension;
        const fileChanged = !currentConfig || currentConfig.file !== filePath;

        currentConfig = {
            language: association.language,
            fileExtension: fileExtension,
            languageModule: association.languageModule,
            file: filePath,
            lespBinary: association.lespBinary
        };

        if (configChanged) {
            treeDataProvider.refresh();
            outputPanel.appendLine(`[CONFIG] Auto-loaded config for ${fileExtension}: ${association.language} [${association.languageModule}] [${association.lespBinary}]`);
            vscode.window.showInformationMessage(`✓ LESP configured for ${fileExtension} files - Ready to run!`);
        } else if (fileChanged) {
            treeDataProvider.refresh();
            outputPanel.appendLine(`[CONFIG] Updated file to: ${filePath}`);
        }
    }
}
