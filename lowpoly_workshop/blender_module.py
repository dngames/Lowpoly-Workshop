#!/usr/bin/env python3
"""Run the kit's headless Blender scripts using the official bpy package.

Use a dedicated Python environment matching the selected bpy wheel. This launcher
supports only the CLI flags used by the Workshop pipeline, and rejects other
options. It is not a replacement for Blender's interactive command line.
"""
import os
import runpy
import sys
import traceback


def main():
    import bpy

    args = sys.argv[1:]
    if args == ["--version"]:
        print("Blender " + bpy.app.version_string)
        print("Python " + sys.version.split()[0] + "; official bpy module")
        return 0

    error_code = 1
    try:
        if not bpy.app.background:
            raise RuntimeError("The module must run in a background process")
        script = None
        factory = False
        threads = None
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--":
                break
            if arg in ("-b", "--background"):
                i += 1
            elif arg == "--factory-startup":
                factory = True
                i += 1
            elif arg in ("-t", "--threads"):
                threads = int(args[i + 1])
                if threads < 1:
                    raise ValueError("Thread count must be positive")
                i += 2
            elif arg == "--python-exit-code":
                error_code = int(args[i + 1])
                if not 1 <= error_code <= 255:
                    raise ValueError("An error exit code must be between 1 and 255")
                i += 2
            elif arg in ("-P", "--python"):
                if script is not None:
                    raise ValueError("Only one script is supported per process")
                script = args[i + 1]
                i += 2
            else:
                raise ValueError("Unsupported Blender launcher option: " + arg)
        if script is None:
            raise ValueError("Expected -P <script>")
        if factory:
            bpy.ops.wm.read_factory_settings(use_empty=False)
        if threads is not None:
            bpy.context.scene.render.threads_mode = 'FIXED'
            bpy.context.scene.render.threads = threads
        # Preserve '--' and its script arguments exactly as the kit expects.
        runpy.run_path(script, run_name="__main__")
        return 0
    except SystemExit as error:
        if error.code is None:
            return 0
        if isinstance(error.code, int):
            return error.code
        print(error.code, file=sys.stderr)
        return error_code
    except BaseException:
        traceback.print_exc()
        return error_code if 1 <= error_code <= 255 else 1


if __name__ == "__main__":
    status = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Each invocation is disposable, like Blender's own background executable.
    # Exit after the script finishes rather than invoking module finalizers in
    # the host interpreter. Render/export exceptions still return nonzero above.
    os._exit(status)
