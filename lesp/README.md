# LESP - Language Execution Server Protocol

LESP is a JSON-RPC based protocol for compiling and executing code using LipVM. It provides a server that can be used by IDEs, editors, and other tools to interact with LipVM.

## Overview

The LESP server is a standalone application that:
- Accepts JSON-RPC requests over stdin
- Compiles code using configurable language modules
- Executes code on the LipVM stack machine
- Supports step-by-step debugging (forward and backward)
- Returns execution state and results

## Installation

The LESP server is installed as part of the lipvm package:

```bash
pip install -e .
```

This creates a `lesp` command-line tool.

## Usage

### Starting the Server

```bash
# Start with default language (minilogo)
lesp

# Start with a specific language module
lesp --language-module languages.minilogo
```

The server reads JSON-RPC requests from stdin and writes responses to stdout.

### Protocol

LESP uses a simple JSON-RPC protocol. Each request is a JSON object on a single line:

```json
{"id": 1, "method": "methodName", "params": {...}}
```

Each response is also a JSON object on a single line:

```json
{"id": 1, "success": true, ...}
```

## Supported Methods

### setLanguageModule

Set the language module to use for compilation.

**Request:**
```json
{
  "id": 1,
  "method": "setLanguageModule",
  "params": {
    "module": "languages.minilogo"
  }
}
```

**Response:**
```json
{
  "id": 1,
  "success": true,
  "message": "Language module set to languages.minilogo"
}
```

### compile

Compile source code.

**Request:**
```json
{
  "id": 2,
  "method": "compile",
  "params": {
    "code": "pen down\nmove 100 100\npen up"
  }
}
```

**Response:**
```json
{
  "id": 2,
  "success": true,
  "message": "Code compiled"
}
```

### start

Start execution of compiled code.

**Request:**
```json
{
  "id": 3,
  "method": "start",
  "params": {}
}
```

**Response:**
```json
{
  "id": 3,
  "success": true,
  "heap": {
    "lines": [[...], [...]]
  },
  "historyLength": 10
}
```

### stepForward

Step forward one instruction in the execution.

**Request:**
```json
{
  "id": 4,
  "method": "stepForward",
  "params": {}
}
```

**Response:**
```json
{
  "id": 4,
  "success": true,
  "heap": {...},
  "position": 5
}
```

### stepBackward

Step backward one instruction in the execution.

**Request:**
```json
{
  "id": 5,
  "method": "stepBackward",
  "params": {}
}
```

**Response:**
```json
{
  "id": 5,
  "success": true,
  "heap": {...},
  "position": 4
}
```

### getState

Get the current execution state.

**Request:**
```json
{
  "id": 6,
  "method": "getState",
  "params": {}
}
```

**Response:**
```json
{
  "id": 6,
  "success": true,
  "heap": {...}
}
```

## Example Session

```bash
# Start the server
lesp

# Send requests (one per line)
{"id":1,"method":"compile","params":{"code":"pen down\nmove 100 100"}}
{"id":2,"method":"start","params":{}}
{"id":3,"method":"getState","params":{}}
```

## Integration

### VS Code Extension

The LESP server is designed to be used with the LipVM VS Code extension. The extension spawns the server as a subprocess and communicates via stdin/stdout.

### Other Editors

Any editor or tool can integrate with LESP by:
1. Spawning the `lesp` process
2. Sending JSON-RPC requests to stdin
3. Reading JSON-RPC responses from stdout

## Logging

The server logs all activity to `lipvm-server.log` in the current directory. This includes:
- Request/response details
- Compilation errors
- Execution state changes
- Error messages

## Error Handling

All errors are returned in the response:

```json
{
  "id": 1,
  "success": false,
  "error": "Error message here"
}
```

Common errors:
- `"No code compiled"` - Tried to execute without compiling first
- `"No execution started"` - Tried to step without starting execution
- `"Compilation failed: ..."` - Syntax or semantic errors in code
- `"Failed to initialize LipVM: ..."` - Invalid language module

## Architecture

```
┌─────────────────┐
│   IDE/Editor    │
└────────┬────────┘
         │ JSON-RPC over stdin/stdout
         │
┌────────▼────────┐
│  LESP Server    │
│  (lesp/server)  │
└────────┬────────┘
         │ Python API
         │
┌────────▼────────┐
│     LipVM       │
│  (backend/*)    │
└────────┬────────┘
         │
┌────────▼────────┐
│   Language      │
│   Compiler      │
│ (languages/*)   │
└─────────────────┘
```

## Development

### Running Tests

```bash
# Test the server manually
echo '{"id":1,"method":"compile","params":{"code":"pen down"}}' | lesp
```

### Adding New Methods

1. Add a handler method to `LESPServer` class in `lesp/server.py`
2. Register it in the `handlers` dictionary in `handle_request()`
3. Document it in this README

## See Also

- [LipVM Documentation](../README.md)
- [VS Code Extension](../extension/README.md)
- [Language Development Guide](../languages/README.md)
