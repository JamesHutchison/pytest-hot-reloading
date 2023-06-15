# A PyTest Hot Reloading Plugin
A hot reloading pytest daemon, implemented as a plugin.

This uses the [jurigged](https://github.com/breuleux/jurigged) library to watch files.

If it takes less than 5 seconds to do all of the imports
necessary to run a unit test, then you probably don't need this.

The minimum Python version is 3.10

## Installation
Do not install in production code. This is exclusively for the developer environment.

pip: Add `pytest-hot-reloading` to your `dev-requirements.txt` file and `pip install -r dev-requirements.txt`
poetry: `poetry add --group=dev pytest-hot-reloading`

## Usage
Add the plugin to the pytest arguments. Example using pyproject.toml:
```toml
[tool.pytest.ini_options]
addopts = "-p pytest_hot_reloading.plugin"
```

When running pytest, the plugin will detect whether the daemon is running, and start it if is not.
Note that a pid file is created to track the pid.

Imports are not reran on subsequent runs, which can be a huge time saver.

Currently, if you want to debug, you will want to run the daemon manually with debugging.
This can easily be done in VS Code with the following launch profile:

```json
        {
            "name": "Pytest Daemon",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "justMyCode": false,
            "args": [
                "--daemon",
                //
                // everything below this is optional
                //
                "--daemon-port",
                "4852", // the default value
                "--daemon-watch-globs",
                "./*.py" // the default value
                // "./my-project/*.py:./some-thing-else/*.py",  // example of colon separated globs
                "--daemon-ignore-watch-globs",
                "./.venv/*" // this is the default value, also colon separated globs
            ]
        },
```

The only reason you would need to limit the watched files is because the jurigged library
opens every file it watches, so it can exhaust the open file limit if you have a lot of files.

If the daemon is already running and you run pytest with `--daemon`, then the old one will be stopped
and a new one will be started. Note that `pytest --daemon` is NOT how you run tests. It is only used to start
the daemon.

## Workarounds
Libraries that use mutated globals may need a workaround to work with this plugin. The preferred
route is to have the library update its code to not mutate globals in a test environment, or to
restore them after a test suite has ran. In some cases, that isn't possible, usually because
the person with the problem doesn't own the library and can't wait around for a fix.

To register a workaround, create a function that is decorated by the
`pytest_hot_reloading.workaround.register_workaround` decorator. It may optionally yield. If it does,
then code after the yield is executed after the test suite has ran.

Example:
```python
from pytest_hot_reloading.workaround import register_workaround

@register_workaround("my_library")
def my_library_workaround():
    import my_library

    yield

    my_library.some_global = BackToOriginalValue()
```

If you are a library author, you can disable any workarounds for your library by creating an empty
module `_clear_hot_reload_workarounds.py`. If this is successfully imported, then workarounds for
the given module will not be executed.

## Known Issues
- This is early alpha
- The jurigged library is not perfect and sometimes it gets in a bad state
- Some libraries were not written with hot reloading in mind, and will not work without some changes.
  There is going to be logic to work around other issues with other libraries, such as pytest-django's
  mutation of the settings module that runs every session, but it hasn't been implemented yet.

## Notes
- pytest-xdist will have its logic disabled, even if args are passed in to enable it
- pytest-django will not create test database suffixes for multiworker runs such as tox.
