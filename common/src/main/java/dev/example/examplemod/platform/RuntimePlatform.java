package dev.example.examplemod.platform;

import java.nio.file.Path;
import java.util.Objects;

public final class RuntimePlatform implements Platform {
    private final String loader;
    private final Path configDirectory;

    public RuntimePlatform(String loader, Path configDirectory) {
        this.loader = Objects.requireNonNull(loader);
        this.configDirectory = Objects.requireNonNull(configDirectory);
    }

    public String loader() { return loader; }
    public Path configDirectory() { return configDirectory; }
}
