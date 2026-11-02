package dev.example.examplemod;

import dev.example.examplemod.config.ModConfig;
import dev.example.examplemod.platform.Platform;
import java.io.IOException;
import java.util.logging.Logger;

public final class TemplateMod {
    public static final String MOD_ID = "examplemod";
    private static final Logger LOG = Logger.getLogger(MOD_ID);

    private TemplateMod() { }

    public static ModConfig initialize(Platform platform) {
        try {
            ModConfig config = ModConfig.load(platform.configDirectory());
            LOG.info("Example Mod initialized on " + platform.loader());
            return config;
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to load Example Mod configuration", exception);
        }
    }
}
