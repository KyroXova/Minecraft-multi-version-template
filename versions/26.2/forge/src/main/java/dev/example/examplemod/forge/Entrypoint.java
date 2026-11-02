package dev.example.examplemod.forge;

import dev.example.examplemod.TemplateMod;
import dev.example.examplemod.platform.RuntimePlatform;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;

@Mod(TemplateMod.MOD_ID)
public final class Entrypoint {
    public Entrypoint() {
        TemplateMod.initialize(new RuntimePlatform("forge", FMLPaths.CONFIGDIR.get()));
    }
}
