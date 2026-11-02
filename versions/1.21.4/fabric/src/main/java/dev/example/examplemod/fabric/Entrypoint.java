package dev.example.examplemod.fabric;

import dev.example.examplemod.TemplateMod;
import dev.example.examplemod.platform.RuntimePlatform;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;

public final class Entrypoint implements ModInitializer {
    public void onInitialize() {
        TemplateMod.initialize(new RuntimePlatform("fabric", FabricLoader.getInstance().getConfigDir()));
    }
}
