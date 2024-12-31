# PartomaticConfig

The first element of Partomatic is the PartomaticConfig class. Descending a class from PartomaticConfig allows you to define any parametric values for your design.

PartomaticConfig makes it easy to load parametric values from Python parameters passed on instantiation, or through a YAML file -- you can even nest PartomaticConfig object definitions in a single YAML file.

YAML was chosen because YAML files are easily human-readable without deep technical knowledge. As an example, imagine a simple model of a wheel with a cut in the center for a bearing. We’ll define both the wheel and the bearing. A simple example of a YAML configuration for a wheel with a bearing axle might look like:

```
wheel:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
```

## YAML node Names
Partomatic makes an attempt to identify the correct root node by searching in the following order:

1. a node matching the lowercase classname, eliminating the string "Config" from the end of the classname. For example, a descendent class named `BearingConfig` would match the node `bearing:`
2. a node matching the lowercase classname exactly, without eliminating the config name. For example, a descendent class named `BearingConfig` would match the node `bearingconfig:`
3. a node matching the classname exactly, without eliminating the config name or changing the case. For example, a descendent class named `BearingConfig` would match the node `BearingConfig:`

If a matching node is not found, a value error is raised when loading the yaml.

## Example Implementation

Now we can define PartomaticConfig objects for both the Wheel and the Bearing as follows:

```
from partomatic import PartomaticConfig
from dataclasses import field

class BearingConfig(PartomaticConfig):
    radius: float = 10
    spindle_radius: float = 2

class WheelConfig(PartomaticConfig):
    depth: float = 2
    radius: float = 50
    bearing: BearingConfig = field(default_factory=BearingConfig)
```

## field factory

Field factory functions are beyond the scope of this documentation, however the [*dataclass* documentation](https://docs.python.org/3/library/dataclasses.html#default-factory-functions) covers this thoroughly.

For PartomaticConfig, all you need to understand is that if you are nesting PartomaticConfig objects, you should follow this pattern when adding the sub-object to the base part:
`<object_name>: <ObjectClass> = field(default_factory=<ObjectClass>)`
Have a look again at the bearing field of the `WheelConfig` object for an example.

# Instantiating a PartomaticConfig descendant

Now that we’ve got the `WheelConfig` (and its member class `BearingConfig`) defined we need to create an instance of `WheelConfig`. We can instantiate this in several ways:
- default configuration
- loading from a file
- loading from a yaml string
- defining parameters

## Instantiating with default configuration

If you’re happy with the default values for your wheel configuration (and its bearing), it couldn’t be simpler to instantiate:
`wheel_config = WheelConfig()`

## Instantiating by loading from a file

Loading from a yaml file can make it easy to build multiple parts with different configurations.

In our example, you might define multiple wheel parts to support different bearings sizes and add prefixes with the standard bearing names. Each of these configurations can be defined in a separate file, and we can use automation to process each of them.

Instantiating a Partomatic object from a yaml file is as simple as passing a filename to a valid yaml file as the only parameter:
`wheel_config = WheelConfig('~/wheel/config/base_wheel.yml')`


## Instantiating with a yaml string

If you’ve loaded a yaml string out of another object or from an environment variable, you can pass the entire yaml string instead of a filename as shown in this example:
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

### Loading a nested yaml node
You may need to load a PartomaticConfig object that is nested within a larger YAML context. In this example, the `wheel` object is defined within a `car` object, underneath of a `drivetrain` node. This can be loaded by using `yaml`’s `safe_load` method, and passing in the node paths as shown below:

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

wheel_config = WheelConfig(
            {"wheel": yaml.safe_load(car_yaml)["car"]["drivetrain"]["wheel"]}
        )
```
note that in the instantiation, we had to define the dictionary ({}) with the key `wheel`.

### Overriding a misnamed yaml node
PartomaticConfig’s attempts to resolve the node name based on the class name may not always work. You can use a similar approach to the example above to "correct" the yaml node name so that your descendant class can load the file or string:

```
wheel_yaml = """
pulley:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
"""

wheel_config = WheelConfig(
            {"wheel": yaml.safe_load(car_yaml)["pulley"]}
        )
```
note that we had to define the dictionary ({}) with the key `wheel` `wheelconfig` or `WheelConfig` would also have worked.


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
By default, Partomatic will create folders if they don’t exist when exporting stl files. If you prefer it to only save parts if the folders already exist, you set this to `False`
