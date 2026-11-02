# Minecraft multi-version template

Shared Java core and isolated native loader build profiles.

This checkpoint contains 6 Minecraft release(s).

Run `python tools/kyro/template.py core` to build and test the shared foundation.

Latest target: 1.16.5; loaders: fabric, forge.

Build explicitly with `python tools/kyro/template.py gradle "-Pmc=1.16.5" "-Ploader=fabric" build`.

Shared logic belongs in `common/`; adapters belong in `versions/`; pins belong in `properties/`; build behavior belongs in `build-logic/`.
