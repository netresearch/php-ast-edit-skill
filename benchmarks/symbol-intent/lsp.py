"""Bounded stdio client for the pinned Phpactor rename protocol; never applies edits."""

import json
import os
import queue
import signal
import subprocess
import threading
import time

RELEASE = "2026.07.22.0"
PHAR_SHA256 = "8c0155380b9d7559a12f35ddf8d09c1dc23e72f1797498038251fc35ad15574d"
CONFIG = {
    "composer.enable": False,
    "language_server_configuration.auto_config": False,
    "language_server.diagnostic_providers": [],
    "language_server.diagnostics_on_open": False,
    "language_server.diagnostics_on_update": False,
    "language_server.diagnostics_on_save": False,
    "indexer.stub_paths": [],
    "indexer.enabled_watchers": ["lsp"],
    "indexer.include_patterns": ["/**/*.php"],
    "indexer.exclude_patterns": [],
    "indexer.follow_symlinks": False,
    "indexer.supported_extensions": ["php"],
    "indexer.max_filesize_to_index": 1_000_000,
}


class IntentError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise IntentError(message)


def isolated_environment(directory):
    env = os.environ.copy()
    for name in (
        "XDG_CONFIG_HOME",
        "XDG_CONFIG_DIRS",
        "XDG_DATA_HOME",
        "XDG_DATA_DIRS",
        "XDG_CACHE_HOME",
    ):
        target = directory / name.lower()
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[name] = str(target)
    return env


def read_frame(stream):
    headers = {}
    while True:
        line = stream.readline(8193)
        require(line, "Phpactor closed its output")
        require(len(line) <= 8192, "Oversized LSP header")
        if line == b"\r\n":
            break
        key, value = line.decode("ascii").split(":", 1)
        require(key.lower() not in headers, "Duplicate LSP header")
        headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "-1"))
    require(0 < length <= 16_000_000, "Invalid LSP content length")
    content = stream.read(length)
    require(len(content) == length, "Incomplete LSP frame")
    message = json.loads(content)
    require(
        isinstance(message, dict) and message.get("jsonrpc") == "2.0",
        "Invalid LSP message",
    )
    return message


class Client:
    def __init__(self, phar, root, directory, timeout=60):
        self.started = time.monotonic()
        self.deadline = self.started + timeout
        self.events = []
        self.messages = []
        self.progress = {}
        self.completed_indexes = []
        self.counter = 0
        self.inbox = queue.Queue()
        self.stderr = (directory / "phpactor.stderr").open("wb")
        argv = [
            "php",
            str(phar),
            "language-server",
            "--working-dir",
            str(root),
            "--config-extra",
            json.dumps(CONFIG),
        ]
        # Pinned local executable; argv, no shell. See benchmarks/TRUST.md.
        self.process = subprocess.Popen(  # NOSONAR(S6350)
            argv,
            cwd=root,
            env=isolated_environment(directory),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            start_new_session=True,
        )
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while True:
                self.inbox.put(read_frame(self.process.stdout))
        except (ValueError, OSError) as error:
            self.inbox.put(error)

    def send(self, message):
        message = {"jsonrpc": "2.0", **message}
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        self.process.stdin.flush()
        self.events.append({"direction": "out", "message": message})

    def receive(self):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "Phpactor deadline exceeded")
        try:
            message = self.inbox.get(timeout=remaining)
        except queue.Empty as error:
            raise IntentError("Phpactor deadline exceeded") from error
        if isinstance(message, Exception):
            raise message
        self.events.append({"direction": "in", "message": message})
        self._notification(message)
        if "method" in message and "id" in message:
            require(
                message["method"] == "window/workDoneProgress/create",
                "Unsupported LSP server request",
            )
            self.send({"id": message["id"], "result": None})
        return message

    def _notification(self, message):
        method = message.get("method")
        if method in ("window/showMessage", "window/logMessage"):
            params = message.get("params", {})
            self.messages.append({"method": method, **params})
            require(
                params.get("type") != 1,
                "Phpactor reported an error: " + str(params.get("message")),
            )
        if method == "$/progress":
            params = message["params"]
            token, value = params["token"], params["value"]
            if value["kind"] == "begin":
                self.progress[token] = value
            if (
                value["kind"] == "end"
                and self.progress.get(token, {}).get("title") == "Indexing workspace"
            ):
                self.completed_indexes.append(
                    {"begin": self.progress[token], "end": value}
                )

    def request(self, method, params):
        self.counter += 1
        identifier = self.counter
        self.send({"id": identifier, "method": method, "params": params})
        while True:
            message = self.receive()
            if message.get("id") == identifier and "method" not in message:
                require(
                    "error" not in message,
                    "LSP request failed: " + str(message.get("error")),
                )
                require("result" in message, "LSP response has no result")
                return message["result"]

    def initialize(self, root, expected_files):
        result = self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {
                    "window": {"workDoneProgress": True},
                    "workspace": {
                        "workspaceEdit": {"documentChanges": True},
                        "didChangeWatchedFiles": {"dynamicRegistration": False},
                    },
                    "general": {"positionEncodings": ["utf-16"]},
                },
            },
        )
        require(
            result.get("serverInfo", {}).get("version") == RELEASE,
            "Unexpected Phpactor release",
        )
        capabilities = result.get("capabilities", {})
        provider = capabilities.get("renameProvider")
        require(
            isinstance(provider, dict) and provider.get("prepareProvider") is True,
            "Missing prepareRename capability",
        )
        require(
            capabilities.get("positionEncoding", "utf-16") == "utf-16",
            "Unsupported position encoding",
        )
        self.send({"method": "initialized", "params": {}})
        while not self.completed_indexes:
            self.receive()
        expected = f"{expected_files} PHP files"
        require(
            self.completed_indexes[0]["begin"].get("message") == expected,
            "Resolver search-file count differs from snapshot",
        )
        return result

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()
        self.stderr.close()
        self.reader.join(timeout=1)


def rename(phar, root, directory, file, position, expected_range, new_name, php_files):
    client = Client(phar, root, directory)
    try:
        server = client.initialize(root, php_files)
        params = {"textDocument": {"uri": file.as_uri()}, "position": position}
        prepared = client.request("textDocument/prepareRename", params)
        require(
            prepared == expected_range,
            "prepareRename does not identify the requested method name exactly",
        )
        edits = client.request("textDocument/rename", {**params, "newName": new_name})
        client.request("shutdown", None)
        client.send({"method": "exit", "params": None})
        return {
            "workspace_edit": edits,
            "server": server,
            "messages": client.messages,
            "index": client.completed_indexes,
            "elapsed_ms": (time.monotonic() - client.started) * 1000,
        }
    finally:
        client.close()
        (directory / "lsp.json").write_text(json.dumps(client.events, indent=2) + "\n")
