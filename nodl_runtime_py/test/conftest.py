# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fixture_nodes import READY

TEST_DIR = Path(__file__).parent
TIMEOUT_S = 15
# How often a signal is resent while waiting for a process that needs more than one.
RESEND_PERIOD_S = 0.3


class NodeProcess:
    """A node executable started in a subprocess, with fixture_nodes importable."""

    def __init__(self, script, argv=()):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(TEST_DIR), os.environ.get('PYTHONPATH')])))
        self.process = subprocess.Popen(
            [sys.executable, str(script), *argv],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        # A reader thread, so that waiting for output can time out.
        self._lines = queue.Queue()
        self._output = []
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _drain(self):
        while not self._lines.empty():
            line = self._lines.get_nowait()
            if line is not None:
                self._output.append(line)

    def kill(self):
        """Kill the process and return everything it printed."""
        self.process.kill()
        self.process.wait()
        self._reader.join(TIMEOUT_S)
        self._drain()
        return ''.join(self._output)

    def wait_ready(self, text=READY, timeout_s=TIMEOUT_S):
        """Return the first line containing `text`, or fail with the output so far."""
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                line = self._lines.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                pytest.fail(f'Did not print {text!r} within {timeout_s}s:\n{self.kill()}')
            if line is None:
                pytest.fail(f'Exited with {self.process.wait()} before printing {text!r}:\n{"".join(self._output)}')
            self._output.append(line)
            if text in line:
                return line.strip()

    def stop(self, sig=signal.SIGINT):
        """Send `sig`, then return the exit code and remaining output."""
        self.process.send_signal(sig)
        return self.finish()

    def stop_with_repeated(self, sig):
        """Send `sig` every RESEND_PERIOD_S until exit, then return the exit code and remaining output."""
        deadline = time.monotonic() + TIMEOUT_S
        while self.process.poll() is None:
            if time.monotonic() > deadline:
                pytest.fail(f'Still running after {TIMEOUT_S}s of {sig.name}:\n{self.kill()}')
            self.process.send_signal(sig)
            try:
                self.process.wait(timeout=RESEND_PERIOD_S)
            except subprocess.TimeoutExpired:
                pass
        return self.finish()

    def finish(self):
        """Wait for exit, then return the exit code and remaining output."""
        try:
            self.process.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            pytest.fail(f'Did not exit within {TIMEOUT_S}s:\n{self.kill()}')
        self._reader.join(TIMEOUT_S)
        self._drain()
        return self.process.returncode, ''.join(self._output)


@pytest.fixture
def run_script():
    processes = []

    def start(script, argv=()):
        processes.append(NodeProcess(script, argv))
        return processes[-1]

    yield start
    for node in processes:
        if node.process.poll() is None:
            node.kill()
