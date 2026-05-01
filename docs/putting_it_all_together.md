# Putting It All Together

This walkthrough builds a complete, runnable example using every major Partomatic feature. We'll model a simple **wheel with a bearing cutout** — the same part referenced throughout the rest of the docs — from config definition through interactive configurator.

## 1. Define the Configuration

Start by defining your `PartomaticConfig` descendant. Nested configs let you group logically related parameters:

```python
from dataclasses import field
from partomatic import PartomaticConfig

class BearingConfig(PartomaticConfig):
    radius: float = field(
        default=5.0,
        # the metadata of the field will control the UI functionality
        metadata={
            "kind": "float",
            "constraints": {"ge": 1.0, "le": 20.0},
            "step": 0.5,
            "description": "Bearing outer radius in mm",
        },
    )
    depth: float = field(
        default=4.0,
        metadata={
            "kind": "float",
            "constraints": {"ge": 1.0, "le": 30.0},
            "step": 0.5,
            "description": "Bearing seat depth in mm",
        },
    )

class WheelConfig(PartomaticConfig):
    stl_folder: str = "./stls"
    file_prefix: str = "wheel-"
    radius: float = field(
        default=30.0,
        metadata={
            "kind": "float",
            "constraints": {"ge": 5.0, "le": 150.0},
            "step": 1.0,
            "description": "Wheel outer radius in mm",
        },
    )
    depth: float = field(
        default=10.0,
        metadata={
            "kind": "float",
            "constraints": {"ge": 2.0, "le": 50.0},
            "step": 0.5,
            "description": "Wheel depth in mm",
        },
    )
    bearing: BearingConfig = field(default_factory=BearingConfig)

    @property
    def diameter(self) -> float:
        return self.radius * 2
```

## 2. Implement the Partomatic Subclass

Declare `_config` as a class variable typed to your config, then implement `compile`:

```python
from build123d import BuildPart, Cylinder, Location, Mode
from partomatic import AutomatablePart, Partomatic

class Wheel(Partomatic):
    _config: WheelConfig = WheelConfig()

    def _build_wheel(self):
        with BuildPart() as wheel:
            # Outer wheel body
            Cylinder(
                radius=self._config.radius,
                height=self._config.depth,
            )
            # Bearing seat cutout
            Cylinder(
                radius=self._config.bearing.radius,
                height=self._config.bearing.depth,
                mode=Mode.SUBTRACT,
            )
        return wheel.part

    def compile(self):
        self.parts.clear()
        # note that in this case we're only generating
        # a single part. call self.parts.append once for
        # each prt you want to generate
        self.parts.append(
            AutomatablePart(
                self._build_wheel(),
                "wheel",
                stl_folder=self._config.stl_folder,
            )
        )
```

## 3. Instantiate and Load Configuration

Partomatic accepts configuration in several ways. Using defaults:

```python
wheel = Wheel()
```

Overriding individual fields via kwargs:

```python
wheel = Wheel(radius=40.0, depth=12.0)
```

Loading from a YAML file:

```python
wheel = Wheel("path/to/wheel.yaml")
```

Where `wheel.yaml` might look like:

```yaml
wheel:
  stl_folder: ./output/stls
  radius: 40.0
  depth: 12.0
  bearing:
    radius: 6.0
    depth: 5.0
```

Reloading configuration at any time:

```python
wheel.load_config("path/to/other_wheel.yaml")
# or override a single field without touching the rest:
wheel.load_config(None, radius=50.0)
```

## 4. Compile and Display

Call `compile` explicitly when you want the geometry without exporting, then `display` to push it to the OCP viewer:

```python
wheel.compile()
wheel.display(viewer_host="127.0.0.1", viewer_port=3939)
```

`display` does not recompile automatically. If you change config values between calls, call `compile` again first. You can check `wheel.is_dirty` to guard this:

```python
wheel._config.radius = 45.0
if wheel.is_dirty:
    wheel.compile()
wheel.display()
```

## 5. Export Files

The simplest export flow — compile and write STLs in one call:

```python
wheel.partomate()
```

Include STEP files:

```python
wheel.partomate(export_steps=True)
```

Export to a specific directory without modifying your config (useful in build scripts):

```python
written = wheel.export_stls_to_directory("/tmp/release/stls")
for path in written:
    print(f"Wrote: {path}")
```

By default, `stl_folder` paths that are relative are resolved from the directory containing your subclass file. Set `stl_folder = "NONE"` to disable all file writes (handy in tests):

```python
wheel._config.stl_folder = "NONE"
wheel.partomate()  # compiles only, no files written
```

## 6. Add Logging

Attach a handler to the `"partomatic"` logger to see what's happening during compilation and export:

```python
import logging
from sys import stdout

logger = logging.getLogger("partomatic")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))
```

## 7. Interactive Preview

`launch_preview` is the fastest way to iterate on geometry. It compiles your part, opens (or connects to) a standalone OCP viewer, and blocks until you press Ctrl+C:

```python
wheel.launch_preview(viewer_host="127.0.0.1", viewer_port=3939)
```

## 8. Web Configurator

`launch_configurator` opens a browser-based UI with a live config editor and embedded 3D preview. First install the extra:

```bash
pip install partomatic[webui]
```

Then launch:

```python
wheel._config.enable_step_exports = True  # adds STEP download button
wheel.launch_configurator(
    host="localhost",
    port=8505,
    viewer_host="127.0.0.1",
    viewer_port=3939,
)
```

The configurator lets you tweak any config field and see the result re-rendered in the preview pane. You can download the current configuration as YAML, or export the compiled STL/STEP directly from the browser.

To embed the configurator inside a larger application without blocking, use `background=True`:

```python
wheel.launch_configurator(host="0.0.0.0", port=8505, background=True)
# execution continues here while the UI runs in a daemon thread
```

## Complete Example

Bringing it all together in a single file:

```python
import logging
from dataclasses import field
from sys import stdout

from build123d import BuildPart, Cylinder, Mode
from partomatic import AutomatablePart, Partomatic, PartomaticConfig


class BearingConfig(PartomaticConfig):
    radius: float = 5.0
    depth: float = 4.0


class WheelConfig(PartomaticConfig):
    stl_folder: str = "NONE"
    file_prefix: str = "wheel-"
    radius: float = 30.0
    depth: float = 10.0
    bearing: BearingConfig = field(default_factory=BearingConfig)

    @property
    def diameter(self) -> float:
        return self.radius * 2


class Wheel(Partomatic):
    _config: WheelConfig = WheelConfig()

    def _build_wheel(self):
        with BuildPart() as wheel:
            Cylinder(radius=self._config.radius, height=self._config.depth)
            Cylinder(
                radius=self._config.bearing.radius,
                height=self._config.bearing.depth,
                mode=Mode.SUBTRACT,
            )
        return wheel.part

    def compile(self):
        self.parts.clear()
        self.parts.append(
            AutomatablePart(self._build_wheel(), "wheel", stl_folder=self._config.stl_folder)
        )


if __name__ == "__main__":
    logging.getLogger("partomatic").addHandler(logging.StreamHandler(stdout))

    wheel = Wheel(radius=40.0, bearing=BearingConfig(radius=6.0))
    wheel.partomate()                                # compile + export STLs
    wheel.export_stls_to_directory("/tmp/stls")     # also copy to /tmp

    # Uncomment to launch the interactive configurator:
    # wheel.launch_configurator(host="localhost", port=8505)
```
