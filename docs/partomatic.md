# Partomatic

Partomatic is an [abstract base class](https://docs.python.org/3/library/abc.html) for creating automatable CAD components. There are 3 primary uses for Partomatic:
  - collecting user modifiable values into a centralized configuration for parametric modeling.
  - simplifying part generation for complex projects with multiple parts and configurations.
  - providing a web UI for configuring and downloading customized parts.

Partomatic automatically handles `__init__` and `load_config`. Overriding these methods is not recommended.

## Quick Start

A minimal Partomatic subclass requires only a `_config` class variable typed to your `PartomaticConfig` descendant, and a `compile` method:

```python
from build123d import BuildPart, Box
from partomatic import AutomatablePart, Partomatic, PartomaticConfig

class WidgetConfig(PartomaticConfig):
    stl_folder: str = "./stls"
    size: float = 20.0

class Widget(Partomatic):
    _config: WidgetConfig = WidgetConfig()

    def compile(self):
        self.parts.clear()
        with BuildPart() as body:
            Box(self._config.size, self._config.size, self._config.size)
        self.parts.append(
            AutomatablePart(
                body.part,
                "widget",
                stl_folder=self._config.stl_folder,
            )
        )

widget = Widget()
widget.partomate()  # compiles and exports STLs to ./stls/
```

## Defined Partomatic Variables

Partomatic defines two variables that your descendant classes will inherit:

```python
_config: PartomaticConfig
parts: list[AutomatablePart] = field(default_factory=list)
```

`_config` holds the parameters from a `PartomaticConfig` object. You must declare `_config` as a class variable in each subclass, typed to your own `PartomaticConfig` descendant:

```python
class Widget(Partomatic):
    _config: WidgetConfig = WidgetConfig()
```

`parts` is a list of `AutomatablePart` objects that `display`, `export_stls`, and `export_steps` operate on. Your `compile` method is responsible for populating it.

### Dirty tracking

Partomatic tracks whether `_config` has changed since the last successful `compile` via the `is_dirty` property. This is used internally by `launch_preview` and `launch_configurator` to avoid redundant recompiles, and is available for your own workflows:

```python
widget.is_dirty  # True if config changed since last compile
```

## Built-in Methods

### `load_config`

```python
foo.load_config(configuration=None, **kwargs)
```

Loads configuration into this instance. `configuration` may be a file path, a YAML string, an existing compatible config object, or `None` to use defaults. Keyword arguments override individual fields.

See the [PartomaticConfig](partomatic_config.md) documentation for full details on configuration loading.

### Abstract `compile` method

`compile` is the one method you **must** implement in every subclass. It is responsible for generating the 3D geometry and should always clear `self.parts` before repopulating it:

```python
def compile(self):
    self.parts.clear()
    self.parts.append(
        AutomatablePart(
            self.complete_wheel(),
            "complete-wheel",
            stl_folder=self._config.stl_folder,
        )
    )
```

After a successful `compile`, `is_dirty` will return `False` until `_config` changes again.

### `display`

```python
foo.display(viewer_host=None, viewer_port=None)
```

Displays each part in `self.parts` at its configured `display_location` in the OCP CAD viewer. `display` does **not** call `compile` — call `compile` first if the geometry may be stale.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `viewer_host` | `str` | `None` | Hostname of a standalone OCP viewer. Only used when `viewer_port` is also set. |
| `viewer_port` | `int` | `None` | Port of a standalone OCP viewer. When omitted, uses VS Code's default OCP integration. |

```python
foo.display(viewer_host="127.0.0.1", viewer_port=3939)
```

### `partomate`

```python
foo.partomate(export_steps=False)
```

Convenience method that calls `compile` then `export_stls`. Pass `export_steps=True` to also write STEP files.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `export_steps` | `bool` | `False` | When `True`, also exports STEP files after STLs. |

```python
foo.partomate(export_steps=True)
```

### `export_stls`

```python
paths = foo.export_stls()
```

Exports all parts in `self.parts` as STL files. The file path for each part is composed from:

- `self._config.stl_folder` (or the part's own `stl_folder`)
- `self._config.file_prefix`
- `AutomatablePart.file_name_base`
- `self._config.file_suffix`

> **Relative paths** for `stl_folder` are resolved relative to the directory containing your subclass file, not the current working directory.

> **Disabling exports:** set `stl_folder = "NONE"` in your config to skip all file writes (useful for testing or display-only workflows).

> **`file_prefix` and `file_suffix`:** these can be set in a configuration file to make alternate versions of components easy to idenityf.

If `create_folders_if_missing` is `False` and the target directory does not exist, the part is skipped. If `True` (default), missing directories are created automatically.

**Returns:** `list[Path]` — the paths of all files written.

### `export_steps`

```python
paths = foo.export_steps()
```

Identical to `export_stls`, but writes STEP files. Follows the same path resolution rules and returns `list[Path]`.

### `export_stls_to_directory` / `export_steps_to_directory`

```python
paths = foo.export_stls_to_directory(output_dir)
paths = foo.export_steps_to_directory(output_dir)
```

Export directly to an explicit directory without modifying your config. Useful for one-off or CI exports.

| Parameter | Type | Description |
|-----------|------|-------------|
| `output_dir` | `str \| Path` | Target directory for all exported files. |

```python
foo.export_stls_to_directory("/tmp/stls")
foo.export_steps_to_directory("/tmp/steps")
```

**Returns:** `list[Path]` — the paths of all files written.

### `launch_preview`

```python
foo.launch_preview(viewer_host="127.0.0.1", viewer_port=3939)
```

Starts (or connects to) a standalone OCP viewer, compiles the part, and pushes it to the viewer. **This call blocks until you press Ctrl+C.**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `viewer_host` | `str` | `"127.0.0.1"` | Hostname for the standalone OCP viewer. |
| `viewer_port` | `int` | `3939` | Port for the standalone OCP viewer. |

### `launch_configurator`

```python
foo.launch_configurator(
    host="localhost",
    port=8505,
    port_retries=10,
    viewer_host="127.0.0.1",
    viewer_port=3939,
    background=False,
)
```

Opens a combined NiceGUI web app with a live config editor and 3D preview side by side. **Requires the `webui` extra:**

```bash
pip install partomatic[webui]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | NiceGUI server host. |
| `port` | `int` | `8505` | Starting port. Incremented automatically if occupied. |
| `port_retries` | `int` | `10` | How many additional ports to try before failing. |
| `viewer_host` | `str` | `"127.0.0.1"` | OCP viewer host. |
| `viewer_port` | `int` | `3939` | OCP viewer port. |
| `background` | `bool` | `False` | When `True`, runs the UI server in a daemon thread and returns immediately. |

Key capabilities:

- Live validation of config fields
- YAML load and YAML download
- STL download
- STEP download when `enable_step_exports` is `True`

```python
foo.launch_configurator(host="localhost", port=8505, viewer_host="127.0.0.1", viewer_port=3939)
```

## Partomatic Logging

Partomatic logs to the `"partomatic"` namespace. Attach a handler to capture output:

```python
import logging
from sys import stdout

logger = logging.getLogger("partomatic")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))

foo = Widget()
foo._config.stl_folder = "NONE"  # disable file writes
foo.partomate()
```
