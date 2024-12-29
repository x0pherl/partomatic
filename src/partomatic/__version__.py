import subprocess


def get_version():
    major = 0
    minor = 2
    # adjust the current_major_minor_build_value to the number of builds prior
    # to the current major and minor version
    # so that it will be automatically subtracted from the returned build number
    current_major_minor_build_value = 10
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            stdout=subprocess.PIPE,
            check=True,
        )
        build_number = result.stdout.decode("utf-8").strip()
    except Exception:
        build_number = "0"
    build_number = int(build_number) - current_major_minor_build_value
    return f"{major}.{minor}.{build_number}"


__version__ = get_version()
