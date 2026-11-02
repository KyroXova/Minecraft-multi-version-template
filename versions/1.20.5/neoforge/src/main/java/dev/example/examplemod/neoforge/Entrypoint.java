package dev.example.examplemod.neoforge;

import dev.example.examplemod.TemplateMod;
import dev.example.examplemod.platform.RuntimePlatform;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.loading.FMLPaths;

@Mod(TemplateMod.MOD_ID)
public final class Entrypoint {
    public Entrypoint() {
        TemplateMod.initialize(new RuntimePlatform("neoforge", FMLPaths.CONFIGDIR.get()));
    }
}
