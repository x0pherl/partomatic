# Partomatic

Partomatic is an attempt to build an automatable ecosystem for generating parametric models through automation -- making CI/CD automation possible for your 3d models.

# The Partomatic philosophy

In the software world, CI/CD technologies are taken for granted. They allow large-scale distributed systems to deploy updates automatically and smoothly. These systems allow an automated flow that takes updated code submitted by a developer, executes tests & validations, and then automated global deployment. Without these technologies the internet as we know it could not operate.

3d Modeling tools are great at creating models, but they don’t make it easy to deploy, generate, and distribute multiple parts. Build123d is a powerful library, but it leaves the creation of final parts up to the developer.

For a large project with many related and interlocking parts, this can make releasing a new version a project in and of itself. Partomatic allows for those designs to be parametric. For example, a wheel might support many different bearings, or come in multiple diameters or thicknesses. Instead of hard coding the saving of each of those STL files, Partomatic allows you to define parameters and file-naming instructions to allow a relatively simple build script to read through multiple configuration files and save each of those STL files in a folder structure and file-naming standard that you define.

[Partomatic](https://github.com/x0pherl/partomatic) enables _parametric modeling_ and standardizes some _build automation_ for a part.

## Parametric Modeling
Parametric 3D modeling is a method of creating 3D models where the geometry is defined by parameters, allowing for easy adjustment by simply changing the values of these parameters. This approach enables the creation of flexible and reusable designs that can be quickly adapted to different requirements.

Using the partomatic library gives you built in support for loading parameters from YAML files -- YAML is a very human, readable format -- someone without any technology background can look at a yaml file that looks like:
```
wheel:
    radius: 20
    thickness: 4
    bearing:
        diameter: 5
        thickness: 4
```
and understand how this represents these related parts

## Partomatic Components
There are 3 primary components to the partomatic library:
- [AutomatablePart](automatable_part.md) — This dataclass represents a build123d part with augmentation to control the location of the part as well as the file name
- [PartomaticConfig](partomatic_config.md) — This dataclass handles loading parameters from yaml strings or files.
- [Partomatic](partomatic.md) — This is the base class for generating, displaying, and exporting 3d objects based on the parameters loaded in the _config member variable, which is a `PartomaticConfig` object.