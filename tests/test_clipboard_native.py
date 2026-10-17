"""Clipboard X11 real em display privado; preserva a área de transferência do usuário."""

import os
import select
import shutil
import subprocess

import pytest

from codar.studio.clipboard import copy_text


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('Xvfb') or not shutil.which('xclip'),
                    reason='requer Xvfb e xclip; outros sistemas exigem validação nativa própria')
def test_native_clipboard_unicode_indent_and_newlines(monkeypatch):
    server = subprocess.Popen(['Xvfb', '-displayfd', '1', '-screen', '0', '640x480x24', '-nolisten', 'tcp'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        ready, _, _ = select.select([server.stdout], [], [], 5)
        assert ready and server.poll() is None, 'Xvfb não iniciou em 5s'
        display = server.stdout.readline().decode().strip()
        assert display.isdigit()
        monkeypatch.setenv('DISPLAY', ':' + display)
        for key in ('WAYLAND_DISPLAY', 'SSH_CONNECTION', 'SSH_TTY'):
            monkeypatch.delenv(key, raising=False)

        class App:
            def copy_to_clipboard(self, value):
                self.clipboard = value

        text = 'def saudacao():\n    print("Olá, João 👋")\n\n'
        app = App()
        copy_text(app, text)
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], capture_output=True,
                                timeout=5, check=True)
        assert app.clipboard == text
        assert result.stdout.decode('utf-8') == text
    finally:
        server.terminate()
        server.wait(timeout=5)
        if server.stdout:
            server.stdout.close()
