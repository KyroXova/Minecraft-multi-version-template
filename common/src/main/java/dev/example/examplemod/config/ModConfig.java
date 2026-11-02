package dev.example.examplemod.config;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

public final class ModConfig {
    public boolean enabled = true;
    public int rewardAmount = 5;

    public static ModConfig load(Path directory) throws IOException {
        Files.createDirectories(directory);
        Path file = directory.resolve("examplemod.json");
        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        if (!Files.exists(file)) {
            ModConfig defaults = new ModConfig();
            Files.write(file, (gson.toJson(defaults) + "\n").getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            return defaults;
        }
        try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            ModConfig config = gson.fromJson(reader, ModConfig.class);
            if (config == null || config.rewardAmount < 0) {
                throw new IllegalArgumentException("Invalid examplemod.json: rewardAmount must be nonnegative");
            }
            return config;
        }
    }
}
