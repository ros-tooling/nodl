# nodl_schema tests

## Unit tests

`test_schema.py` and `test_validator_cli.py` are pure unit tests — no ROS
environment or build step needed.

## Integration tests

`test_integration.py` tests include resolution through the real ament index.
It uses an embedded colcon workspace (`test_ws/`) that gets built automatically
by a session-scoped pytest fixture in `conftest.py`.

### How it works

1. `test_ws/` contains minimal ament_cmake packages that install `.nodl.yaml`
   files via `ament_nodl_install()`. No executables, no nodes — just YAML.
2. The `test_ws_env` fixture builds the workspace once per pytest session
   (skips if already up-to-date), sources the install, and returns a clean
   environment dict.
3. Outer workspace entries are stripped from `AMENT_PREFIX_PATH` so only the
   test packages and the base ROS install are visible.

### Prerequisites

- The outer workspace must be built (`ament_nodl` and `nodl_schema` installed)
  so the test packages can `find_package(ament_nodl)` and validate at build time.
- `colcon` must be on `PATH`.

### Running

```bash
# From the workspace root (e.g. lyrical_ws/)
pixi run bash -c 'source install/setup.bash && python3 -m pytest src/nodl/nodl_schema/test/ -v'
```

### Workspace layout

```
test_ws/
  COLCON_IGNORE            # Outer workspace ignores this
  src/
    nodl_fragment_a/       # Installs diagnostics.nodl.yaml, shared_base.nodl.yaml
    nodl_fragment_b/       # Installs sensors.nodl.yaml
```

`build/`, `install/`, and `log/` are gitignored.
