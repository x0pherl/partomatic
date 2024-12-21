# Partomatic

Partomatic is an attempt to build an automatable ecosystem for generating parametric models through automation -- making CI/CD automation possible for your 3d models.

# The Partomatic philosophy

Build123d is a powerful library, but it leaves the creation of final parts up to the developer. For a large project with many related and interlocking parts, this can make releasing a new version a project in and of itself.

[Partomatic](https://github.com/x0pherl/partomatic) enables _parametric modeling_ and standardizes some _build automation_ for a part.

## Parametric Modeling
Parametric 3D modeling is a method of creating 3D models where the geometry is defined by parameters, allowing for easy adjustment by simply changing the values of these parameters. This approach enables the creation of flexible and reusable designs that can be quickly adapted to different requirements.

## Build Automation

Build automation is a common practice in the software delivery world. Continuous Integration uses build automation to deliver software into testing and production environments whenever changes are checked in by a developer. Partomatic wraps additional information about how to name files and where to store them, so that an automated build script generate and save those parts.
