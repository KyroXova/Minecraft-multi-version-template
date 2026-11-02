# Minecraft multi-version template

Shared Java core and isolated native loader build profiles.

This checkpoint contains 36 Minecraft release(s).

Run `python tools/kyro/template.py core` to build and test the shared foundation.

Latest target: 26.1; loaders: fabric, forge, neoforge.

Build explicitly with `python tools/kyro/template.py gradle "-Pmc=26.1" "-Ploader=fabric" build`.

Shared logic belongs in `common/`; adapters belong in `versions/`; pins belong in `properties/`; build behavior belongs in `build-logic/`.
