# Packaging the LESP Runner Extension

## Prerequisites

Install the VS Code Extension Manager (vsce):

```bash
npm install -g @vscode/vsce
```

## Steps to Package

1. **Compile the TypeScript code:**
   ```bash
   npm run compile
   ```

2. **Package the extension:**
   ```bash
   npm run package
   ```
   
   Or directly:
   ```bash
   vsce package
   ```

   This will create a `.vsix` file (e.g., `lesp-runner-0.0.1.vsix`)

## Installing the Extension

### Method 1: Via VS Code UI
1. Open VS Code
2. Go to Extensions view (Ctrl+Shift+X)
3. Click the "..." menu at the top
4. Select "Install from VSIX..."
5. Choose the `.vsix` file

### Method 2: Via Command Line
```bash
code --install-extension lesp-runner-0.0.1.vsix
```

### Method 3: Via Command Palette
1. Open Command Palette (Ctrl+Shift+P)
2. Type "Extensions: Install from VSIX..."
3. Select the `.vsix` file

## Uninstalling

```bash
code --uninstall-extension lesp.lesp-runner
```

Or use the Extensions view in VS Code.

## Notes

- The `.vsix` file is portable and can be shared with others
- No need to publish to the marketplace for private use
- The extension will work in any VS Code instance (not just debug mode)
