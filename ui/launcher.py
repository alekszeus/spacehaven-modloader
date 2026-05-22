import os
import subprocess
import sys

import ui.log


def _launch_macos(path):
    """Launch Space Haven on macOS by invoking the bundled JRE directly.

    Using 'open spacehaven.app -W' delegates to the native launcher binary,
    which does not reliably pass -javaagent vmArgs to the JVM — particularly
    when the path contains spaces (e.g. 'Application Support').
    Falls back to 'open' if bundled JRE or config.json are missing.
    """
    import json as _json

    resources_dir = os.path.join(path, "Contents", "Resources") if path.endswith(".app") else os.path.dirname(path)
    config_path = os.path.join(resources_dir, "config.json")
    jre_java = os.path.join(resources_dir, "jre", "bin", "java")

    if not os.path.isfile(config_path) or not os.path.isfile(jre_java):
        ui.log.log("Direct JVM launch unavailable (missing config.json or jre/bin/java), falling back to 'open'")
        subprocess.call(["open", path, "-W"])
        return

    try:
        import io as _io
        with _io.open(config_path, "r", encoding="utf-8") as f:
            config = _json.load(f)
    except Exception as ex:
        ui.log.log("Could not read config.json ({}), falling back to 'open'".format(ex))
        subprocess.call(["open", path, "-W"])
        return

    vm_args = config.get("vmArgs", [])
    cp_list = config.get("classPath", [])
    main_cls = config.get("mainClass", "fi.bugbyte.spacehaven.steam.SpacehavenSteam")

    cp_resolved = []
    for entry in cp_list:
        cp_resolved.append(entry if os.path.isabs(entry) else os.path.join(resources_dir, entry))
    classpath = ":".join(cp_resolved)

    # The game's bundled JRE is Java 8; --add-opens is a Java 9+ module flag
    # that causes the JVM to refuse to start entirely.  Strip any such args
    # before invoking the bundled JRE — they are not needed for AspectJ on Java 8.
    vm_args_filtered = [a for a in vm_args if not (isinstance(a, str) and a.startswith("--add-opens"))]

    cmd = [jre_java] + vm_args_filtered + ["-cp", classpath, main_cls]
    ui.log.log("Launching game directly via bundled JRE (macOS)")
    ui.log.log("  JRE: {}".format(jre_java))
    ui.log.log("  vmArgs: {}".format(" ".join(str(a) for a in vm_args_filtered)))
    subprocess.call(cmd, cwd=resources_dir)


def launchAndWait(path):
    """Launch the game and wait for it to exit"""
    ui.log.updateBackgroundState("Running")

    # FIXME cloud credentials aren't found when launching from the modloader.
    # cwd issue ?? apparently not as the cwd doesnt change anything...
    from_dir = os.path.dirname(path)
    if sys.platform == "darwin":
        _launch_macos(path)
    else:
        subprocess.call([path], cwd=from_dir)


def open(path):
    """Open a path in an OS-native way"""

    if path is None:
        return

    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        # Can't use `open path` when path is inside a .app bundle — macOS
        # resolves up to the .app and launches the game instead of the folder.
        # AppleScript's `reveal` navigates inside bundles correctly.
        subprocess.call(["osascript", "-e", f'tell application "Finder" to reveal POSIX file "{path}"'])
        subprocess.call(["osascript", "-e", 'tell application "Finder" to activate'])
    else:
        subprocess.call(["xdg-open", path])
