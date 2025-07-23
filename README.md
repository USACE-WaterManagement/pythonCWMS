# Python CWMS Portable Environment

A portable, Windows, Python environment bundled with CWMS libraries and dependencies.

## What's Included

- **WinPython 3.12.10.1**: Portable Python distribution
- **Pre-installed Libraries**: All dependencies from `requirements_binary_only.txt`
- **Custom Configuration**: CWMS-specific setup and utilities

## Quick Start

### Download
Go to [Releases](../../releases) and download the latest `pythonCWMS*.7z` file.

### Installation
1. Extract the `.7z` file to your desired location
2. No installation required - it's completely portable!

### Usage
- Run `WinPython Command Prompt.exe` for command line access
- Run `WinPython Interpreter.exe` for Python IDLE
- Or use `pythonCWMS.bat` for the custom CWMS environment

## Development

### Building Locally
1. Clone this repository
2. Create/modify `requirements_binary_only.txt` with your dependencies
3. Push a tag to trigger the build: `git tag v0.8 && git push origin v0.8`

### Manual Build
You can also trigger a build manually from the Actions tab.

## Requirements File

The `requirements_binary_only.txt` file contains all Python packages to be installed. Only binary wheels are used to ensure compatibility and faster installation.

