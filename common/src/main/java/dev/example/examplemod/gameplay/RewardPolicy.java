package dev.example.examplemod.gameplay;

import dev.example.examplemod.config.ModConfig;

public final class RewardPolicy {
    private RewardPolicy() { }

    public static int rewardFor(ModConfig config, boolean eligible) {
        return config.enabled && eligible ? config.rewardAmount : 0;
    }
}
