import * as vscode from 'vscode';
import * as path from 'path';
import * as http from 'http';
import * as os from 'os';
import * as fs from 'fs';

let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;
let chatPanel: vscode.WebviewPanel | undefined;
let decorationsType: vscode.TextEditorDecorationType;

export function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('Terry AI');
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.text = '$(hubot) Terry';
    statusBarItem.tooltip = 'Terry AI Agent';
    statusBarItem.command = 'terry.chat';
    statusBarItem.show();

    // Create decoration type for Terry suggestions
    decorationsType = vscode.window.createTextEditorDecorationType({
        backgroundColor: 'rgba(255, 255, 0, 0.2)',
        isWholeLine: false,
    });

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('terry.chat', () => openChatPanel()),
        vscode.commands.registerCommand('terry.explain', () => explainSelected()),
        vscode.commands.registerCommand('terry.fix', () => fixSelected()),
        vscode.commands.registerCommand('terry.review', () => reviewFile()),
        vscode.commands.registerCommand('terry.generateTests', () => generateTests()),
        vscode.commands.registerCommand('terry.startServer', () => startServer()),
        vscode.commands.registerCommand('terry.openSettings', () => openSettings()),
        statusBarItem
    );

    outputChannel.appendLine('Terry AI Agent activated');
}

// ========== Webview Panel (Chat UI) ==========

function openChatPanel() {
    if (chatPanel) {
        chatPanel.reveal(vscode.ViewColumn.Beside);
        return;
    }

    chatPanel = vscode.window.createWebviewPanel(
        'terryChat',
        'Terry AI Chat',
        vscode.ViewColumn.Beside,
        {
            enableScripts: true,
            retainContextWhenHidden: true,
        }
    );

    chatPanel.webview.html = getWebviewContent();

    chatPanel.webview.onDidReceiveMessage(async (message) => {
        switch (message.command) {
            case 'send':
                await handleChatMessage(message.text);
                break;
            case 'openSettings':
                openSettings();
                break;
        }
    });

    chatPanel.onDidDispose(() => {
        chatPanel = undefined;
    });
}

function getWebviewContent(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terry AI Chat</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: var(--vscode-editor-background); color: var(--vscode-editor-foreground); }
        .container { max-width: 800px; margin: 0 auto; }
        .messages { margin-bottom: 20px; }
        .message { margin: 10px 0; padding: 12px; border-radius: 8px; }
        .user { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
        .assistant { background: var(--vscode-editor-inactiveSelectionBackground); }
        .input-area { display: flex; gap: 10px; }
        #input { flex: 1; padding: 12px; border: 1px solid var(--vscode-input-border); background: var(--vscode-input-background); color: var(--vscode-input-foreground); border-radius: 4px; font-size: 14px; }
        #send { padding: 12px 24px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
        #send:hover { background: var(--vscode-button-hoverBackground); }
        .settings-link { text-align: center; margin-top: 10px; }
        .settings-link a { color: var(--vscode-textLink-foreground); cursor: pointer; }
        pre { background: var(--vscode-editor-inactiveSelectionBackground); padding: 10px; border-radius: 4px; overflow-x: auto; }
        code { font-family: 'Courier New', monospace; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Terry AI Chat</h1>
        <div class="messages" id="messages"></div>
        <div class="input-area">
            <input type="text" id="input" placeholder="Ask Terry anything..." />
            <button id="send">Send</button>
        </div>
        <div class="settings-link">
            <a id="settings">⚙️ Settings</a>
        </div>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        const messages = document.getElementById('messages');
        const input = document.getElementById('input');
        const send = document.getElementById('send');

        send.addEventListener('click', () => {
            const text = input.value.trim();
            if (!text) return;
            addMessage('user', text);
            vscode.postMessage({ command: 'send', text });
            input.value = '';
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') send.click();
        });

        document.getElementById('settings').addEventListener('click', () => {
            vscode.postMessage({ command: 'openSettings' });
        });

        window.addEventListener('message', (event) => {
            const message = event.data;
            if (message.type === 'response') {
                addMessage('assistant', message.text);
            } else if (message.type === 'stream') {
                updateStreamingMessage(message.text);
            }
        });

        function addMessage(role, text) {
            const div = document.createElement('div');
            div.className = 'message ' + role;
            div.innerHTML = text.replace(/\n/g, '<br>').replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function updateStreamingMessage(text) {
            let last = messages.querySelector('.assistant:last-child');
            if (!last) {
                last = document.createElement('div');
                last.className = 'message assistant';
                messages.appendChild(last);
            }
            last.innerHTML = text.replace(/\n/g, '<br>');
            messages.scrollTop = messages.scrollHeight;
        }
    </script>
</body>
</html>`;
}

async function handleChatMessage(text: string) {
    if (!chatPanel) return;

    statusBarItem.text = '$(sync~spin) Terry thinking...';

    try {
        // Try streaming first, fallback to regular
        const config = vscode.workspace.getConfiguration('terry');
        const enableStreaming = config.get<boolean>('enableStreaming', true);

        if (enableStreaming) {
            await callTerryStreaming(text, (chunk) => {
                chatPanel?.webview.postMessage({ type: 'stream', text: chunk });
            });
        } else {
            const response = await callTerry(text);
            chatPanel.webview.postMessage({ type: 'response', text: response });
        }

        statusBarItem.text = '$(hubot) Terry';
    } catch (e: any) {
        chatPanel.webview.postMessage({ type: 'response', text: `❌ Error: ${e.message}` });
        statusBarItem.text = '$(error) Terry';
    }
}

// ========== Streaming Support ==========

async function callTerryStreaming(message: string, onChunk: (chunk: string) => void): Promise<void> {
    const config = vscode.workspace.getConfiguration('terry');
    const serverUrl = config.get<string>('serverUrl', 'http://127.0.0.1:8670');

    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ message, session_id: 'vscode_' + Date.now(), stream: true });
        const url = new URL('/api/chat/stream', serverUrl);
        const req = http.request({
            hostname: url.hostname,
            port: url.port || 8670,
            path: '/api/chat/stream',
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
            timeout: 120000,
        }, (res) => {
            let buffer = '';
            res.on('data', (chunk) => {
                buffer += chunk.toString();
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        if (jsonStr === '[DONE]') {
                            resolve();
                            return;
                        }
                        try {
                            const json = JSON.parse(jsonStr);
                            if (json.chunk) {
                                onChunk(json.chunk);
                            }
                        } catch {}
                    }
                }
            });
            res.on('end', () => resolve());
        });
        req.on('error', (e) => reject(e));
        req.write(data);
        req.end();
    });
}

// ========== Diff View ==========

async function showDiffAndApply(original: string, modified: string, filename: string): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;

    const action = await vscode.window.showInformationMessage(
        `Terry modified ${filename}. Review changes?`,
        'Show Diff',
        'Apply',
        'Dismiss'
    );

    if (action === 'Show Diff') {
        const tempDir = os.tmpdir();
        const originalPath = path.join(tempDir, `${filename}.original`);
        const modifiedPath = path.join(tempDir, `${filename}.modified`);
        const originalUri = vscode.Uri.file(originalPath);
        const modifiedUri = vscode.Uri.file(modifiedPath);

        fs.writeFileSync(originalPath, original);
        fs.writeFileSync(modifiedPath, modified);

        await vscode.commands.executeCommand('vscode.diff', originalUri, modifiedUri, `${filename} (Terry Changes)`);

        const apply = await vscode.window.showInformationMessage('Apply these changes?', 'Apply', 'Dismiss');
        if (apply === 'Apply') {
            await editor.edit(builder => {
                builder.replace(new vscode.Range(0, 0, editor.document.lineCount, 0), modified);
            });
        }

        // Cleanup temp files
        try { fs.unlinkSync(originalPath); } catch {}
        try { fs.unlinkSync(modifiedPath); } catch {}
    } else if (action === 'Apply') {
        await editor.edit(builder => {
            builder.replace(new vscode.Range(0, 0, editor.document.lineCount, 0), modified);
        });
    }
}

// ========== Inline Decorations ==========

function highlightTerrySuggestion(editor: vscode.TextEditor, ranges: vscode.Range[]): void {
    editor.setDecorations(decorationsType, ranges);
}

function clearHighlights(editor: vscode.TextEditor): void {
    editor.setDecorations(decorationsType, []);
}

// ========== Settings ==========

function openSettings() {
    vscode.commands.executeCommand('workbench.action.openSettings', 'terry');
}

// ========== Existing Functions (with improvements) ==========

async function callTerry(message: string): Promise<string> {
    const config = vscode.workspace.getConfiguration('terry');
    const serverUrl = config.get<string>('serverUrl', 'http://127.0.0.1:8670');
    const apiKey = config.get<string>('apiKey', '');

    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ message, session_id: 'vscode_' + Date.now() });
        const url = new URL('/api/chat', serverUrl);
        const headers: any = {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data)
        };
        if (apiKey) {
            headers['Authorization'] = `Bearer ${apiKey}`;
        }

        const req = http.request({
            hostname: url.hostname,
            port: url.port || 8670,
            path: '/api/chat',
            method: 'POST',
            headers,
            timeout: 120000,
        }, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    const result = JSON.parse(body);
                    resolve(result.response || result.error || body);
                } catch { resolve(body); }
            });
        });
        req.on('error', (e) => reject(new Error(`Cannot connect to Terry server at ${serverUrl}. Run "Terry: Start Server" first.`)));
        req.write(data);
        req.end();
    });
}

async function explainSelected() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const selection = editor.document.getText(editor.selection);
    if (!selection) {
        vscode.window.showWarningMessage('Select code to explain first.');
        return;
    }

    openChatPanel();
    if (chatPanel) {
        chatPanel.webview.postMessage({
            type: 'response',
            text: `🧑 Explain this code...`
        });
    }

    statusBarItem.text = '$(sync~spin) Terry explaining...';

    try {
        const response = await callTerry(
            `Explain the following code in detail. What does it do, how does it work, and are there any potential issues?\n\n\`\`\`\n${selection}\n\`\`\``
        );
        if (chatPanel) {
            chatPanel.webview.postMessage({ type: 'response', text: response });
        }
        statusBarItem.text = '$(hubot) Terry';
    } catch (e: any) {
        vscode.window.showErrorMessage(`Terry: ${e.message}`);
        statusBarItem.text = '$(error) Terry';
    }
}

async function fixSelected() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const selection = editor.document.getText(editor.selection);
    const originalContent = editor.document.getText();
    if (!selection) {
        vscode.window.showWarningMessage('Select code to fix first.');
        return;
    }

    openChatPanel();
    statusBarItem.text = '$(sync~spin) Terry fixing...';

    try {
        const response = await callTerry(
            `Fix any bugs, issues, or improvements in this code. Return ONLY the fixed code in a code block:\n\n\`\`\`\n${selection}\n\`\`\``
        );

        if (chatPanel) {
            chatPanel.webview.postMessage({ type: 'response', text: response });
        }

        const codeMatch = response.match(/```[\w]*\n([\s\S]*?)```/);
        if (codeMatch && editor) {
            const modifiedContent = originalContent.replace(selection, codeMatch[1]);
            await showDiffAndApply(originalContent, modifiedContent, path.basename(editor.document.fileName));
        }
        statusBarItem.text = '$(hubot) Terry';
    } catch (e: any) {
        vscode.window.showErrorMessage(`Terry: ${e.message}`);
        statusBarItem.text = '$(error) Terry';
    }
}

async function reviewFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;

    const content = editor.document.getText();
    const filename = editor.document.fileName;

    openChatPanel();
    statusBarItem.text = '$(sync~spin) Terry reviewing...';

    try {
        const response = await callTerry(
            `Review the following file (${path.basename(filename)}) for bugs, security issues, and code quality. Provide specific line references:\n\n\`\`\`\n${content.slice(0, 5000)}\n\`\`\``
        );

        if (chatPanel) {
            chatPanel.webview.postMessage({ type: 'response', text: response });
        }
        statusBarItem.text = '$(hubot) Terry';

        // Highlight problematic lines
        const lineMatch = response.match(/Line (\d+)/gi);
        if (lineMatch && editor) {
            const ranges = lineMatch.map(match => {
                const lineNum = parseInt(match.replace(/\D/g, '')) - 1;
                return new vscode.Range(lineNum, 0, lineNum, editor.document.lineAt(lineNum).text.length);
            });
            highlightTerrySuggestion(editor, ranges);
        }
    } catch (e: any) {
        vscode.window.showErrorMessage(`Terry: ${e.message}`);
        statusBarItem.text = '$(error) Terry';
    }
}

async function generateTests() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;

    const content = editor.document.getText();
    const filename = editor.document.fileName;

    openChatPanel();
    statusBarItem.text = '$(sync~spin) Terry generating tests...';

    try {
        const response = await callTerry(
            `Generate comprehensive unit tests for the following code. Cover edge cases and error handling. Return the test code in a code block:\n\n\`\`\`\n${content.slice(0, 4000)}\n\`\`\``
        );

        if (chatPanel) {
            chatPanel.webview.postMessage({ type: 'response', text: response });
        }

        const codeMatch = response.match(/```[\w]*\n([\s\S]*?)```/);
        if (codeMatch) {
            const testName = path.basename(filename).replace('.py', '_test.py');
            const testPath = path.join(path.dirname(filename), testName);
            const uri = vscode.Uri.file(testPath);
            const doc = await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(doc, { preview: false });
            const edit = new vscode.WorkspaceEdit();
            edit.insert(uri, new vscode.Position(0, 0), codeMatch[1]);
            await vscode.workspace.applyEdit(edit);
            vscode.window.showInformationMessage(`Tests created: ${testName}`);
        }
        statusBarItem.text = '$(hubot) Terry';
    } catch (e: any) {
        vscode.window.showErrorMessage(`Terry: ${e.message}`);
        statusBarItem.text = '$(error) Terry';
    }
}

function startServer() {
    const terminal = vscode.window.createTerminal('Terry Server');
    terminal.show();
    terminal.sendText('terry webui');
    vscode.window.showInformationMessage('Terry server starting at http://127.0.0.1:8670');
    statusBarItem.text = '$(vm-running) Terry';
}

export function deactivate() {
    if (statusBarItem) statusBarItem.dispose();
    if (outputChannel) outputChannel.dispose();
    if (chatPanel) chatPanel.dispose();
    if (decorationsType) decorationsType.dispose();
}
