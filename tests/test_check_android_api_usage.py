import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

API_XML = """<?xml version="1.0" encoding="utf-8"?>
<api version="4">
    <class name="android/view/MotionEvent" since="1">
        <extends name="android/view/InputEvent"/>
        <method name="getX(I)F"/>
        <method name="getRawX(I)F" since="29"/>
    </class>
    <class name="android/view/InputEvent" since="1">
        <extends name="java/lang/Object"/>
        <method name="getSource()I"/>
    </class>
    <class name="android/app/ActivityManager$TaskDescription$Builder" since="33">
        <extends name="java/lang/Object"/>
        <method name="build()Landroid/app/ActivityManager$TaskDescription;"/>
    </class>
    <class name="java/lang/Object" since="1">
        <method name="&lt;init>()V"/>
    </class>
</api>
"""


class ApiDatabaseTest(unittest.TestCase):
    def _db(self, tmpdir):
        from check_android_api_usage import ApiDatabase

        path = pathlib.Path(tmpdir) / "api-versions.xml"
        path.write_text(API_XML, encoding="utf-8")
        return ApiDatabase(str(path))

    def test_reports_api_level_of_late_members(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._db(tmpdir)
            self.assertEqual(db.method_since("android/view/MotionEvent", "getRawX", "(I)F"), 29)
            self.assertEqual(db.method_since("android/view/MotionEvent", "getX", "(I)F"), 1)
            self.assertEqual(
                db.method_since("android/app/ActivityManager$TaskDescription$Builder", "build",
                                "()Landroid/app/ActivityManager$TaskDescription;"), 33)

    def test_inherits_members_from_superclass_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._db(tmpdir)
            # getSource 声明在父类 InputEvent 上，子类引用也要能查到。
            self.assertEqual(db.method_since("android/view/MotionEvent", "getSource", "()I"), 1)

    def test_unknown_member_is_reported_as_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = self._db(tmpdir)
            self.assertIsNone(db.method_since("android/view/MotionEvent", "getNoSuchApi", "()V"))
            self.assertIsNone(db.method_since("com/example/App", "anything", "()V"))

    def test_rejects_non_dex_input(self):
        from check_android_api_usage import Dex

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "classes.dex"
            path.write_text("not a dex file", encoding="utf-8")
            with self.assertRaises(ValueError):
                Dex(str(path))


if __name__ == "__main__":
    unittest.main()
