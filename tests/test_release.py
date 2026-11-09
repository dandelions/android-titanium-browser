import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_SCRIPT = REPO_ROOT / "release.sh"


class TestReleaseFilter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

        # Mock vanadium/args.gn
        vanadium_dir = self.work_dir / "vanadium"
        vanadium_dir.mkdir(parents=True, exist_ok=True)
        (vanadium_dir / "args.gn").write_text('android_default_version_name = "157.0.8103.38"\n')

        # Mock out/release dir
        self.release_dir = self.work_dir / "chromium" / "src" / "out" / "release"
        self.release_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy artifacts
        self.main_arm64 = self.release_dir / "157.0.8103.38-arm64-v8a.apk"
        self.main_arm = self.release_dir / "157.0.8103.38-armeabi-v7a.apk"
        self.lemur_arm64 = self.release_dir / "157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk"
        self.lemur_arm = self.release_dir / "157.0.8103.38-lemur-style-app-menu-armeabi-v7a.apk"

        self.main_arm64.write_text("main arm64 content")
        self.main_arm.write_text("main arm content")
        self.lemur_arm64.write_text("lemur arm64 content")
        self.lemur_arm.write_text("lemur arm content")

        # Mock git repo
        subprocess.run(["git", "init"], cwd=self.work_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.work_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.work_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=self.work_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.work_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/test/repo.git"], cwd=self.work_dir, check=True)

        # Mock gh executable that records calls to gh_log.txt
        self.bin_dir = self.work_dir / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.gh_log = self.work_dir / "gh_log.txt"
        gh_mock = self.bin_dir / "gh"
        gh_mock.write_text(f"""#!/bin/sh
echo "$@" >> "{self.gh_log}"
exit 0
""")
        gh_mock.chmod(0o755)

        # Copy release.sh
        self.script_copy = self.work_dir / "release.sh"
        shutil.copy(RELEASE_SCRIPT, self.script_copy)
        self.script_copy.chmod(0o755)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_release(self, args=None, env=None):
        test_env = os.environ.copy()
        test_env["PATH"] = f"{self.bin_dir}:{test_env['PATH']}"
        test_env["RELEASE_DIR"] = str(self.release_dir)
        test_env["SKIP_GIT_PUSH"] = "1"
        if env:
            test_env.update(env)
        cmd = [str(self.script_copy)] + (args or [])
        return subprocess.run(
            cmd,
            cwd=self.work_dir,
            env=test_env,
            capture_output=True,
            text=True,
        )

    def test_release_only_lemur_arm64_via_last_build_outputs(self):
        # Record only lemur 64-bit in .last_build_outputs
        marker = self.release_dir / ".last_build_outputs"
        marker.write_text("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk\n")

        res = self.run_release()
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-lemur-style-app-menu-armeabi-v7a.apk", res.stdout)

        # Verify gh upload calls
        gh_calls = self.gh_log.read_text()
        self.assertIn("upload v157.0.8103.38", gh_calls)
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", gh_calls)
        self.assertNotIn("157.0.8103.38-arm64-v8a.apk", gh_calls)

    def test_release_only_specified_file_arg(self):
        res = self.run_release(args=["157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk"])
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-arm64-v8a.apk", res.stdout)

        gh_calls = self.gh_log.read_text()
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", gh_calls)
        self.assertNotIn("157.0.8103.38-arm64-v8a.apk", gh_calls)

    def test_release_branch_filter_fallback(self):
        # Without .last_build_outputs, on branch lemur-style-app-menu with BUILD_ARM=0 BUILD_ARM64=1
        subprocess.run(["git", "checkout", "-b", "lemur-style-app-menu"], cwd=self.work_dir, check=True)
        res = self.run_release(env={"BUILD_ARM": "0", "BUILD_ARM64": "1"})
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-lemur-style-app-menu-armeabi-v7a.apk", res.stdout)

    def test_multi_branch_release_via_last_build_outputs(self):
        # When multiple branches were built, .last_build_outputs contains all of them
        marker = self.release_dir / ".last_build_outputs"
        marker.write_text("""157.0.8103.38-arm64-v8a.apk
157.0.8103.38-armeabi-v7a.apk
157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk
""")
        # Extra artifact from an unbuilt branch
        old_android = self.release_dir / "157.0.8103.38-old-android-arm64-v8a.apk"
        old_android.write_text("old android content")

        res = self.run_release()
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")
        self.assertIn("157.0.8103.38-arm64-v8a.apk", res.stdout)
        self.assertIn("157.0.8103.38-armeabi-v7a.apk", res.stdout)
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-old-android-arm64-v8a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-lemur-style-app-menu-armeabi-v7a.apk", res.stdout)

        # Verify .last_build_outputs was cleaned up after successful release
        self.assertFalse(marker.exists())

    def test_multi_branch_release_via_release_branches_env(self):
        # Without .last_build_outputs, specify RELEASE_BRANCHES for multi-branch release
        old_android = self.release_dir / "157.0.8103.38-old-android-arm64-v8a.apk"
        old_android.write_text("old android content")

        res = self.run_release(env={
            "RELEASE_BRANCHES": "main, lemur-style-app-menu",
            "BUILD_ARM": "1",
            "BUILD_ARM64": "1",
        })
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")
        self.assertIn("157.0.8103.38-arm64-v8a.apk", res.stdout)
        self.assertIn("157.0.8103.38-armeabi-v7a.apk", res.stdout)
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", res.stdout)
        self.assertIn("157.0.8103.38-lemur-style-app-menu-armeabi-v7a.apk", res.stdout)
        self.assertNotIn("157.0.8103.38-old-android-arm64-v8a.apk", res.stdout)

    def test_sha256_merging_preserves_untouched_branch_files(self):
        sha_file = self.release_dir / "157.0.8103.38-SHA256SUMS.txt"
        sha_file.write_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  157.0.8103.38-arm64-v8a.apk\n")

        res = self.run_release(args=["157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk"])
        self.assertEqual(res.returncode, 0, f"release.sh failed: {res.stderr}\n{res.stdout}")

        sha_content = sha_file.read_text()
        # Must preserve the untouched main file's checksum
        self.assertIn("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  157.0.8103.38-arm64-v8a.apk", sha_content)
        # Must include the new lemur file's checksum
        self.assertIn("157.0.8103.38-lemur-style-app-menu-arm64-v8a.apk", sha_content)


if __name__ == "__main__":
    unittest.main()
