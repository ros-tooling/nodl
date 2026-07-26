# nodl_schema tests

## Unit tests

`test_schema.py` and `test_validator_cli.py` are pure unit tests — no ROS
environment or build step needed.

## CMake macro tests

`test_ament_nodl_install.py`, `test_register_executable.py`,
`test_register_component.py`, and `test_macro_rejection.py` test the
`ament_nodl_*()` CMake macros shipped by `nodl_schema`. They exercise the
macros via the `test_ament_nodl` jig package in `test_ws/`.

## Integration tests

`test_integration.py` tests include resolution through the real ament index.
It uses an embedded colcon workspace (`test_ws/`) that gets built automatically
by a session-scoped pytest fixture in `conftest.py`.

### How it works

1. `test_ws/` contains minimal ament_cmake packages that install `.nodl.yaml`
   files via `ament_nodl_install()`. No executables, no nodes — just YAML.
2. The `pytest-colcon-ws` plugin builds the workspace once per pytest session
   in a clean shell, sources the install, and provides the `test_ws_env`
   fixture (a `dict[str, str]` of environment variables).
3. The outer workspace is sourced as an underlay so `nodl_schema` (and its
   cmake macros) are available at build time. Clean-shell isolation prevents
   env leakage from the host.

### Prerequisites

- `pytest>=8` and [`pytest-colcon-ws`](https://github.com/alistair-english/pytest-colcon-ws)
  must be installed (handles workspace build, sourcing, and env capture).
- The outer workspace must be built (`nodl_schema` installed) so the test
  packages can `find_package(nodl_schema)` and validate at build time.
- `colcon` must be on `PATH`.
- `ROS_SETUP_PATH` env var should point to the base ROS `setup.bash`.

### Running

```bash
# From the workspace root - outer ws must be built first
pixi run python -m pytest src/nodl/nodl_schema/test/ -v
```

### Workspace layout

```
test_ws/
  COLCON_IGNORE            # Outer workspace ignores this
  src/
    test_ament_nodl/       # Exercises all three ament_nodl_*() macros
    nodl_fragment_a/       # Installs diagnostics.nodl.yaml, shared_base.nodl.yaml
    nodl_fragment_b/       # Installs sensors.nodl.yaml
```

`build/`, `install/`, and `log/` are gitignored.
