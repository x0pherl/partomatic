# PartomaticConfig

The first element of Partomatic is the PartomaticConfig class. Descending a class from PartomaticConfig allows you to define any parametric values for your design. It also allows for nesting objects hierarchically.

Partomatic also handles loading configuration data in a number of ways. One of these is through a YAML file. YAML was chosen over other configuration formats because it is reasonably easy for someone with no coding experience to read and modify a YAML file.

## Getting Started
The most simple implementation of a PartomaticConfig would just define a descendant class containing several fields. Imagine we had a part that was a wheel with a radius and a spindle_radius. It is important to annotate the type of each field for the dataclass functionality to work.

```python
from partomatic import PartomaticConfig

class WheelConfig(PartomaticConfig):
    depth: float = 10
    radius: float = 30
```

To instantiate a default Wheel config is simple:

```python
wheel_config = WheelConfig()
print (wheel_config.radius) # 30.0
```

## Defining Derived values

If you have many instances of code that require the diameter to be calculated, you may find that your code is littered with the fragment `wheel_config.radius * 2`. You could switch the field to the diameter instead, but then instead you'd have the same problem `wheel_config.diameter / 2`. You can easily solve this with a property. Let's see what that looks like and how to use it:

```python
from partomatic import PartomaticConfig

class WheelConfig(PartomaticConfig):
    depth: float = 10
    radius: float = 30

    @property #use the property annotation above the method
    def diameter(self) -> float:
        return self.radius * 2

wheel_config = WheelConfig()
print (wheel_config.diameter) # 60.0 - note that this behaves like a field rather than a method that would require parens: `wheel_config.diameter()`
```

## Nested Partomatic Configs

Now that we have the basic parameters of the wheel set, we might find we need to add a bearing. For something as simple as a bearing we could easily add the bearing properties within the WheelConfig class (e.g. `bearing_radius: float = 2.5`). However, most "simple" subcomponents eventually evolve into something that should be broken into its own class for clarity and portability.

```python
from partomatic import PartomaticConfig
from dataclasses import field

class BearingConfig(PartomaticConfig):
    radius: float = 10
    spindle_radius: float = 2
```

now that this is defined, we can add a BearingConfig within the wheel:

```python
class WheelConfig(PartomaticConfig):
    depth: float = 2
    radius: float = 50
    bearing: BearingConfig = field(default_factory=BearingConfig)
```

and call the bearing fields from within the Wheel

```python
wheel_config = WheelConfig()
print(wheel_config.bearing.radius) #10
print(wheel_config.radius) #50
```

### A note about fields & factories

Field factory functions are beyond the scope of this documentation, however the [*dataclass* documentation](https://docs.python.org/3/library/dataclasses.html#default-factory-functions) covers this thoroughly.

For PartomaticConfig, all you need to understand is that if you are nesting PartomaticConfig objects, you should follow this pattern when adding the sub-object to the base part:
`<object_name>: <ObjectClass> = field(default_factory=<ObjectClass>)`
Have a look again at the bearing field of the `WheelConfig` object above for an example.

## Putting it all together
```python
from partomatic import PartomaticConfig
from dataclasses import field

class BearingConfig(PartomaticConfig):
    radius: float = 10
    spindle_radius: float = 2

    @property
    def diameter(self) -> float:
        return self.radius * 2

class WheelConfig(PartomaticConfig):
    depth: float = 2
    radius: float = 50
    bearing: BearingConfig = field(default_factory=BearingConfig)

    @property
    def diameter(self) -> float:
        return self.radius * 2

wheel_config = WheelConfig()
print(wheel_config.bearing.diameter) #20
print(wheel_config.diameter) #100
```

## A note about Hierarchy and Derived Values

While you can nest PartomaticConfig objects, nested configs are not aware of their parents. This is intentionally not supported within PartomaticConfig to allow for part reuse. A PartomaticConfig class can be picked up and used inside of other models. The BearingConfig sits inside of a WheelConfig in our example, but it might equally be used in, say, a GeartrainConfig.

However, it is possible to use the __post_init__ method of the parent config in a PartomaticConfig hierarchy to properly set a value in the child (or parent) using values from both as follows:

```python
from partomatic import PartomaticConfig
from dataclasses import field

class ChildConfig(PartomaticConfig):
  component_value: float = 5
  derived_value: float = None

class ParentConfig(PartomaticConfig):
  parent_value: float = 20
  child: ChildConfig = field(default_factory=ChildConfig)
  
  def __post_init__(self):
    self.child.derived_value = self.parent_value/self.child.component_value

child = ChildConfig()
print(child.derived_value)
parent = ParentConfig()
print(parent.child.derived_value)

```

# Storing and setting data for PartomaticConfig objects

While defining default configuration values may be sufficient in many cases, the power of build123d is that it lets you build parametric designs. This allows you to modify the size and even the shape of an object without needing to modify the code. There are different ways to handle setting these parameters.

## Default Configuration

If you’re happy with the default values for your wheel configuration (and its bearing), or comfortable modifying the python files when needed, you simply instantiate the class as we've been doing in our examples so far:
`wheel_config = WheelConfig()`

### Instantiating with parameters passed

If you understand the correct parameters from elsewhere in your code, you could simply define each of those as kwargs and pass them to the definition as in this example:

```
bearing_config = BearingConfig(radius=20, spindle_radius=10)
wheel_config = WheelConfig(depth=5, radius=50, bearing=bearing_config)
```

## Instantiating by passing an existing config instance
```
wheel_config = WheelConfig()
...
back_wheel_config = WheelConfig(wheel_config)
```

When both a configuration input (file path, YAML string, or config object) and explicit keyword arguments are passed, keyword arguments take precedence for matching fields.

## Exporting Configuration Data

PartomaticConfig provides helper methods to serialize the current configuration:

1. as_dict(): returns a plain Python dictionary with enum values serialized by name.
2. to_yaml(root_node=None): returns a YAML string wrapped in the selected root node.
3. save_yaml(path, root_node=None): writes that YAML output to a file.

## Configuration Files

PartomaticConfig makes it easy to load parametric values from a YAML file -- you can even nest PartomaticConfig object definitions in a single YAML file.

YAML was chosen because YAML files are easily human-readable without deep technical knowledge. Our example is a simple model of a wheel with a cut in the center for a bearing. We’ll define both the wheel and the bearing. A simple example of a YAML configuration for a wheel with a bearing axle might look like:

```python
wheel:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
```

In our example, you might define multiple wheel parts to support different bearings sizes and add prefixes with the standard bearing names. Each of these configurations can be defined in a separate file, and we can use automation to process each of them.

### YAML node Names
If the top node of the child element in a YAML file matches the name of the class derived from PartomaticConfig, then Partomatic will make an attempt to identify the correct root node by searching in the following order:

1. a node matching the classname exactly, without eliminating the config name or changing the case. For example, a descendent class named `BearingConfig` would match the node `BearingConfig:`
2. a node matching the lowercase classname exactly, without eliminating the config name. For example, a descendent class named `BearingConfig` would match the node `bearingconfig:`
3. a node matching the classname, eliminating the string "Config" from the end of the classname. For example, a descendent class named `BearingConfig` would match the node `Bearing:`
4. a node matching the lowercase classname, eliminating the string "Config" from the end of the classname. For example, a descendent class named `BearingConfig` would match the node `bearing:`

If a matching node is not found, a ValueError is raised when loading the YAML.

### Example Implementation

Instantiating a Partomatic object from a YAML file is as simple as passing a filename to a valid YAML file as the only parameter:
`wheel_config = WheelConfig('~/wheel/config/base_wheel.yml')`


## Instantiating with a YAML string

If you’ve loaded a YAML string out of another object or from an environment variable, you can pass the entire YAML string instead of a filename as shown in this example:
```python
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

## Loading a nested YAML node
You may need to load a PartomaticConfig object that is nested within a larger YAML context, whether that's in a file or a string. In this example, the `wheel` object is defined within a `car` object, underneath of a `drivetrain` node. This can be loaded by using `yaml`’s `safe_load` method, and passing in the node paths as shown below:

```python
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

### Overriding a misnamed YAML node
PartomaticConfig’s attempts to resolve the node name based on the class name will not work when the name of the class and the key of the YAML file don't match. This example demonstrates how to "correct" the YAML node name so that your descendant class can load the file or string. In this case the "wheel" is described in the YAML string as a "pulley":

```python
wheel_yaml = """
pulley:
    depth: 10
    radius: 30
    bearing:
        radius: 4
        spindle_radius: 1.5
"""

wheel_config = WheelConfig(
            {"wheel": yaml.safe_load(wheel_yaml)["pulley"]}
        )
```
note that we had to define the dictionary ({}) with the key `wheel` `wheelconfig` or `WheelConfig` would also have worked.


# Other PartomaticConfig fields

The base PartomaticConfig object also declares the following fields:
```python
    stl_folder: str = "NONE"
    file_prefix: str = ""
    file_suffix: str = ""
    create_folders_if_missing: bool = True
```

### `stl_folder`
This defines the folder in which Partomatic STL files will be generated

### `file_prefix`
Your `Partomatic` object will generate one or more parts, and it defines file names for each part. The `file_prefix` allows you to define a prefix that will be added to each file when saving. This makes it possible to generate parts from multiple configurations in the same folder with easy to recognize names.

In our example, where we are defining multiple wheel parts to support different bearing sizes, we might add prefixes with the standard bearing names.

### `file_suffix`
This works the same way as `file_prefix` (described above), but adds this string to the end of each generated file.

### `create_folders_if_missing`
By default, Partomatic will create folders if they don’t exist when exporting stl files. If you prefer it to only save parts if the folders already exist, you set this to `False`


# Contributions & Credit

[jdegenstein](https://github.com/jdegenstein) asked questions about building derived values in PartomaticConfig - how a nested PartomaticConfig could read values from the parent config. The discussion led to the implentation of post_init and the section on hierarchy and derived values.