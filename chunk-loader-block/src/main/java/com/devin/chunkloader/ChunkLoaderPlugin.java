package com.devin.chunkloader;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Chunk;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.block.CreatureSpawner;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.event.world.WorldUnloadEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.logging.Level;

public final class ChunkLoaderPlugin extends JavaPlugin implements Listener, CommandExecutor, TabCompleter {
    private static final String DATA_FILE_NAME = "loaders.yml";
    private static final String DATA_ROOT_PATH = "loaders";

    private final Map<String, Set<BlockKey>> loadersByWorld = new HashMap<>();
    private final Map<String, Set<Long>> activeChunkTicketsByWorld = new HashMap<>();
    private final Map<String, Integer> virtualSpawnerDelays = new HashMap<>();
    private final Random random = new Random();

    private NamespacedKey loaderItemKey;
    private Material loaderMaterial;
    private int chunkSize;
    private String displayName;
    private List<String> lore;
    private boolean notifyPlayer;
    private boolean logActions;

    private boolean spawnersEnabled;
    private long spawnerIntervalTicks;
    private boolean onlyWhenNoPlayerNearby;
    private int maxSpawnerSpawnsPerCycle;

    private boolean particlesEnabled;
    private Particle ambientParticle;
    private int ambientCount;
    private double ambientHeight;
    private double ambientOffset;
    private double ambientSpeed;
    private long ambientIntervalTicks;
    private boolean showBorders;
    private Particle borderParticle;
    private long borderIntervalTicks;
    private int borderStep;
    private double particlePlayerRadius;
    private boolean burstOnPlace;
    private boolean burstOnBreak;

    private boolean soundsEnabled;
    private Sound placeSound;
    private Sound breakSound;
    private float soundVolume;
    private float soundPitch;

    private File dataFile;
    private FileConfiguration dataConfig;
    private BukkitTask ambientTask;
    private BukkitTask borderTask;
    private BukkitTask spawnerTask;

    @Override
    public void onEnable() {
        loaderItemKey = new NamespacedKey(this, "chunk_loader_item");

        saveDefaultConfig();
        readConfigValues();
        prepareDataFile();
        loadLoadersFromDisk();

        getServer().getPluginManager().registerEvents(this, this);
        if (getCommand("chunkloader") != null) {
            getCommand("chunkloader").setExecutor(this);
            getCommand("chunkloader").setTabCompleter(this);
        } else {
            getLogger().severe("Команда 'chunkloader' отсутствует в plugin.yml");
        }

        Bukkit.getScheduler().runTask(this, new Runnable() {
            @Override
            public void run() {
                refreshChunkTickets();
            }
        });
        startParticleTasks();
        startSpawnerTask();

        getLogger().info("ChunkLoaderBlock включён. Материал=" + loaderMaterial + ", размер=" + chunkSize + "x" + chunkSize + ".");
    }

    @Override
    public void onDisable() {
        stopTasks();
        releaseAllChunkTickets();
        saveLoadersToDisk();
        virtualSpawnerDelays.clear();
    }

    private void readConfigValues() {
        FileConfiguration config = getConfig();

        String materialName = config.getString("loader-material", "LODESTONE");
        Material material = Material.matchMaterial(materialName == null ? "" : materialName.trim().toUpperCase());
        if (material == null || !material.isBlock()) {
            getLogger().warning("Неверный материал loader-material='" + materialName + "', использую LODESTONE.");
            material = Material.LODESTONE;
        }
        loaderMaterial = material;

        chunkSize = config.getInt("chunk-size", 8);
        if (chunkSize < 1) {
            getLogger().warning("chunk-size должен быть >= 1, получено " + chunkSize + ". Использую 8.");
            chunkSize = 8;
        }

        displayName = color(config.getString("display-name", "&bПрогружатель чанков &7[&a8x8&7]"));
        List<String> configuredLore = config.getStringList("lore");
        lore = new ArrayList<>(configuredLore.size());
        for (String line : configuredLore) {
            lore.add(color(line));
        }

        notifyPlayer = config.getBoolean("notify-player", true);
        logActions = config.getBoolean("log-actions", true);

        ConfigurationSection spawners = getOrCreateSection(config, "spawners");
        spawnersEnabled = spawners.getBoolean("enabled", true);
        spawnerIntervalTicks = Math.max(1L, spawners.getLong("interval-ticks", 20L));
        onlyWhenNoPlayerNearby = spawners.getBoolean("only-when-no-player-nearby", true);
        maxSpawnerSpawnsPerCycle = Math.max(1, spawners.getInt("max-spawns-per-cycle", 64));

        ConfigurationSection particles = getOrCreateSection(config, "particles");
        particlesEnabled = particles.getBoolean("enabled", true);
        ambientParticle = parseParticle(particles.getString("type", "END_ROD"), Particle.END_ROD);
        ambientCount = Math.max(1, particles.getInt("count", 6));
        ambientHeight = Math.max(0.0D, particles.getDouble("height", 1.5D));
        ambientOffset = Math.max(0.0D, particles.getDouble("offset", 0.25D));
        ambientSpeed = Math.max(0.0D, particles.getDouble("speed", 0.02D));
        ambientIntervalTicks = Math.max(1L, particles.getLong("interval-ticks", 10L));
        showBorders = particles.getBoolean("show-borders", true);
        borderParticle = parseParticle(particles.getString("border-type", "COMPOSTER"), Particle.COMPOSTER);
        borderIntervalTicks = Math.max(1L, particles.getLong("border-interval-ticks", 40L));
        borderStep = Math.max(1, particles.getInt("border-step", 8));
        particlePlayerRadius = Math.max(0.0D, particles.getDouble("player-radius", 96.0D));
        burstOnPlace = particles.getBoolean("burst-on-place", true);
        burstOnBreak = particles.getBoolean("burst-on-break", true);

        ConfigurationSection sounds = getOrCreateSection(config, "sounds");
        soundsEnabled = sounds.getBoolean("enabled", true);
        placeSound = parseSound(sounds.getString("on-place", "BLOCK_BEACON_ACTIVATE"), Sound.BLOCK_BEACON_ACTIVATE);
        breakSound = parseSound(sounds.getString("on-break", "BLOCK_BEACON_DEACTIVATE"), Sound.BLOCK_BEACON_DEACTIVATE);
        soundVolume = (float) sounds.getDouble("volume", 0.7D);
        soundPitch = (float) sounds.getDouble("pitch", 1.2D);
    }

    private ConfigurationSection getOrCreateSection(FileConfiguration config, String path) {
        ConfigurationSection section = config.getConfigurationSection(path);
        if (section == null) {
            section = config.createSection(path);
        }
        return section;
    }

    private Particle parseParticle(String value, Particle fallback) {
        if (value == null || value.trim().isEmpty()) {
            return fallback;
        }
        try {
            return Particle.valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            getLogger().warning("Неизвестная частица '" + value + "', использую " + fallback.name() + ".");
            return fallback;
        }
    }

    private Sound parseSound(String value, Sound fallback) {
        if (value == null || value.trim().isEmpty()) {
            return fallback;
        }
        try {
            return Sound.valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            getLogger().warning("Неизвестный звук '" + value + "', использую " + fallback.name() + ".");
            return fallback;
        }
    }

    private void prepareDataFile() {
        File dataFolder = getDataFolder();
        if (!dataFolder.exists() && !dataFolder.mkdirs()) {
            getLogger().severe("Не удалось создать папку плагина: " + dataFolder);
        }

        dataFile = new File(dataFolder, DATA_FILE_NAME);
        if (!dataFile.exists()) {
            try {
                if (!dataFile.createNewFile()) {
                    getLogger().warning("Файл данных уже существует, продолжаю.");
                }
            } catch (IOException ex) {
                getLogger().log(Level.SEVERE, "Не удалось создать файл данных " + dataFile, ex);
            }
        }
        dataConfig = YamlConfiguration.loadConfiguration(dataFile);
    }

    private void loadLoadersFromDisk() {
        loadersByWorld.clear();
        if (dataConfig == null || !dataConfig.isConfigurationSection(DATA_ROOT_PATH)) {
            return;
        }

        ConfigurationSection root = dataConfig.getConfigurationSection(DATA_ROOT_PATH);
        if (root == null) {
            return;
        }

        for (String worldName : root.getKeys(false)) {
            List<String> entries = dataConfig.getStringList(DATA_ROOT_PATH + "." + worldName);
            Set<BlockKey> keys = new LinkedHashSet<>();
            for (String entry : entries) {
                BlockKey key = BlockKey.parse(entry);
                if (key != null) {
                    keys.add(key);
                } else {
                    getLogger().warning("Пропускаю некорректную запись прогружателя: " + worldName + ":" + entry);
                }
            }
            if (!keys.isEmpty()) {
                loadersByWorld.put(worldName, keys);
            }
        }
    }

    private void saveLoadersToDisk() {
        if (dataConfig == null || dataFile == null) {
            return;
        }

        dataConfig.set(DATA_ROOT_PATH, null);
        for (Map.Entry<String, Set<BlockKey>> entry : loadersByWorld.entrySet()) {
            List<String> serialized = new ArrayList<>();
            for (BlockKey key : entry.getValue()) {
                serialized.add(key.toStorageString());
            }
            Collections.sort(serialized);
            dataConfig.set(DATA_ROOT_PATH + "." + entry.getKey(), serialized);
        }

        try {
            dataConfig.save(dataFile);
        } catch (IOException ex) {
            getLogger().log(Level.SEVERE, "Не удалось сохранить " + dataFile, ex);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        if (!isLoaderItem(event.getItemInHand())) {
            return;
        }

        Player player = event.getPlayer();
        if (!player.hasPermission("chunkloader.place")) {
            player.sendMessage(ChatColor.RED + "У вас нет прав на установку прогружателя чанков.");
            event.setCancelled(true);
            event.setBuild(false);
            return;
        }

        Block block = event.getBlockPlaced();
        if (block.getType() != loaderMaterial) {
            return;
        }

        if (registerLoader(block)) {
            refreshChunkTickets();
            saveLoadersToDisk();
            emitPlaceEffect(block);
            playSound(block, placeSound);

            int loadedChunks = countClaimedChunks(block.getWorld().getName());
            if (notifyPlayer) {
                player.sendMessage(ChatColor.AQUA + "Прогружатель чанков установлен. "
                        + ChatColor.GRAY + "Загружено " + ChatColor.GREEN + loadedChunks
                        + ChatColor.GRAY + " чанков в этом мире.");
            }
            if (logActions) {
                getLogger().info("Установлен прогружатель в " + describeBlock(block) + " игроком " + player.getName() + ".");
            }
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        Block block = event.getBlock();
        if (!isRegisteredLoader(block)) {
            return;
        }

        Player player = event.getPlayer();
        if (!player.hasPermission("chunkloader.break")) {
            player.sendMessage(ChatColor.RED + "У вас нет прав ломать прогружатель чанков.");
            event.setCancelled(true);
            return;
        }

        unregisterLoader(block);
        refreshChunkTickets();
        saveLoadersToDisk();
        emitBreakEffect(block);
        playSound(block, breakSound);
        event.setDropItems(false);
        if (player.getGameMode() != GameMode.CREATIVE) {
            block.getWorld().dropItemNaturally(block.getLocation().add(0.5D, 0.5D, 0.5D), createLoaderItem(1));
        }

        if (notifyPlayer) {
            player.sendMessage(ChatColor.AQUA + "Прогружатель чанков сломан. "
                    + ChatColor.GRAY + "Активных чанков в этом мире осталось: "
                    + ChatColor.YELLOW + countClaimedChunks(block.getWorld().getName()) + ChatColor.GRAY + ".");
        }
        if (logActions) {
            getLogger().info("Сломан прогружатель в " + describeBlock(block) + " игроком " + player.getName() + ".");
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        unregisterExplodedLoaders(event.blockList());
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        unregisterExplodedLoaders(event.blockList());
    }

    @EventHandler
    public void onWorldLoad(WorldLoadEvent event) {
        if (loadersByWorld.containsKey(event.getWorld().getName())) {
            refreshChunkTickets();
        }
    }

    @EventHandler
    public void onWorldUnload(WorldUnloadEvent event) {
        activeChunkTicketsByWorld.remove(event.getWorld().getName());
        virtualSpawnerDelays.keySet().removeIf(new java.util.function.Predicate<String>() {
            @Override
            public boolean test(String key) {
                return key.startsWith(event.getWorld().getName() + ":");
            }
        });
    }

    private void unregisterExplodedLoaders(List<Block> blocks) {
        boolean changed = false;
        for (Block block : blocks) {
            if (isRegisteredLoader(block)) {
                unregisterLoader(block);
                changed = true;
                if (logActions) {
                    getLogger().info("Прогружатель удалён взрывом в " + describeBlock(block) + ".");
                }
            }
        }
        if (changed) {
            refreshChunkTickets();
            saveLoadersToDisk();
        }
    }

    private boolean registerLoader(Block block) {
        String worldName = block.getWorld().getName();
        Set<BlockKey> loaders = loadersByWorld.get(worldName);
        if (loaders == null) {
            loaders = new LinkedHashSet<>();
            loadersByWorld.put(worldName, loaders);
        }
        return loaders.add(BlockKey.from(block));
    }

    private boolean unregisterLoader(Block block) {
        String worldName = block.getWorld().getName();
        Set<BlockKey> loaders = loadersByWorld.get(worldName);
        if (loaders == null) {
            return false;
        }
        boolean removed = loaders.remove(BlockKey.from(block));
        if (loaders.isEmpty()) {
            loadersByWorld.remove(worldName);
        }
        virtualSpawnerDelays.clear();
        return removed;
    }

    private boolean isRegisteredLoader(Block block) {
        Set<BlockKey> loaders = loadersByWorld.get(block.getWorld().getName());
        return loaders != null && loaders.contains(BlockKey.from(block));
    }

    private void refreshChunkTickets() {
        Map<String, Set<Long>> desired = computeDesiredChunkTickets();
        Set<String> worldNames = new HashSet<>();
        worldNames.addAll(activeChunkTicketsByWorld.keySet());
        worldNames.addAll(desired.keySet());

        for (String worldName : worldNames) {
            World world = Bukkit.getWorld(worldName);
            if (world == null) {
                continue;
            }

            Set<Long> active = activeChunkTicketsByWorld.get(worldName);
            if (active == null) {
                active = Collections.emptySet();
            }
            Set<Long> wanted = desired.get(worldName);
            if (wanted == null) {
                wanted = Collections.emptySet();
            }

            for (Long chunkKey : new ArrayList<>(active)) {
                if (!wanted.contains(chunkKey)) {
                    world.removePluginChunkTicket(unpackChunkX(chunkKey), unpackChunkZ(chunkKey), this);
                }
            }

            for (Long chunkKey : wanted) {
                if (!active.contains(chunkKey)) {
                    int chunkX = unpackChunkX(chunkKey);
                    int chunkZ = unpackChunkZ(chunkKey);
                    world.addPluginChunkTicket(chunkX, chunkZ, this);
                    if (!world.isChunkLoaded(chunkX, chunkZ)) {
                        world.loadChunk(chunkX, chunkZ);
                    }
                }
            }

            if (wanted.isEmpty()) {
                activeChunkTicketsByWorld.remove(worldName);
            } else {
                activeChunkTicketsByWorld.put(worldName, new LinkedHashSet<>(wanted));
            }
        }
    }

    private void releaseAllChunkTickets() {
        for (Map.Entry<String, Set<Long>> entry : new HashMap<>(activeChunkTicketsByWorld).entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) {
                continue;
            }
            for (Long chunkKey : entry.getValue()) {
                world.removePluginChunkTicket(unpackChunkX(chunkKey), unpackChunkZ(chunkKey), this);
            }
        }
        activeChunkTicketsByWorld.clear();
    }

    private Map<String, Set<Long>> computeDesiredChunkTickets() {
        Map<String, Set<Long>> desired = new HashMap<>();
        for (Map.Entry<String, Set<BlockKey>> entry : loadersByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) {
                continue;
            }

            Set<Long> chunks = new LinkedHashSet<>();
            for (BlockKey loader : entry.getValue()) {
                int centerChunkX = blockToChunk(loader.x);
                int centerChunkZ = blockToChunk(loader.z);
                addLoaderChunkSquare(chunks, centerChunkX, centerChunkZ);
            }
            if (!chunks.isEmpty()) {
                desired.put(world.getName(), chunks);
            }
        }
        return desired;
    }

    private void addLoaderChunkSquare(Set<Long> chunks, int centerChunkX, int centerChunkZ) {
        int half = chunkSize / 2;
        int startX = centerChunkX - half;
        int startZ = centerChunkZ - half;
        int endX = startX + chunkSize;
        int endZ = startZ + chunkSize;

        for (int chunkX = startX; chunkX < endX; chunkX++) {
            for (int chunkZ = startZ; chunkZ < endZ; chunkZ++) {
                chunks.add(packChunkKey(chunkX, chunkZ));
            }
        }
    }

    private int countClaimedChunks(String worldName) {
        Set<Long> chunks = computeDesiredChunkTickets().get(worldName);
        return chunks == null ? 0 : chunks.size();
    }

    private void startParticleTasks() {
        stopParticleTasks();
        if (!particlesEnabled) {
            return;
        }

        ambientTask = Bukkit.getScheduler().runTaskTimer(this, new Runnable() {
            @Override
            public void run() {
                emitAmbientParticles();
            }
        }, ambientIntervalTicks, ambientIntervalTicks);

        if (showBorders) {
            borderTask = Bukkit.getScheduler().runTaskTimer(this, new Runnable() {
                @Override
                public void run() {
                    emitBorderParticles();
                }
            }, borderIntervalTicks, borderIntervalTicks);
        }
    }

    private void stopParticleTasks() {
        if (ambientTask != null) {
            ambientTask.cancel();
            ambientTask = null;
        }
        if (borderTask != null) {
            borderTask.cancel();
            borderTask = null;
        }
    }

    private void startSpawnerTask() {
        stopSpawnerTask();
        if (!spawnersEnabled) {
            return;
        }

        spawnerTask = Bukkit.getScheduler().runTaskTimer(this, new Runnable() {
            @Override
            public void run() {
                tickVirtualSpawners();
            }
        }, spawnerIntervalTicks, spawnerIntervalTicks);
    }

    private void stopSpawnerTask() {
        if (spawnerTask != null) {
            spawnerTask.cancel();
            spawnerTask = null;
        }
    }

    private void stopTasks() {
        stopParticleTasks();
        stopSpawnerTask();
    }

    private void emitAmbientParticles() {
        forEachLoaderBlock(new LoaderBlockConsumer() {
            @Override
            public void accept(Block block) {
                if (!hasParticleViewer(block.getLocation())) {
                    return;
                }
                Location location = block.getLocation().add(0.5D, ambientHeight, 0.5D);
                block.getWorld().spawnParticle(ambientParticle, location, ambientCount, ambientOffset, ambientOffset, ambientOffset, ambientSpeed);
            }
        });
    }

    private void emitBorderParticles() {
        forEachLoaderBlock(new LoaderBlockConsumer() {
            @Override
            public void accept(Block block) {
                if (!hasParticleViewer(block.getLocation())) {
                    return;
                }
                spawnBorder(block);
            }
        });
    }

    private void spawnBorder(Block block) {
        World world = block.getWorld();
        int centerChunkX = blockToChunk(block.getX());
        int centerChunkZ = blockToChunk(block.getZ());
        int half = chunkSize / 2;
        int startChunkX = centerChunkX - half;
        int startChunkZ = centerChunkZ - half;
        int endChunkX = startChunkX + chunkSize;
        int endChunkZ = startChunkZ + chunkSize;

        int minX = startChunkX << 4;
        int minZ = startChunkZ << 4;
        int maxX = (endChunkX << 4) - 1;
        int maxZ = (endChunkZ << 4) - 1;
        double y = block.getY() + 1.05D;

        for (int x = minX; x <= maxX; x += borderStep) {
            world.spawnParticle(borderParticle, new Location(world, x + 0.5D, y, minZ + 0.5D), 1, 0.0D, 0.0D, 0.0D, 0.0D);
            world.spawnParticle(borderParticle, new Location(world, x + 0.5D, y, maxZ + 0.5D), 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
        for (int z = minZ; z <= maxZ; z += borderStep) {
            world.spawnParticle(borderParticle, new Location(world, minX + 0.5D, y, z + 0.5D), 1, 0.0D, 0.0D, 0.0D, 0.0D);
            world.spawnParticle(borderParticle, new Location(world, maxX + 0.5D, y, z + 0.5D), 1, 0.0D, 0.0D, 0.0D, 0.0D);
        }
    }

    private void emitPlaceEffect(Block block) {
        if (!particlesEnabled || !burstOnPlace) {
            return;
        }
        block.getWorld().spawnParticle(ambientParticle, block.getLocation().add(0.5D, 1.0D, 0.5D), Math.max(ambientCount * 5, 20), 0.45D, 0.45D, 0.45D, ambientSpeed);
    }

    private void emitBreakEffect(Block block) {
        if (!particlesEnabled || !burstOnBreak) {
            return;
        }
        block.getWorld().spawnParticle(borderParticle, block.getLocation().add(0.5D, 1.0D, 0.5D), Math.max(ambientCount * 4, 16), 0.45D, 0.45D, 0.45D, ambientSpeed);
    }

    private boolean hasParticleViewer(Location location) {
        if (particlePlayerRadius <= 0.0D) {
            return true;
        }
        double radiusSquared = particlePlayerRadius * particlePlayerRadius;
        for (Player player : location.getWorld().getPlayers()) {
            if (player.getLocation().distanceSquared(location) <= radiusSquared) {
                return true;
            }
        }
        return false;
    }

    private void tickVirtualSpawners() {
        Map<String, Set<Long>> chunksByWorld = new HashMap<>(activeChunkTicketsByWorld);
        int spawnedThisCycle = 0;

        for (Map.Entry<String, Set<Long>> entry : chunksByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) {
                continue;
            }

            for (Long chunkKey : new ArrayList<>(entry.getValue())) {
                if (spawnedThisCycle >= maxSpawnerSpawnsPerCycle) {
                    return;
                }

                int chunkX = unpackChunkX(chunkKey);
                int chunkZ = unpackChunkZ(chunkKey);
                if (!world.isChunkLoaded(chunkX, chunkZ)) {
                    continue;
                }

                Chunk chunk = world.getChunkAt(chunkX, chunkZ);
                for (BlockState state : chunk.getTileEntities()) {
                    if (state instanceof CreatureSpawner) {
                        spawnedThisCycle += tickSpawner((CreatureSpawner) state, maxSpawnerSpawnsPerCycle - spawnedThisCycle);
                        if (spawnedThisCycle >= maxSpawnerSpawnsPerCycle) {
                            return;
                        }
                    }
                }
            }
        }
    }

    private int tickSpawner(CreatureSpawner spawner, int remainingCycleBudget) {
        EntityType type = spawner.getSpawnedType();
        if (type == null || !type.isAlive() || remainingCycleBudget <= 0) {
            return 0;
        }

        Location center = spawner.getLocation().add(0.5D, 0.5D, 0.5D);
        int requiredPlayerRange = Math.max(0, spawner.getRequiredPlayerRange());
        String key = spawnerDelayKey(spawner);
        if (onlyWhenNoPlayerNearby && requiredPlayerRange > 0 && hasPlayerNearby(center, requiredPlayerRange)) {
            virtualSpawnerDelays.remove(key);
            return 0;
        }

        int delay = virtualSpawnerDelays.containsKey(key) ? virtualSpawnerDelays.get(key) : normalizedDelay(spawner.getDelay(), spawner);
        delay -= (int) spawnerIntervalTicks;
        if (delay > 0) {
            virtualSpawnerDelays.put(key, delay);
            return 0;
        }

        if (isSpawnerCrowded(spawner, type)) {
            resetSpawnerDelay(spawner, key);
            return 0;
        }

        int spawned = 0;
        int spawnCount = Math.max(1, spawner.getSpawnCount());
        int attempts = Math.min(spawnCount, remainingCycleBudget);
        for (int i = 0; i < attempts; i++) {
            if (spawnOneMob(spawner, type)) {
                spawned++;
            }
        }

        resetSpawnerDelay(spawner, key);
        return spawned;
    }

    private int normalizedDelay(int delay, CreatureSpawner spawner) {
        if (delay > 0) {
            return delay;
        }
        return nextSpawnerDelay(spawner);
    }

    private void resetSpawnerDelay(CreatureSpawner spawner, String key) {
        int delay = nextSpawnerDelay(spawner);
        virtualSpawnerDelays.put(key, delay);
        spawner.setDelay(delay);
        spawner.update(true, false);
    }

    private int nextSpawnerDelay(CreatureSpawner spawner) {
        int min = Math.max(1, spawner.getMinSpawnDelay());
        int max = Math.max(min, spawner.getMaxSpawnDelay());
        if (max <= min) {
            return min;
        }
        return min + random.nextInt(max - min + 1);
    }

    private boolean isSpawnerCrowded(CreatureSpawner spawner, EntityType type) {
        int maxNearby = spawner.getMaxNearbyEntities();
        if (maxNearby <= 0) {
            return false;
        }

        Location center = spawner.getLocation().add(0.5D, 0.5D, 0.5D);
        double horizontalRadius = Math.max(1.0D, spawner.getSpawnRange() * 2.0D);
        Collection<Entity> nearby = center.getWorld().getNearbyEntities(center, horizontalRadius, 4.0D, horizontalRadius);
        int matching = 0;
        for (Entity entity : nearby) {
            if (entity.getType() == type && !entity.isDead()) {
                matching++;
                if (matching >= maxNearby) {
                    return true;
                }
            }
        }
        return false;
    }

    private boolean spawnOneMob(CreatureSpawner spawner, EntityType type) {
        World world = spawner.getWorld();
        int range = Math.max(1, spawner.getSpawnRange());
        Location base = spawner.getLocation();

        for (int attempt = 0; attempt < 6; attempt++) {
            double x = base.getBlockX() + 0.5D + (random.nextDouble() - random.nextDouble()) * range;
            double y = base.getBlockY() + random.nextInt(3) - 1;
            double z = base.getBlockZ() + 0.5D + (random.nextDouble() - random.nextDouble()) * range;
            Location spawnLocation = new Location(world, x, y, z);
            if (!canSpawnAt(spawnLocation)) {
                continue;
            }

            try {
                world.spawnEntity(spawnLocation, type);
                return true;
            } catch (IllegalArgumentException ex) {
                getLogger().fine("Не удалось создать сущность " + type + " из спавнера: " + ex.getMessage());
                return false;
            }
        }
        return false;
    }

    private boolean canSpawnAt(Location location) {
        World world = location.getWorld();
        int y = location.getBlockY();
        if (world == null || y < 0 || y >= world.getMaxHeight() - 1) {
            return false;
        }

        int chunkX = blockToChunk(location.getBlockX());
        int chunkZ = blockToChunk(location.getBlockZ());
        if (!world.isChunkLoaded(chunkX, chunkZ)) {
            return false;
        }

        Block feet = location.getBlock();
        Block head = feet.getRelative(BlockFace.UP);
        return !feet.getType().isSolid() && !head.getType().isSolid();
    }

    private boolean hasPlayerNearby(Location location, int range) {
        double rangeSquared = (double) range * (double) range;
        for (Player player : location.getWorld().getPlayers()) {
            if (player.getLocation().distanceSquared(location) <= rangeSquared) {
                return true;
            }
        }
        return false;
    }

    private String spawnerDelayKey(CreatureSpawner spawner) {
        Location location = spawner.getLocation();
        return location.getWorld().getName() + ":" + location.getBlockX() + ":" + location.getBlockY() + ":" + location.getBlockZ();
    }

    private void forEachLoaderBlock(LoaderBlockConsumer consumer) {
        for (Map.Entry<String, Set<BlockKey>> entry : new HashMap<>(loadersByWorld).entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) {
                continue;
            }
            for (BlockKey key : new ArrayList<>(entry.getValue())) {
                int chunkX = blockToChunk(key.x);
                int chunkZ = blockToChunk(key.z);
                if (!world.isChunkLoaded(chunkX, chunkZ)) {
                    continue;
                }
                consumer.accept(world.getBlockAt(key.x, key.y, key.z));
            }
        }
    }

    private void playSound(Block block, Sound sound) {
        if (!soundsEnabled || sound == null) {
            return;
        }
        block.getWorld().playSound(block.getLocation().add(0.5D, 0.5D, 0.5D), sound, soundVolume, soundPitch);
    }

    private ItemStack createLoaderItem(int amount) {
        ItemStack item = new ItemStack(loaderMaterial, amount);
        ItemMeta meta = item.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(displayName);
            meta.setLore(lore);
            meta.getPersistentDataContainer().set(loaderItemKey, PersistentDataType.BYTE, (byte) 1);
            item.setItemMeta(meta);
        }
        return item;
    }

    private boolean isLoaderItem(ItemStack item) {
        if (item == null || item.getType() != loaderMaterial || !item.hasItemMeta()) {
            return false;
        }
        ItemMeta meta = item.getItemMeta();
        return meta != null && meta.getPersistentDataContainer().has(loaderItemKey, PersistentDataType.BYTE);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!sender.hasPermission("chunkloader.admin")) {
            sender.sendMessage(ChatColor.RED + "Нет прав: chunkloader.admin");
            return true;
        }

        if (args.length == 0 || args[0].equalsIgnoreCase("help")) {
            sendHelp(sender, label);
            return true;
        }

        if (args[0].equalsIgnoreCase("give")) {
            handleGive(sender, args);
            return true;
        }

        if (args[0].equalsIgnoreCase("list")) {
            handleList(sender);
            return true;
        }

        if (args[0].equalsIgnoreCase("reload")) {
            reloadConfig();
            readConfigValues();
            refreshChunkTickets();
            stopTasks();
            startParticleTasks();
            startSpawnerTask();
            sender.sendMessage(ChatColor.GREEN + "ChunkLoaderBlock перезагружен. Активных чанков: " + countAllClaimedChunks() + ".");
            return true;
        }

        sendHelp(sender, label);
        return true;
    }

    private void handleGive(CommandSender sender, String[] args) {
        Player target;
        if (args.length >= 2) {
            target = Bukkit.getPlayerExact(args[1]);
            if (target == null) {
                sender.sendMessage(ChatColor.RED + "Игрок не найден: " + args[1]);
                return;
            }
        } else if (sender instanceof Player) {
            target = (Player) sender;
        } else {
            sender.sendMessage(ChatColor.RED + "Консоль должна указать игрока: /chunkloader give <игрок>");
            return;
        }

        ItemStack item = createLoaderItem(1);
        PlayerInventory inventory = target.getInventory();
        Map<Integer, ItemStack> leftovers = inventory.addItem(item);
        for (ItemStack leftover : leftovers.values()) {
            target.getWorld().dropItemNaturally(target.getLocation(), leftover);
        }

        target.sendMessage(ChatColor.AQUA + "Вы получили прогружатель чанков.");
        if (!target.equals(sender)) {
            sender.sendMessage(ChatColor.GREEN + "Выдан прогружатель игроку " + target.getName() + ".");
        }
    }

    private void handleList(CommandSender sender) {
        if (loadersByWorld.isEmpty()) {
            sender.sendMessage(ChatColor.YELLOW + "Активных прогружателей нет.");
            return;
        }

        sender.sendMessage(ChatColor.AQUA + "Активные прогружатели:");
        for (Map.Entry<String, Set<BlockKey>> entry : loadersByWorld.entrySet()) {
            sender.sendMessage(ChatColor.GRAY + "- " + ChatColor.WHITE + entry.getKey() + ChatColor.GRAY
                    + ": " + ChatColor.GREEN + entry.getValue().size() + ChatColor.GRAY
                    + " блок(ов), " + countClaimedChunks(entry.getKey()) + " чанков");

            int shown = 0;
            for (BlockKey key : entry.getValue()) {
                if (shown >= 8) {
                    sender.sendMessage(ChatColor.DARK_GRAY + "  ...и ещё " + (entry.getValue().size() - shown));
                    break;
                }
                sender.sendMessage(ChatColor.DARK_GRAY + "  " + key.toStorageString());
                shown++;
            }
        }
    }

    private int countAllClaimedChunks() {
        int total = 0;
        for (Set<Long> chunks : computeDesiredChunkTickets().values()) {
            total += chunks.size();
        }
        return total;
    }

    private void sendHelp(CommandSender sender, String label) {
        sender.sendMessage(ChatColor.AQUA + "ChunkLoaderBlock:");
        sender.sendMessage(ChatColor.GRAY + "/" + label + " give [игрок]" + ChatColor.WHITE + " - выдать блок-прогружатель");
        sender.sendMessage(ChatColor.GRAY + "/" + label + " list" + ChatColor.WHITE + " - показать активные прогружатели");
        sender.sendMessage(ChatColor.GRAY + "/" + label + " reload" + ChatColor.WHITE + " - перезагрузить конфиг");
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!sender.hasPermission("chunkloader.admin")) {
            return Collections.emptyList();
        }

        if (args.length == 1) {
            return filter(Arrays.asList("give", "list", "reload"), args[0]);
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("give")) {
            List<String> names = new ArrayList<>();
            for (Player player : Bukkit.getOnlinePlayers()) {
                names.add(player.getName());
            }
            return filter(names, args[1]);
        }
        return Collections.emptyList();
    }

    private List<String> filter(List<String> values, String prefix) {
        String lowerPrefix = prefix == null ? "" : prefix.toLowerCase();
        List<String> result = new ArrayList<>();
        for (String value : values) {
            if (value.toLowerCase().startsWith(lowerPrefix)) {
                result.add(value);
            }
        }
        return result;
    }

    private static String color(String value) {
        return ChatColor.translateAlternateColorCodes('&', value == null ? "" : value);
    }

    private static int blockToChunk(int blockCoordinate) {
        return blockCoordinate >> 4;
    }

    private static long packChunkKey(int x, int z) {
        return (((long) x) << 32) ^ (z & 0xffffffffL);
    }

    private static int unpackChunkX(long key) {
        return (int) (key >> 32);
    }

    private static int unpackChunkZ(long key) {
        return (int) key;
    }

    private static String describeBlock(Block block) {
        return block.getWorld().getName() + " " + block.getX() + "," + block.getY() + "," + block.getZ();
    }

    private interface LoaderBlockConsumer {
        void accept(Block block);
    }

    private static final class BlockKey {
        private final int x;
        private final int y;
        private final int z;

        private BlockKey(int x, int y, int z) {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        private static BlockKey from(Block block) {
            return new BlockKey(block.getX(), block.getY(), block.getZ());
        }

        private static BlockKey parse(String value) {
            if (value == null) {
                return null;
            }

            String[] parts = value.trim().split(",");
            if (parts.length != 3) {
                return null;
            }

            try {
                return new BlockKey(Integer.parseInt(parts[0].trim()), Integer.parseInt(parts[1].trim()), Integer.parseInt(parts[2].trim()));
            } catch (NumberFormatException ex) {
                return null;
            }
        }

        private String toStorageString() {
            return x + "," + y + "," + z;
        }

        @Override
        public boolean equals(Object other) {
            if (this == other) {
                return true;
            }
            if (!(other instanceof BlockKey)) {
                return false;
            }
            BlockKey that = (BlockKey) other;
            return x == that.x && y == that.y && z == that.z;
        }

        @Override
        public int hashCode() {
            int result = x;
            result = 31 * result + y;
            result = 31 * result + z;
            return result;
        }
    }
}
