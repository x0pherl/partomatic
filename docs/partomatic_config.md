# PartomaticConfig

The first element of Partomatic is the PartomaticConfig class. Descending a class from PartomaticConfig allows you to define any parametric values for your design.

PartomaticConfig makes it easy to load parametric values from Python parameters passed on instantiation, or through a YAML file -- you can even nest PartomaticConfig object definitions in a single YAML file.

YAML was chosen because YAML files are easily human-readable without deep technical knowledge. As an example, imagine a simple model of a wheel with a cut in the center for a bearing. We'll define both the wheel and the bearing. A simple example of a YAML configuration for a wheel with a bearing axle might look like:

```
wheel:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
```
Now we can define PartomaticConfig objects for both the Wheel and the Bearing as follows:

```
from partomatic import PartomaticConfig
from dataclasses import field

class BearingConfig(PartomaticConfig):
    yaml_tree: str = "wheel/bearing"
    radius: float = 10
    spindle_radius: float = 2

class WheelConfig(PartomaticConfig):
    yaml_tree = "wheel"
    depth: float = 2
    radius: float = 50
    bearing: BearingConfig = field(default_factory=BearingConfig)
```

You may have noted a few things that aren't obvious given the YAML section above. Let's take a deeper look at yaml_tree and the field definition for the bearing.

## yaml_tree

The value `yaml_tree` defines the tree of the configuration within a file that you would like to load. For our example, not that "wheel" is the root object of our yaml file because our first line reads `wheel:`.

Bearing is a sub element of that wheel object, because it is at the same indent level as `depth` and `radius`. Partomatic separates objects on the tree with the `/` character, so we define the bearing's `yaml_tree` as `wheel/bearing` so it could be loaded independently from the same file.

Note that the yaml tree of the sub object is not _required_ to follow this pattern. In our sample case it makes it easy to load a bearing object from the same file as the wheel if only the bearing is required for some python files within our project. `yaml_tree` can also be passed when initializing the BearingConfig object, so it could be overwritten if appropriate.

## field factory

Field factory functions are beyond the scope of this documentation, however the [*dataclass* documentation](https://docs.python.org/3/library/dataclasses.html#default-factory-functions) covers this thoroughly.

For PartomaticConfig, all you need to understand is that if you are nesting PartomaticConfig objects, you should follow this pattern when adding the sub-object to the base part:
`<object_name>: <ObjectClass> = field(default_factory=<ObjectClass>)`
Have a look again at the bearing field of the `WheelConfig` object for an example.

## Instantiating a PartomaticConfig descendant

Now that we've got the `WheelConfig` (and it's member class `BearingConfig`) defined we need to create an instance of `WheelConfig`. We can instantiate this in several ways:
- default configuration
- loading from a file
- loading from a yaml string
- defining parameters

### Instantiating with default configuration

If you're happy with the default values for your wheel configuration (and its bearing), it couldn't be simpler to instantiate:
`wheel_config = WheelConfig()`

### Instantiating by loading from a file

Loading from a yaml file can make it easy to build multiple parts with different configurations.

In our example, you might define multiple wheel parts to support different bearings sizes and add prefixes with the standard bearing names. Each of these configurations can be defined in a separate file, and we can use automation to process each of them.

Instantiating a Partomatic object from a yaml file is as simple as passing a filename to a valid yaml file as the only parameter:
`wheel_config = WheelConfig('~/wheel/config/base_wheel.yml')`


### Instantiating with a yaml string

If you've loaded a yaml string out of another object or from an environment variable, you can pass the entire yaml string instead of a filename as shown in this example:
```
wheel_yaml = """
wheel:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
"""
wheel_config = WheelConfig(wheel_yaml)
```

Remember that you can also load the object from anywhere in a `yaml_tree`; so if the `wheel` object is defined in a yaml tree for a parent object you could use that as follows:

```
car_yaml = """
car:
    <some car values>
    drivetrain:
        <some drivetrain values>
        wheel:
            depth: 10
            radius: 30
            bearing:
                radius: 4
                spindle_radius: 1.5
"""
wheel_config = WheelConfig(car_yaml, yaml_tree='car/drivetrain/wheel')
```

### Instantiating with parameters passed

If you understand the correct parameters from elsewhere in your code, you could simply define each of those as kwargs and pass them to the definition as in this example:

```
bearing_config = BearingConfig(radius=20, spindle_radius=10)
wheel_config = WheelConfig(depth=5, radius=50, bearing=bearing_config)
```

## Other PartomaticConfig fields

The base PartomaticConfig object also declares the following fields:
```
    stl_folder: str = "NONE"
    file_prefix: str = ""
    file_suffix: str = ""
    create_folders_if_missing: bool = True
```

### `stl_folder`
This defines the folder in which Partomatic STL files will be generated

### `file_prefix`
Your `Partomatic` object will generate one or more parts, and it defines file names for each part. The `file_prefix` allows you to define a prefix that will be added to each file when saving. This makes it possible to generate parts from multiple configurations in the same folder.

In our example, where we are defining multiple wheel parts to support different bearings sizes, we might add prefixes with the standard bearing names.

### `file_suffix`
This works the same way as `file_prefix` (described above), but adds this string to the end of each generated file.

### `create_folders_if_missing`
By default, Partomatic will create folders if they don't exist when exporting stl files. If you prefer it to only save parts if the folders already exist, you set this to `False`
