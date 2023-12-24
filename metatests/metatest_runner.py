import argparse
import shutil
import time
from os import system
from pathlib import Path
from typing import Callable

METATESTS_DIR = Path(__file__).parent
TEMP_DIR = METATESTS_DIR / "mtests"
TEMPLATE_DIR = METATESTS_DIR / "template"
MODIFIED_CONFTEST_FILE = TEMP_DIR / "conftest.py"
MODIFIED_TEST_FILE = TEMP_DIR / "test_fixture_changes.py"
MODIFIED_USED_BY_CONFTEST_FILE = TEMP_DIR / "used_by_conftest.py"


def make_fresh_copy():
    # delete the directory contents if it is not empty
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    shutil.copytree(TEMPLATE_DIR, TEMP_DIR)
    with (TEMP_DIR / ".gitignore").open("w") as gitignore:
        gitignore.write("*")


def run_test(test_name: str, *file_mod_funcs: Callable, expect_fail: bool = False):
    make_fresh_copy()
    if system(
        f"pytest --daemon-start-if-needed --daemon-use-watchman {TEMP_DIR}/test_fixture_changes.py::test_always_ran"
    ):
        raise Exception("Failed to prep daemon")
    for func in file_mod_funcs:
        func()
    if system(f"pytest {TEMP_DIR}/test_fixture_changes.py::{test_name}"):
        if not expect_fail:
            raise Exception(f"Failed to run test {test_name}")
    elif expect_fail:
        raise Exception(f"Expected test {test_name} to fail but it passed")


def add_fixture():
    with MODIFIED_CONFTEST_FILE.open("a") as f:
        f.write(
            """
@pytest.fixture()
def added_fixture():
    pass"""
        )


def add_async_fixture():
    with MODIFIED_CONFTEST_FILE.open("a") as f:
        f.write(
            """
@pytest.fixture()
async def async_added_fixture():
    pass"""
        )


def remove_fixture(trigger_comment="# start of removed fixture") -> None:
    # remove the fixture from conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
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
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        f.writelines(new_lines)


def remove_use_of_fixture(fixture_name="removed_fixture") -> None:
    # remove the fixture from test_fixture_changes.py
    with MODIFIED_TEST_FILE.open() as f:
        lines = f.readlines()

    with MODIFIED_TEST_FILE.open("w") as f:
        for line in lines:
            f.write(line.replace(f"({fixture_name})", "()"))


def rename_fixture() -> None:
    # rename the fixture in conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
        lines = f.readlines()

    # write new version of conftest.py
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        for line in lines:
            f.write(line.replace("renamed_fixture", "renamed_fixture2"))


def rename_use_of_fixture() -> None:
    # rename the fixture in test_fixture_changes.py
    with MODIFIED_TEST_FILE.open() as f:
        lines = f.readlines()

    with MODIFIED_TEST_FILE.open("w") as f:
        for line in lines:
            f.write(line.replace("renamed_fixture", "renamed_fixture2"))


def modify_dependency_fixture_return() -> None:
    # modify the dependency fixture in conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
        lines = f.readlines()

    # write new version of conftest.py
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        for line in lines:
            f.write(line.replace("return 1  # dependency value", "return 2  # dependency value"))


def modify_dependency_fixture_name() -> None:
    # modify the dependency fixture in conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
        lines = f.readlines()

    # write new version of conftest.py
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        for line in lines:
            f.write(line.replace("dependency_fixture", "dependency_fixture2"))


def remove_dependency_fixture() -> None:
    # remove the dependency fixture from conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
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
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        f.writelines(new_lines)


def remove_dependency_fixture_usage() -> None:
    # remove the dependency fixture from conftest.py
    with MODIFIED_CONFTEST_FILE.open() as f:
        lines = f.readlines()

    # write new version of conftest.py
    with MODIFIED_CONFTEST_FILE.open("w") as f:
        for line in lines:
            f.write(
                line.replace(
                    "dependency_change_fixture(dependency_fixture)", "dependency_change_fixture()"
                ).replace(
                    "dependency_removed_fixture(dependency_fixture)",
                    "dependency_removed_fixture()",
                )
            )


def modify_fixture_outside_of_conftest() -> None:
    # modify the dependency fixture in conftest.py
    with MODIFIED_USED_BY_CONFTEST_FILE.open() as f:
        lines = f.readlines()

    # write new version of used_by_conftest.py
    with MODIFIED_USED_BY_CONFTEST_FILE.open("w") as f:
        for line in lines:
            f.write(
                line.replace(
                    "return value_modified_by_autouse_fixture", "return 'modified value'"
                )
            )


def remove_autouse_fixture_outside_of_conftest() -> None:
    # remove the dependency fixture from conftest.py
    with MODIFIED_USED_BY_CONFTEST_FILE.open() as f:
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
    with MODIFIED_USED_BY_CONFTEST_FILE.open("w") as f:
        f.writelines(new_lines)


def main(do_not_reset_daemon: bool) -> None:
    if not do_not_reset_daemon:
        system("pytest --stop-daemon")
    run_test("test_adding_fixture", add_fixture)
    run_test("test_adding_fixture_async", add_async_fixture)
    run_test("test_removing_fixture")  # needed to trigger caching of fixture info
    run_test("test_removing_fixture", remove_fixture, remove_use_of_fixture)
    run_test(
        "test_removing_fixture_async",
        lambda: remove_fixture("# start of async removed fixture"),
        lambda: remove_use_of_fixture("async_removed_fixture"),
    )
    run_test("test_removing_should_fail", remove_fixture, expect_fail=True)
    run_test("test_renaming_fixture", rename_fixture, rename_use_of_fixture)
    run_test("test_renaming_should_fail", rename_fixture, expect_fail=True)
    run_test("test_fixture_changes_dependency", modify_dependency_fixture_return)
    run_test("test_fixture_has_dependency_renamed", modify_dependency_fixture_name)
    run_test("test_fixture_has_dependency_removed", remove_dependency_fixture, expect_fail=True)
    run_test(
        "test_fixture_removes_dependency",
        remove_dependency_fixture,
        remove_dependency_fixture_usage,
    )
    run_test("test_fixture_outside_of_conftest", expect_fail=True)
    run_test("test_fixture_outside_of_conftest", modify_fixture_outside_of_conftest)
    run_test(
        "test_autouse_fixture_outside_of_conftest_is_removed",
        remove_autouse_fixture_outside_of_conftest,
    )


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--do-not-reset-daemon", action="store_true")
    args = argparser.parse_args()
    main(args.do_not_reset_daemon)
