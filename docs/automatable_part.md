# AutomatablePart

## Overview
AutomatablePart is a small wrapper around build123d’s Part class that adds some useful additional data for generating parts in an automated context. These variables are members of the AutomatablePart class:
```
    part: Part = field(default_factory=Part)
    display_location: Location = field(default_factory=Location)
    stl_folder: str = getcwd()
    _file_name_base: str = "partomatic"
```

## Explanation
<!-- `part` is simply a build123d `Part` object -->
`display_location` defines a build123d `Location` in which to display the object (this is useful combining multiple `AutomatablePart`s into a single Partomatic object, and will be covered below)
`stl_folder` defines the folder in which the part should be saved
`file_name_base` (there are getters and setters for the `_filename_base` variable) defines the base file name. Note that this base will likely be combined with prefixes and suffixes that describe the parametric configuration, so any extension that is passed will be automatically stripped off.

## Example

```
from build123d import Location, Part
from partomatic import AutomatablePart

wheel_part = Part()
wheel_automatable = AutomatablePart(
    wheel_part,
    "widget.stl",
    display_location=Location((100, 100, 100)),
    stl_folder="/tmp/test/folder",
)

```