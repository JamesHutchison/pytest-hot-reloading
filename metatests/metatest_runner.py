import argparse
import shutil
import tempfile
import time
from os import system
from pathlib import Path
from typing import Callable

METATESTS_DIR = Path(__file__).parent
TEMPLATE_DIR = METATESTS_DIR / "template"


class MetaTestRunner:
    def __init__(
        self,
        do_not_reset_daemon: bool,
        use_watchman: bool,
        change_delay: float,
        retries: int,
        temp_dir: Path,
    ) -> None:
        self.do_not_reset_daemon = do_not_reset_daemon
        self.use_watchman = use_watchman
        self.change_delay = change_delay
        self.retries = retries
        self.temp_dir = temp_dir
        self.modified_conftest_file = self.temp_dir / "conftest.py"
        self.modified_test_file = self.temp_dir / "test_fixture_changes.py"
        self.modified_used_by_conftest_file = self.temp_dir / "used_by_conftest.py"

    def make_fresh_copy(self):
        # delete the directory contents if it is not empty
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        shutil.copytree(TEMPLATE_DIR, self.temp_dir)
        with (self.temp_dir / ".gitignore").open("w") as gitignore:
            gitignore.write("*")

    def run_test(
        self,
        test_name: str,
        *file_mod_funcs: Callable,
        expect_fail: bool = False,
        use_watchman: bool = False,
        change_delay: float = 0.01,
        retries: int = 0,
    ):
        for retry_num in range(retries + 1):
            self.make_fresh_copy()
            if system(
                f"pytest -p pytest_hot_reloading.plugin --daemon-start-if-needed {'--daemon-use-watchman' if use_watchman else ''} "
                f"{self.temp_dir}/test_fixture_changes.py::test_always_ran"
            ):
                raise Exception("Failed to prep daemon")
            for func in file_mod_funcs:
                func()
            time.sleep(change_delay + retry_num * 0.25)
            try:
                if system(f"pytest {self.temp_dir}/test_fixture_changes.py::{test_name}"):
                    if not expect_fail:
                        raise Exception(f"Failed to run test {test_name}")
                elif expect_fail:
                    raise Exception(f"Expected test {test_name} to fail but it passed")
            except Exception:
                if retry_num >= retries:
                    raise
                else:
                    print("Retrying failed metatest")
            else:
                break

    def add_fixture(self) -> None:
        with self.modified_conftest_file.open("a") as f:
            f.write(
                """
@pytest.fixture()
def added_fixture():
    pass"""
            )

    def add_async_fixture(self) -> None:
        with self.modified_conftest_file.open("a") as f:
            f.write(
                """
@pytest.fixture()
async def async_added_fixture():
    pass"""
            )

    def remove_fixture(self, trigger_comment="# start of removed fixture") -> None:
        # remove the fixture from conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        new_lines = []
        is_removed_fixture = False
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == f"@pytest.fixture()  {trigger_comment}":
                is_removed_fixture = True
            elif not stripped_line:
                is_removed_fixture = False
            if not is_removed_fixture:
                new_lines.append(line)

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            f.writelines(new_lines)

    def remove_use_of_fixture(self, fixture_name="removed_fixture") -> None:
        # remove the fixture from test_fixture_changes.py
        with self.modified_test_file.open() as f:
            lines = f.readlines()

        with self.modified_test_file.open("w") as f:
            for line in lines:
                f.write(line.replace(f"({fixture_name})", "()"))

    def rename_fixture(self) -> None:
        # rename the fixture in conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            for line in lines:
                f.write(line.replace("renamed_fixture", "renamed_fixture2"))

    def rename_use_of_fixture(self) -> None:
        # rename the fixture in test_fixture_changes.py
        with self.modified_test_file.open() as f:
            lines = f.readlines()

        with self.modified_test_file.open("w") as f:
            for line in lines:
                f.write(line.replace("renamed_fixture", "renamed_fixture2"))

    def modify_dependency_fixture_return(self) -> None:
        # modify the dependency fixture in conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            for line in lines:
                f.write(
                    line.replace(
                        "return 1  # dependency value", "return 2222  # dependency value"
                    )
                )

    def modify_dependency_fixture_name(self) -> None:
        # modify the dependency fixture in conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            for line in lines:
                f.write(line.replace("dependency_fixture", "dependency_fixture2"))

    def remove_dependency_fixture(self) -> None:
        # remove the dependency fixture from conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        new_lines = []
        is_dependency_fixture = False
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "@pytest.fixture()  # start of dependency fixture":
                is_dependency_fixture = True
            elif not stripped_line:
                is_dependency_fixture = False
            if not is_dependency_fixture:
                new_lines.append(line)

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            f.writelines(new_lines)

    def remove_dependency_fixture_usage(self) -> None:
        # remove the dependency fixture from conftest.py
        with self.modified_conftest_file.open() as f:
            lines = f.readlines()

        # write new version of conftest.py
        with self.modified_conftest_file.open("w") as f:
            for line in lines:
                f.write(
                    line.replace(
                        "dependency_change_fixture(dependency_fixture)",
                        "dependency_change_fixture()",
                    ).replace(
                        "dependency_removed_fixture(dependency_fixture)",
                        "dependency_removed_fixture()",
                    )
                )

    def modify_fixture_outside_of_conftest(self) -> None:
        # modify the dependency fixture in conftest.py
        with self.modified_used_by_conftest_file.open() as f:
            lines = f.readlines()

        # write new version of used_by_conftest.py
        with self.modified_used_by_conftest_file.open("w") as f:
            for line in lines:
                f.write(
                    line.replace(
                        "return value_modified_by_autouse_fixture", "return 'modified value'"
                    )
                )

    def remove_autouse_fixture_outside_of_conftest(self) -> None:
        # remove the dependency fixture from conftest.py
        with self.modified_used_by_conftest_file.open() as f:
            lines = f.readlines()

        new_lines = []
        is_autouse_fixture = False
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "@pytest.fixture(autouse=True)":
                is_autouse_fixture = True
            elif not stripped_line:
                is_autouse_fixture = False
            if not is_autouse_fixture:
                new_lines.append(line)

        # write new version of conftest.py
        with self.modified_used_by_conftest_file.open("w") as f:
            f.writelines(new_lines)

    def main(self) -> None:
        if not self.do_not_reset_daemon:
            system("pytest --stop-daemon")
        if self.use_watchman:
            self.run_test("test_always_ran", use_watchman=True)
        self.run_test(
            "test_adding_fixture",
            self.add_fixture,
        )
        self.run_test(
            "test_adding_fixture_async",
            self.add_async_fixture,
        )
        self.run_test("test_removing_fixture")  # needed to trigger caching of fixture info
        self.run_test(
            "test_removing_fixture",
            self.remove_fixture,
            self.remove_use_of_fixture,
        )
        self.run_test(
            "test_removing_fixture_async",
            lambda: self.remove_fixture("# start of async removed fixture"),
            lambda: self.remove_use_of_fixture("async_removed_fixture"),
        )
        self.run_test(
            "test_removing_should_fail",
            self.remove_fixture,
            expect_fail=True,
        )
        self.run_test(
            "test_renaming_fixture",
            self.rename_fixture,
            self.rename_use_of_fixture,
        )
        self.run_test(
            "test_renaming_should_fail",
            self.rename_fixture,
            expect_fail=True,
        )
        self.run_test(
            "test_fixture_changes_dependency",
            self.modify_dependency_fixture_return,
        )
        self.run_test(
            "test_fixture_has_dependency_renamed",
            self.modify_dependency_fixture_name,
        )
        self.run_test(
            "test_fixture_has_dependency_removed",
            self.remove_dependency_fixture,
            expect_fail=True,
        )
        self.run_test(
            "test_fixture_removes_dependency",
            self.remove_dependency_fixture,
            self.remove_dependency_fixture_usage,
        )
        self.run_test("test_fixture_outside_of_conftest", expect_fail=True)
        self.run_test(
            "test_fixture_outside_of_conftest",
            self.modify_fixture_outside_of_conftest,
        )
        self.run_test(
            "test_autouse_fixture_outside_of_conftest_is_removed",
            self.remove_autouse_fixture_outside_of_conftest,
        )


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--do-not-reset-daemon", action="store_true")
    argparser.add_argument("--use-watchman", action="store_true")
    argparser.add_argument("--change-delay", default=0.01, type=float)
    argparser.add_argument("--retry", default=0, type=int)
    args = argparser.parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        runner = MetaTestRunner(
            args.do_not_reset_daemon,
            args.use_watchman,
            args.change_delay,
            args.retry,
            Path(temp_dir),
        )
        runner.main()
