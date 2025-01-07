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

#### `export_stls`

 This method calculates the appropriate file path based on the descendant class’ `stl_folder`, `file_prefix`, the `AutomatablePart`’s `file_name_base` and the `file_prefix` and `file_suffix`. If `create_folders_if_missing` is set to False, no part will be saved if the file is not present.

 #### `load_config`

 This method will load a configuration from file, kwargs, or a yaml string -- see the `PartomaticConfig` documentation for more details.

 #### `partomate`

 `partomate` is a convenience function that will execute the `compile` and `export_stls` functions of the Partomatic descendant.

### Partomatic logging

Partomatic logs to the "partomatic" namespace; you can capture and handle partomatic logs easily:

```
logger = logging.getLogger("partomatic")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))

foo = Wheel()
foo._config.stl_folder = "NONE"
foo.partomate()```