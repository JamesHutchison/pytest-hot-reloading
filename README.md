# A PyTest Hot Reloading Plugin
A hot reloading pytest daemon, implemented as a plugin.

This uses the [jurigged](https://github.com/breuleux/jurigged) library to watch files.

If it takes less than 5 seconds to do all of the imports
necessary to run a unit test, then you probably don't need this.

## Installation
TBD

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

## Known Issues
- This is early alpha
- The jurigged library is not perfect and sometimes it gets in a bad state
- Some libraries were not written with hot reloading in mind, and will not work without some changes.
  There is going to be logic to work around other issues with other libraries, such as pytest-django's
  mutation of the settings module that runs every session, but it hasn't been implemented yet.
