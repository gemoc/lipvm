# LESP Runner

A VS Code extension for debugging and running programs with LESP (Language Execution Server Protocol), featuring time-travel debugging with step forward and backward through execution.

## Features

- **LESP Protocol** - Language Execution Server Protocol for RPC communication
- **Time-travel debugging** - Step forward and backward through program execution
- **Auto-compile on save** - Automatically recompiles when you save the configured file
- **Persistent configuration** - Config stays active across file switches
- **File extension associations** - Automatically loads config based on file extension
- **Workspace settings** - Saves extension associations to `.vscode/settings.json`
- **Configurable LESP path** - Specify custom LESP binary location
- **Full RPC logging** - All communication between extension and server is logged

## Quick Start

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Compile the extension**
   ```bash
   npm run compile
   ```

3. **Launch in VS Code**
   - Press `F5` to open a new VS Code window with the extension loaded
   - Or run: `code --extensionDevelopmentPath=$(pwd) --disable-extensions /path/to/your/project`

4. **Ensure Python 3 is available**
   - The extension uses `python3` command to run the VM server
   - Make sure `python3` is in your PATH

## Usage

### Configure the Debugger

Use the **Configure** button in the LESP Runner sidebar or open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run `LESP: Configure` to set up:
- **Language**: e.g., `logo`
- **File extension**: e.g., `.logo`
- **Language module**: Python package path (e.g., `languages.minilogo`)
  - This specifies which Parser, Lexer, and Compiler to use
  - Default: `languages.minilogo`
  - Custom: `languages.mylang` (if you have your own language implementation)
- **LESP Binary** (required): Path to lesp executable
  - **For UV venv installations**: `/path/to/project/.venv/bin/lesp`
  - **For system installation**: `/usr/local/bin/lesp` or `lesp` (if in PATH)
  - The binary will be run with `--server` flag to start the JSON-RPC server
- **File to run**: Path to your program file

**The configuration is automatically saved** to workspace settings (`.vscode/settings.json`) and associated with the file extension. Next time you open a file with the same extension, the configuration will be loaded automatically and you can just click Run!

**Example workspace settings:**

### How It Works

When you run your program, the extension:
1. Executes: `lesp` (runs in server mode by default)
2. Communicates via JSON-RPC over stdin/stdout
3. Sends commands: `setLanguageModule`, `compile`, `start`, `stepForward`, `stepBackward`
4. Receives VM state updates with heap and execution position

### Automatic Configuration Loading

Once you configure an extension (e.g., `.logo`), the extension will:
1. Save the association to workspace settings
2. **Automatically load the configuration when you open any file with that extension**
3. Update the sidebar to show the current file and configuration
4. Show a notification: "✓ LESP configured for .logo files - Ready to run!"

**You can then just click Run or press F5 without reconfiguring!**

The sidebar will show:
- 📄 Current file name and path
- Language and module information
- Control buttons (Configure, Run, Step Forward, Step Backward)
```json
{
  "lespRunner.extensionAssociations": {
    ".logo": {
      "language": "logo",
      "languageModule": "languages.minilogo",
      "lespBinary": "/path/to/.venv/bin/lesp"
    },
    ".mylang": {
      "language": "mylang",
      "languageModule": "languages.mylang",
      "lespBinary": "/usr/local/bin/lesp"
    }
  }
}
```

### Run and Debug

- **Run**: `F5` or click the **Run** button in the sidebar - Starts the VM and executes your program
- **Step Forward**: Click the **Step Forward** button in the sidebar - Move forward one step in execution
- **Step Backward**: Click the **Step Backward** button in the sidebar - Move backward one step in execution

All commands are also available via the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).

### Visualization Views

The extension provides multiple visualization modes:

- **Trace View** - Shows execution history with heap state at each step
- **Canvas View** - Renders graphical output from `heap.lines` array
- **Both Views** - Split view showing both trace and canvas

**Switch views from the sidebar or command palette:**
- `LESP: View Trace` - Show execution trace only
- `LESP: View Canvas` - Show canvas output only  
- `LESP: View Both` - Show both views side-by-side

**Canvas Format:**
The canvas view reads `heap.lines` array where each line is:
```python
[start_point, end_point, color]
# Example: [[100, 100], [200, 200], "#FF0000"]
```

This matches the format from the original IDE.py implementation.

### View Output

Open the **Output** panel and select:
- **LESP Runner** - Main output with VM state and execution info
- **LESP RPC** - Detailed RPC communication logs

The **LESP Visualization** panel opens automatically when you run a program and shows:
- **Trace View**: Step-by-step execution history with heap snapshots
- **Canvas View**: Graphical rendering of lines from `heap.lines`
- **Both Views**: Side-by-side trace and canvas

You can switch between view modes using the buttons in the sidebar.

## Architecture

```
┌─────────────────┐         JSON-RPC Protocol     ┌──────────────┐
│  VS Code        │◄──────────────────────────────►│  lesp        │
│  Extension      │   (over stdin/stdout)          │  --server    │
│  (TypeScript)   │                                │              │
└─────────────────┘                                └──────────────┘
```

### Components

- **extension.ts** - Main extension entry point with commands and UI
- **vmClient.ts** - RPC client that spawns and communicates with lesp binary
- **visualizationPanel.ts** - Webview-based visualization (trace/canvas views)
- **lesp** (external) - LESP binary, runs in server mode
- **Language implementations** (external) - Parser/Lexer/Compiler modules

### RPC Protocol

All messages are JSON over newline-delimited stdin/stdout:

**Set Language Module:**
```json
{"id": 0, "method": "setLanguageModule", "params": {"module": "languages.minilogo"}}
```

**Compile Request:**
```json
{"id": 1, "method": "compile", "params": {"code": "..."}}
```

**Response:**
```json
{"id": 1, "success": true, "heap": {...}, "historyLength": 10}
```

### Supported RPC Methods

- `setLanguageModule(module)` - Set the language module (Parser/Lexer/Compiler)
- `compile(code)` - Compile source code
- `start()` - Start execution
- `stepForward()` - Step forward one instruction
- `stepBackward()` - Step backward one instruction
- `getState()` - Get current VM state

## Development

### Watch mode
```bash
npm run watch
```

### Debugging
1. Open this folder in VS Code
2. Press `F5` to launch extension development host
3. Set breakpoints in TypeScript files
4. Check logs in Output panels

## Files

- `src/extension.ts` - Main extension code
- `src/vmClient.ts` - RPC client
- `src/visualizationPanel.ts` - Webview-based visualization
- `package.json` - Extension manifest
- `tsconfig.json` - TypeScript configuration

**Note:** The `lesp` binary is not part of this extension. It must be installed separately.

## Requirements

- VS Code ^1.60.0
- LESP binary installed
  - Provides the `lesp` binary for server mode
- Node.js and npm (for extension development)
