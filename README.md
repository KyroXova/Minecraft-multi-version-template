# Minecraft multi-version template

Shared Java core and isolated native loader build profiles.

This checkpoint contains 7 Minecraft release(s).

Run `python tools/kyro/template.py core` to build and test the shared foundation.

Latest target: 1.17; loaders: fabric.

Build explicitly with `python tools/kyro/template.py gradle "-Pmc=1.17" "-Ploader=fabric" build`.

Shared logic belongs in `common/`; adapters belong in `versions/`; pins belong in `properties/`; build behavior belongs in `build-logic/`.
