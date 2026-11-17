"""Historical command alias; all initialization now uses Python."""

import runpy

if __name__ == "__main__":
    runpy.run_module("setup_local", run_name="__main__")
