#!/usr/bin/env python3
"""guest-run 合同测试：路径换算、退出码解析、干运行、探测与并发锁。

运行：python3 tests/test_guest_run.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "guest-run"
LOADER = SourceFileLoader("pemb_guest_run", str(BIN))
SPEC = importlib.util.spec_from_loader("pemb_guest_run", LOADER)
MOD = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MOD)

IMPORT_HEAD = """
import importlib.util, json, sys
from importlib.machinery import SourceFileLoader
_loader = SourceFileLoader("gr", sys.argv[1])
_spec = importlib.util.spec_from_loader("gr", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)
"""

HOLDER = IMPORT_HEAD + """
key, hold, job = sys.argv[2], float(sys.argv[3]), sys.argv[4]
fd, wait, pos, err = mod.acquire_lock(key, 10, {"job_id": job, "action": "run"})
print("ACQUIRED" if fd is not None else "FAILED", flush=True)
if fd is None:
    sys.exit(1)
import time
time.sleep(hold)
mod.release_lock(fd, key)
"""

WAITER = IMPORT_HEAD + """
key, timeout = sys.argv[2], float(sys.argv[3])
fd, wait, pos, err = mod.acquire_lock(key, timeout, {"job_id": "waiter", "action": "run"})
print(json.dumps({"acquired": fd is not None, "wait_ms": wait,
                  "position": pos, "error": err}))
if fd is not None:
    mod.release_lock(fd, key)
"""


class 路径换算测试(unittest.TestCase):
    def test_共享根本身(self):
        self.assertEqual(
            MOD.to_unc(Path.home(), Path.home(), r"\\Mac\Home"), r"\\Mac\Home"
        )

    def test_子目录换成反斜杠(self):
        p = Path.home() / "work" / "proj" / "iar" / "x.bat"
        self.assertEqual(
            MOD.to_unc(p, Path.home(), r"\\Mac\Home"),
            r"\\Mac\Home\work\proj\iar\x.bat",
        )

    def test_自定义共享根(self):
        p = Path.home() / "a" / "b.bat"
        self.assertEqual(
            MOD.to_unc(p, Path.home(), r"\\VM\Share"), r"\\VM\Share\a\b.bat"
        )

    def test_越界路径报错(self):
        with self.assertRaises(ValueError):
            MOD.to_unc(Path("/etc/hosts"), Path.home(), r"\\Mac\Home")


class 退出码解析测试(unittest.TestCase):
    def test_取最后一个标记(self):
        text = "CLI BUILD END rc=0\n---- x ----\nIARBUILD_EXIT=2\n"
        self.assertEqual(MOD.parse_exit_code(text), 2)

    def test_多种格式(self):
        self.assertEqual(MOD.parse_exit_code("CSPYBAT_EXIT=0"), 0)
        self.assertEqual(MOD.parse_exit_code("JLINK_EXIT=1"), 1)
        self.assertEqual(MOD.parse_exit_code("FLASH END rc=90"), 90)

    def test_无标记返回空(self):
        self.assertIsNone(MOD.parse_exit_code("Build succeeded"))


class 命令行合同测试(unittest.TestCase):
    def 调用(self, *args):
        return subprocess.run(
            [sys.executable, str(BIN), *args],
            capture_output=True,
            text=True,
            timeout=90,
        )

    def test_帮助可用(self):
        r = self.调用("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("guest-run", r.stdout)

    def test_探测返回必需字段(self):
        r = self.调用("probe")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        for key in ("ok", "vm", "transport", "prlctl_available", "share_root", "mac_home"):
            self.assertIn(key, d)
        self.assertIn(d["transport"], ("prlctl", "stub"))
        self.assertTrue(d["ok"])

    def test_干运行不产生日志(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            bat = Path(tmp) / "x.bat"
            bat.write_bytes(b"@echo off\r\n")
            log = Path(tmp) / "x.log"
            r = self.调用(
                "run", "--bat", str(bat), "--log", str(log),
                "--marker", "DONE", "--dry-run",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertTrue(d["dry_run"])
            self.assertTrue(d["plan"])
            self.assertFalse(log.exists())

    def test_可强制传输方式(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            bat = Path(tmp) / "x.bat"
            bat.write_bytes(b"@echo off\r\n")
            r = self.调用(
                "run", "--bat", str(bat), "--log", str(Path(tmp) / "x.log"),
                "--marker", "DONE", "--transport", "stub", "--dry-run",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["transport"], "stub")

    def test_单条命令干运行不写临时批处理(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            r = self.调用(
                "exec", "--command", "echo ok",
                "--log", str(Path(tmp) / "p.log"), "--dry-run",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((Path(tmp) / "pemb_exec.bat").exists())


class 锁名测试(unittest.TestCase):
    class 参数:
        def __init__(self, scope="device", key=None):
            self.lock_scope = scope
            self.lock_key = key

    def test_默认按设备收敛(self):
        self.assertEqual(MOD.lock_key_for(self.参数(), "Win11_M7"), "dev-Win11_M7")

    def test_vm作用域(self):
        self.assertEqual(MOD.lock_key_for(self.参数("vm"), "Win11_M7"), "vm-Win11_M7")

    def test_关闭加锁(self):
        self.assertIsNone(MOD.lock_key_for(self.参数("none"), "Win11_M7"))

    def test_显式锁名优先(self):
        self.assertEqual(
            MOD.lock_key_for(self.参数(key="69660101"), "Win11_M7"), "69660101"
        )

    def test_非法字符被收敛(self):
        self.assertEqual(MOD.lock_key_for(self.参数(key="a/b c"), "x"), "a_b_c")


class 日志命名测试(unittest.TestCase):
    def test_保留原路径(self):
        self.assertEqual(
            MOD.resolve_log(Path("/a/b.log"), "J1", "exact"), Path("/a/b.log")
        )

    def test_加任务后缀(self):
        self.assertEqual(
            MOD.resolve_log(Path("/a/b.log"), "J1", "unique").name, "b.J1.log"
        )

    def test_无后缀也加得上(self):
        self.assertEqual(
            MOD.resolve_log(Path("/a/noext"), "J1", "unique").name, "noext.J1"
        )

    def test_清空前留档(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "b.log"
            log.write_text("上一轮证据")
            MOD.archive_log(log, "J1")
            prev = Path(tmp) / "b.log.J1.prev"
            self.assertTrue(prev.exists())
            self.assertEqual(prev.read_text(), "上一轮证据")

    def test_空日志不留档(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "b.log"
            log.write_text("")
            MOD.archive_log(log, "J1")
            self.assertFalse((Path(tmp) / "b.log.J1.prev").exists())


class 并发锁测试(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.env = dict(
            os.environ,
            PEMB_HOME=str(self.home / "pemb"),
            PYTHONDONTWRITEBYTECODE="1",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def 收尾(self, p):
        if p.poll() is None:
            p.kill()
        p.wait()
        for stream in (p.stdout, p.stderr):
            try:
                stream.close()
            except Exception:
                pass

    def 持有(self, key="k", hold=8, job="holder"):
        p = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(BIN), key, str(hold), job],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.收尾, p)
        line = p.stdout.readline().strip()
        if line != "ACQUIRED":
            p.kill()
            self.fail("持有者未能取锁：%r / %s" % (line, p.stderr.read()))
        return p

    def 抢锁(self, key="k", timeout=0):
        r = subprocess.run(
            [sys.executable, "-c", WAITER, str(BIN), key, str(timeout)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return json.loads(r.stdout.strip().splitlines()[-1])

    def 状态(self, key=None):
        cmd = [sys.executable, str(BIN), "status"]
        if key:
            cmd += ["--key", key]
        r = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_锁被占用时取不到(self):
        self.持有(key="busy")
        d = self.抢锁(key="busy", timeout=0)
        self.assertFalse(d["acquired"])
        self.assertEqual(d["error"], "lock_timeout")

    def test_锁释放后可以取到(self):
        p = self.持有(key="free", hold=1)
        p.wait(timeout=20)
        d = self.抢锁(key="free", timeout=10)
        self.assertTrue(d["acquired"])

    def test_持有者崩溃后自动释放(self):
        p = self.持有(key="crash", hold=600)
        self.assertTrue(self.状态("crash")["locks"][0]["held"])
        p.kill()
        p.wait(timeout=20)
        state = self.状态("crash")["locks"][0]
        self.assertFalse(state["held"])
        self.assertTrue(state["stale_holder"])
        d = self.抢锁(key="crash", timeout=5)
        self.assertTrue(d["acquired"])

    def test_等待者进入队列且位置递增(self):
        self.持有(key="q", hold=600, job="holder-A")
        w = subprocess.Popen(
            [sys.executable, "-c", WAITER, str(BIN), "q", "30"],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.收尾, w)
        waiting = []
        for _ in range(40):
            waiting = self.状态("q")["locks"][0]["waiting"]
            if waiting:
                break
            time.sleep(0.1)
        self.assertTrue(waiting, "等待者未出现在队列中")
        self.assertEqual(waiting[0]["job_id"], "waiter")
        self.assertEqual(waiting[0]["position"], 0)

    def test_无锁时状态为空(self):
        self.assertEqual(self.状态()["locks"], [])

    def test_锁被占用时命令行退出码为2(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            bat = Path(tmp) / "x.bat"
            bat.write_bytes(b"@echo off\r\n")
            self.持有(key="clibusy", hold=600)
            r = subprocess.run(
                [
                    sys.executable, str(BIN), "run",
                    "--bat", str(bat), "--log", str(Path(tmp) / "x.log"),
                    "--marker", "DONE", "--transport", "stub",
                    "--lock-key", "clibusy", "--lock-timeout", "0",
                ],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("锁超时", json.loads(r.stdout)["error"])

    def test_干运行不创建锁目录(self):
        with tempfile.TemporaryDirectory(dir=str(Path.home())) as tmp:
            bat = Path(tmp) / "x.bat"
            bat.write_bytes(b"@echo off\r\n")
            r = subprocess.run(
                [
                    sys.executable, str(BIN), "run",
                    "--bat", str(bat), "--log", str(Path(tmp) / "x.log"),
                    "--marker", "DONE", "--transport", "stub", "--dry-run",
                ],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((self.home / "pemb" / "locks").exists())
            self.assertIn("wait lock", json.loads(r.stdout)["plan"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
