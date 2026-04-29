# Partomatic

Partomatic is an [abstract base class](https://docs.python.org/3/library/abc.html) for components within a larger project.

Partomatic automatically handles the `__init__` method as well as `load_config`. Overriding these methods is not recommended.

### Defined Partomatic Variables

Partomatic defines two important variables that you descendent classes will inherit:
```
    _config: PartomaticConfig
    parts: list[AutomatablePart] = field(default_factory=list)
```

`_config` stores the parameters from a PartomaticConfig object. `parts` is a list of AutomatableParts, which partomatic will display or export when the appropriate methods are called.

### Abstract `compile` method

Partomatic defines an abstract methods which must be defined within a descendent class.

This method is responsible for generating the 3d geometry for each component. It should clear the parts list and regenerate each element of your design as a AutomatablePart.

A simple example might look like this:

```
# ... Partomatic descendant class fragment

    def complete_wheel() -> Part:
        # <CODE TO GENERATE PART>

    def compile(self):
        """
        Builds the relevant parts for the filament wheel
        """
        self.parts.clear()
        self.parts.append(
            AutomatablePart(
                self.complete_wheel(),
                "complete-wheel",
                stl_folder=self._config.stl_folder,
            )
        )

```

### Partomatic built-in methods

#### `display`

The `display` method will display each AutomatablePart in the `parts` list in the appropriate display_location

You can target a standalone OCP endpoint by passing:

```python
foo.display(viewer_host="127.0.0.1", viewer_port=3939)
```

#### `export_stls`

 This method calculates the appropriate file path based on the descendant class’ `stl_folder`, `file_prefix`, the `AutomatablePart`’s `file_name_base` and the `file_prefix` and `file_suffix`. If `create_folders_if_missing` is set to False, no part will be saved if the folder is not present.

#### `export_steps`

This works the same way as `export_stls`, but writes STEP files instead of STL files.

#### `export_stls_to_directory` / `export_steps_to_directory`

These helper methods export directly to an explicit output directory without mutating your config.

```python
foo.export_stls_to_directory("/tmp/stls")
foo.export_steps_to_directory("/tmp/steps")
```

 #### `load_config`

 This method will load a configuration from file, kwargs, or a yaml string -- see the `PartomaticConfig` documentation for more details.

 #### `partomate`

 `partomate` is a convenience function that will execute the `compile` and `export_stls` functions of the Partomatic descendant.

If you want STEP exports in that flow, pass `export_steps=True`:

```python
foo.partomate(export_steps=True)
```

#### `launch_preview`

`launch_preview` starts/uses an OCP standalone viewer endpoint, compiles the part, and displays it. This call blocks until you press Ctrl+C.

```python
foo.launch_preview(viewer_host="127.0.0.1", viewer_port=3939)
```

#### `launch_configurator`

`launch_configurator` opens a combined NiceGUI app with both config editing and 3D preview in one page.

Key capabilities:
- live validation of config fields
- YAML load and YAML download
- STL download
- STEP download when `enable_step_exports` is true

```python
foo.launch_configurator(host="localhost", port=8505, viewer_host="127.0.0.1", viewer_port=3939)
```

### Partomatic logging

Partomatic logs to the "partomatic" namespace; you can capture and handle partomatic logs easily:

```
logger = logging.getLogger("partomatic")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))

foo = Wheel()
foo._config.stl_folder = "NONE"
foo.partomate()
```