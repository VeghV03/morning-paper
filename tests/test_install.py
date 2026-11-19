"""`paper install` on macOS and Linux, with launchctl and systemctl recorded rather than run.
(Windows runs for real in CI.)"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from paper import cli
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain


class LinuxTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.unit = Path(tempfile.mkdtemp()) / "morning-paper.service"
        self.ran = []
        run = lambda cmd, **kw: self.ran.append(cmd) or SimpleNamespace(returncode=0, stderr="")
        self.patches = [mock.patch.object(cli, "UNIT", self.unit), mock.patch.object(cli.subprocess, "run", run),
                        mock.patch.object(cli.shutil, "which", lambda name: "/usr/bin/" + name),
                        mock.patch.dict(os.environ, {"PATH": "/home/r/paper/.tools/node/bin:/usr/bin"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_the_unit_runs_the_server_with_node_and_the_home(self):
        self.assertEqual(cli._install_linux(self.h, again=False), 0)
        text = self.unit.read_text(encoding="utf-8")
        self.assertIn(f'ExecStart="{sys.executable}" -m paper.cli serve', text)
        self.assertIn(f'Environment="PAPER_HOME={self.h.root}"', text)
        self.assertIn('Environment="PATH=/home/r/paper/.tools/node/bin:/usr/bin"', text)
        self.assertIn('Environment="PYTHONUTF8=1"', text)
        self.assertEqual([c[2:] for c in self.ran],
                         [["daemon-reload"], ["enable", self.unit.name], ["restart", self.unit.name]])

    def test_again_restarts_only_what_was_installed(self):
        self.assertEqual(cli._install_linux(self.h, again=True), 0)
        self.assertEqual(self.ran, [])
        cli._install_linux(self.h, again=False)
        self.ran.clear()
        cli._install_linux(self.h, again=True)
        self.assertEqual(self.ran, [["systemctl", "--user", "restart", self.unit.name]])


class MacTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.agent = Path(tempfile.mkdtemp()) / f"{cli.LABEL}.plist"
        self.ran = []
        run = lambda cmd, **kw: self.ran.append(cmd) or SimpleNamespace(returncode=0, stderr="")
        self.patches = [mock.patch.object(cli, "AGENT", self.agent), mock.patch.object(cli.subprocess, "run", run),
                        mock.patch.object(cli.os, "getuid", lambda: 501, create=True)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_install_writes_the_agent_and_loads_it(self):
        self.assertEqual(cli._install_mac(self.h, again=False), 0)
        agent = cli.plistlib.loads(self.agent.read_bytes())
        self.assertEqual(agent["ProgramArguments"], [sys.executable, "-m", "paper.cli", "serve"])
        self.assertEqual(agent["EnvironmentVariables"]["PYTHONUTF8"], "1")
        self.assertEqual([c[:2] for c in self.ran], [["launchctl", "bootout"], ["launchctl", "bootstrap"]])

    def test_again_kickstarts_only_what_was_installed(self):
        cli._install_mac(self.h, again=True)
        self.assertEqual(self.ran, [])
        cli._install_mac(self.h, again=False)
        self.ran.clear()
        cli._install_mac(self.h, again=True)
        self.assertEqual(self.ran, [["launchctl", "kickstart", "-k", f"gui/501/{cli.LABEL}"]])


if __name__ == "__main__":
    unittest.main()
