package com.devin.chunkloader;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Chunk;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.OfflinePlayer;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.PluginCommand;
import org.bukkit.command.TabCompleter;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

public final class ChunkLoaderPlugin extends JavaPlugin implements Listener, CommandExecutor, TabCompleter {

    private static final String DATA_FILE_NAME = "loaders.yml";
    private static final String DATA_ROOT_PATH = "loaders";

    private NamespacedKey loaderItemKey;
    private NamespacedKey ownerKey;
    private Material loaderMaterial;
    private int chunkSize;
    private String displayName;
    private List<String> lore;
    private boolean notifyPlayer;
    private boolean logActions;

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
    private final Map<String, Set<Long>> loadersByWorld = new HashMap<>();

    private BukkitTask ambientTask;
    private BukkitTask borderTask;

    @Override
    public void onEnable() {
        this.loaderItemKey = new NamespacedKey(this, "chunk_loader_item");
        this.ownerKey = new NamespacedKey(this, "chunk_loader_owner");

        saveDefaultConfig();
        readConfigValues();
        prepareDataFile();
        loadLoadersFromDisk();

        getServer().getPluginManager().registerEvents(this, this);

        PluginCommand cmd = Objects.requireNonNull(
                getCommand("chunkloader"),
                "команда 'chunkloader' отсутствует в plugin.yml"
        );
        cmd.setExecutor(this);
        cmd.setTabCompleter(this);

        Bukkit.getScheduler().runTask(this, this::applyAllForceLoads);
        startParticleTasks();

        getLogger().info("ChunkLoaderBlock включён. Материал=" + loaderMaterial
                + ", размер=" + chunkSize + "x" + chunkSize + ".");
    }

    @Override
    public void onDisable() {
        stopParticleTasks();
        removeAllPluginChunkTickets();
        saveLoadersToDisk();
    }

    // ==================== Config ====================

    private void readConfigValues() {
        FileConfiguration cfg = getConfig();

        String materialName = cfg.getString("loader-material", "LODESTONE");
        Material parsed = Material.matchMaterial(materialName == null ? "" : materialName.toUpperCase());
        if (parsed == null || !parsed.isBlock()) {
            getLogger().warning("Неверный материал loader-material='" + materialName + "', использую LODESTONE.");
            parsed = Material.LODESTONE;
        }
        this.loaderMaterial = parsed;

        int size = cfg.getInt("chunk-size", 8);
        if (size < 1) {
            getLogger().warning("chunk-size должен быть >= 1, получено " + size + ". Использую 8.");
            size = 8;
        }
        this.chunkSize = size;

        this.displayName = ChatColor.translateAlternateColorCodes('&',
                cfg.getString("display-name", "&bПрогружатель чанков &7[&a8x8&7]"));

        List<String> rawLore = cfg.getStringList("lore");
        List<String> coloredLore = new ArrayList<>(rawLore.size());
        for (String line : rawLore) {
            coloredLore.add(ChatColor.translateAlternateColorCodes('&', line));
        }
        this.lore = coloredLore;
        this.notifyPlayer = cfg.getBoolean("notify-player", true);
        this.logActions = cfg.getBoolean("log-actions", true);

        ConfigurationSection particles = cfg.getConfigurationSection("particles");
        if (particles == null) particles = cfg.createSection("particles");
        this.particlesEnabled = particles.getBoolean("enabled", true);
        this.ambientParticle = parseParticle(particles.getString("type", "END_ROD"), Particle.END_ROD);
        this.ambientCount = Math.max(1, particles.getInt("count", 6));
        this.ambientHeight = Math.max(0.0, particles.getDouble("height", 1.5));
        this.ambientOffset = Math.max(0.0, particles.getDouble("offset", 0.25));
        this.ambientSpeed = Math.max(0.0, particles.getDouble("speed", 0.02));
        this.ambientIntervalTicks = Math.max(1L, particles.getLong("interval-ticks", 10L));
        this.showBorders = particles.getBoolean("show-borders", true);
        this.borderParticle = parseParticle(particles.getString("border-type", "COMPOSTER"), Particle.COMPOSTER);
        this.borderIntervalTicks = Math.max(1L, particles.getLong("border-interval-ticks", 40L));
        this.borderStep = Math.max(1, particles.getInt("border-step", 8));
        this.particlePlayerRadius = Math.max(0.0, particles.getDouble("player-radius", 96.0));
        this.burstOnPlace = particles.getBoolean("burst-on-place", true);
        this.burstOnBreak = particles.getBoolean("burst-on-break", true);

        ConfigurationSection sounds = cfg.getConfigurationSection("sounds");
        if (sounds == null) sounds = cfg.createSection("sounds");
        this.soundsEnabled = sounds.getBoolean("enabled", true);
        this.placeSound = parseSound(sounds.getString("on-place", "BLOCK_BEACON_ACTIVATE"), Sound.BLOCK_BEACON_ACTIVATE);
        this.breakSound = parseSound(sounds.getString("on-break", "BLOCK_BEACON_DEACTIVATE"), Sound.BLOCK_BEACON_DEACTIVATE);
        this.soundVolume = (float) sounds.getDouble("volume", 0.7);
        this.soundPitch = (float) sounds.getDouble("pitch", 1.2);
    }

    private Particle parseParticle(String name, Particle fallback) {
        if (name == null || name.isEmpty()) return fallback;
        try {
            return Particle.valueOf(name.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            getLogger().warning("Неизвестная частица '" + name + "', использую " + fallback.name() + ".");
            return fallback;
        }
    }

    private Sound parseSound(String name, Sound fallback) {
        if (name == null || name.isEmpty()) return fallback;
        try {
            return Sound.valueOf(name.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            getLogger().warning("Неизвестный звук '" + name + "', использую " + fallback.name() + ".");
            return fallback;
        }
    }

    // ==================== Data persistence ====================

    private void prepareDataFile() {
        File folder = getDataFolder();
        if (!folder.exists() && !folder.mkdirs()) {
            getLogger().severe("Не удалось создать папку плагина: " + folder);
        }
        this.dataFile = new File(folder, DATA_FILE_NAME);
        if (!dataFile.exists()) {
            try {
                if (!dataFile.createNewFile()) {
                    getLogger().warning("Файл данных уже существует, продолжаю.");
                }
            } catch (IOException ex) {
                getLogger().log(Level.SEVERE, "Не удалось создать файл данных " + dataFile, ex);
            }
        }
        this.dataConfig = YamlConfiguration.loadConfiguration(dataFile);
    }

    private void loadLoadersFromDisk() {
        loadersByWorld.clear();
        if (dataConfig == null) return;
        if (!dataConfig.isConfigurationSection(DATA_ROOT_PATH)) return;

        Set<String> worldNames = Objects.requireNonNull(
                dataConfig.getConfigurationSection(DATA_ROOT_PATH)).getKeys(false);
        for (String worldName : worldNames) {
            List<String> raw = dataConfig.getStringList(DATA_ROOT_PATH + "." + worldName);
            Set<Long> packed = new LinkedHashSet<>();
            for (String entry : raw) {
                Long key = parseBlockKey(entry);
                if (key != null) packed.add(key);
            }
            if (!packed.isEmpty()) {
                loadersByWorld.put(worldName, packed);
            }
        }
    }

    private void saveLoadersToDisk() {
        if (dataConfig == null || dataFile == null) return;
        dataConfig.set(DATA_ROOT_PATH, null);
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            List<String> serialized = new ArrayList<>(entry.getValue().size());
            for (Long packed : entry.getValue()) {
                serialized.add(formatBlockKey(packed));
            }
            dataConfig.set(DATA_ROOT_PATH + "." + entry.getKey(), serialized);
        }
        try {
            dataConfig.save(dataFile);
        } catch (IOException ex) {
            getLogger().log(Level.SEVERE, "Не удалось сохранить файл данных " + dataFile, ex);
        }
    }

    // ==================== Block events ====================

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        ItemStack inHand = event.getItemInHand();
        if (!isChunkLoaderItem(inHand)) return;

        Player player = event.getPlayer();
        if (!player.hasPermission("chunkloader.place")) {
            player.sendMessage(ChatColor.RED + "У вас нет прав на установку прогружателя чанков.");
            event.setBuild(false);
            return;
        }

        Block block = event.getBlockPlaced();
        if (block.getType() != loaderMaterial) return;

        long key = packBlockKey(block.getX(), block.getY(), block.getZ());
        String worldName = block.getWorld().getName();
        Set<Long> set = loadersByWorld.computeIfAbsent(worldName, k -> new LinkedHashSet<>());
        if (!set.add(key)) return;

        int loaded = applyForceLoadAround(block.getWorld(), block.getChunk(), true);
        saveLoadersToDisk();

        if (burstOnPlace) emitPlaceEffect(block);
        if (soundsEnabled) {
            block.getWorld().playSound(
                    block.getLocation().add(0.5, 0.5, 0.5), placeSound, soundVolume, soundPitch);
        }
        if (notifyPlayer) {
            player.sendMessage(ChatColor.AQUA + "Прогружатель чанков установлен. "
                    + ChatColor.GRAY + "Загружено " + ChatColor.GREEN + loaded
                    + ChatColor.GRAY + " чанков (" + chunkSize + "x" + chunkSize + ").");
        }
        if (logActions) {
            getLogger().info("Установлен прогружатель в " + describeBlock(block)
                    + " игроком " + player.getName() + " (загружено " + loaded + " чанков).");
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        Block block = event.getBlock();
        long key = packBlockKey(block.getX(), block.getY(), block.getZ());
        String worldName = block.getWorld().getName();
        Set<Long> set = loadersByWorld.get(worldName);
        if (set == null || !set.contains(key)) return;

        Player player = event.getPlayer();
        if (!player.hasPermission("chunkloader.break")) {
            player.sendMessage(ChatColor.RED + "У вас нет прав ломать прогружатель чанков.");
            event.setCancelled(true);
            return;
        }

        set.remove(key);
        if (set.isEmpty()) loadersByWorld.remove(worldName);

        int released = releaseForceLoadAround(block.getWorld(), block.getChunk());
        saveLoadersToDisk();

        if (burstOnBreak) emitBreakEffect(block);
        if (soundsEnabled) {
            block.getWorld().playSound(
                    block.getLocation().add(0.5, 0.5, 0.5), breakSound, soundVolume, soundPitch);
        }
        if (notifyPlayer) {
            player.sendMessage(ChatColor.AQUA + "Прогружатель чанков сломан. "
                    + ChatColor.GRAY + "Освобождено " + ChatColor.YELLOW + released
                    + ChatColor.GRAY + " чанков.");
        }
        if (logActions) {
            getLogger().info("Сломан прогружатель в " + describeBlock(block)
                    + " игроком " + player.getName() + " (освобождено " + released + " чанков).");
        }
    }

    @EventHandler
    public void onWorldLoad(WorldLoadEvent event) {
        World world = event.getWorld();
        Set<Long> set = loadersByWorld.get(world.getName());
        if (set == null || set.isEmpty()) return;

        int total = 0;
        for (Long packed : set) {
            int bx = unpackX(packed);
            int bz = unpackZ(packed);
            Chunk chunk = world.getChunkAt(bx >> 4, bz >> 4);
            total += applyForceLoadAround(world, chunk, false);
        }
        if (logActions) {
            getLogger().info("Мир '" + world.getName() + "' загружен; переприменено для "
                    + set.size() + " прогружателя(ей), всего " + total + " чанков.");
        }
    }

    // ==================== Core chunk loading ====================

    private void applyAllForceLoads() {
        int worlds = 0, loaders = 0, chunks = 0;
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) continue;
            ++worlds;
            for (Long packed : entry.getValue()) {
                int bx = unpackX(packed);
                int bz = unpackZ(packed);
                Chunk chunk = world.getChunkAt(bx >> 4, bz >> 4);
                chunks += applyForceLoadAround(world, chunk, false);
                ++loaders;
            }
        }
        if (logActions) {
            getLogger().info("Применена прогрузка при старте: " + loaders
                    + " прогружателя(ей) в " + worlds + " мире(ах), " + chunks + " чанков.");
        }
    }

    private int applyForceLoadAround(World world, Chunk center, boolean countOnlyNew) {
        int count = 0;
        int half = chunkSize / 2;
        int startX = center.getX() - half;
        int startZ = center.getZ() - half;
        int endX = startX + chunkSize;
        int endZ = startZ + chunkSize;

        for (int cx = startX; cx < endX; cx++) {
            for (int cz = startZ; cz < endZ; cz++) {
                boolean wasForced = world.isChunkForceLoaded(cx, cz);

                // Mark as force-loaded (persists in world data)
                world.setChunkForceLoaded(cx, cz, true);

                // Add plugin chunk ticket (keeps chunk loaded in memory reliably)
                world.addPluginChunkTicket(cx, cz, this);

                // Ensure the chunk is actually loaded now
                if (!world.isChunkLoaded(cx, cz)) {
                    world.loadChunk(cx, cz);
                }

                if (!countOnlyNew || !wasForced) {
                    ++count;
                }
            }
        }
        return count;
    }

    private int releaseForceLoadAround(World world, Chunk center) {
        int released = 0;
        int half = chunkSize / 2;
        int startX = center.getX() - half;
        int startZ = center.getZ() - half;
        int endX = startX + chunkSize;
        int endZ = startZ + chunkSize;

        Set<Long> claimedByOthers = computeClaimedChunks(world.getName());
        for (int cx = startX; cx < endX; cx++) {
            for (int cz = startZ; cz < endZ; cz++) {
                long chunkKey = packChunkKey(cx, cz);
                if (claimedByOthers.contains(chunkKey)) continue;

                if (world.isChunkForceLoaded(cx, cz)) {
                    world.setChunkForceLoaded(cx, cz, false);
                    world.removePluginChunkTicket(cx, cz, this);
                    ++released;
                }
            }
        }
        return released;
    }

    private Set<Long> computeClaimedChunks(String worldName) {
        Set<Long> claimed = new HashSet<>();
        Set<Long> loaders = loadersByWorld.get(worldName);
        if (loaders == null) return claimed;

        int half = chunkSize / 2;
        for (Long packed : loaders) {
            int bx = unpackX(packed);
            int bz = unpackZ(packed);
            int centerCx = bx >> 4;
            int centerCz = bz >> 4;
            int startX = centerCx - half;
            int startZ = centerCz - half;
            int endX = startX + chunkSize;
            int endZ = startZ + chunkSize;
            for (int cx = startX; cx < endX; cx++) {
                for (int cz = startZ; cz < endZ; cz++) {
                    claimed.add(packChunkKey(cx, cz));
                }
            }
        }
        return claimed;
    }

    private void removeAllPluginChunkTickets() {
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) continue;
            int half = chunkSize / 2;
            for (Long packed : entry.getValue()) {
                int bx = unpackX(packed);
                int bz = unpackZ(packed);
                int centerCx = bx >> 4;
                int centerCz = bz >> 4;
                int startX = centerCx - half;
                int startZ = centerCz - half;
                int endX = startX + chunkSize;
                int endZ = startZ + chunkSize;
                for (int cx = startX; cx < endX; cx++) {
                    for (int cz = startZ; cz < endZ; cz++) {
                        world.removePluginChunkTicket(cx, cz, this);
                    }
                }
            }
        }
    }

    // ==================== Particles ====================

    private void startParticleTasks() {
        stopParticleTasks();
        if (!particlesEnabled) return;
        this.ambientTask = Bukkit.getScheduler().runTaskTimer(
                this, this::tickAmbientParticles, ambientIntervalTicks, ambientIntervalTicks);
        if (showBorders) {
            this.borderTask = Bukkit.getScheduler().runTaskTimer(
                    this, this::tickBorderParticles, borderIntervalTicks, borderIntervalTicks);
        }
    }

    private void stopParticleTasks() {
        if (ambientTask != null) { ambientTask.cancel(); ambientTask = null; }
        if (borderTask != null) { borderTask.cancel(); borderTask = null; }
    }

    private void tickAmbientParticles() {
        double r2 = particlePlayerRadius * particlePlayerRadius;
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) continue;
            List<Player> players = world.getPlayers();
            if (players.isEmpty()) continue;

            for (Long packed : entry.getValue()) {
                int bx = unpackX(packed);
                int by = unpackY(packed);
                int bz = unpackZ(packed);
                if (!world.isChunkLoaded(bx >> 4, bz >> 4)) continue;
                if (!anyPlayerWithin(players, bx, bz, r2)) continue;

                double cx = bx + 0.5;
                double cz = bz + 0.5;
                ThreadLocalRandom rng = ThreadLocalRandom.current();
                for (int i = 0; i < ambientCount; i++) {
                    double dy = rng.nextDouble() * ambientHeight;
                    world.spawnParticle(ambientParticle, cx, by + 1.0 + dy, cz,
                            1, ambientOffset, 0.0, ambientOffset, ambientSpeed);
                }
            }
        }
    }

    private void tickBorderParticles() {
        double r2 = particlePlayerRadius * particlePlayerRadius;
        int half = chunkSize / 2;
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            World world = Bukkit.getWorld(entry.getKey());
            if (world == null) continue;
            List<Player> players = world.getPlayers();
            if (players.isEmpty()) continue;

            for (Long packed : entry.getValue()) {
                int bx = unpackX(packed);
                int by = unpackY(packed);
                int bz = unpackZ(packed);
                if (!world.isChunkLoaded(bx >> 4, bz >> 4)) continue;
                if (!anyPlayerWithin(players, bx, bz, r2)) continue;

                int chunkX = bx >> 4;
                int chunkZ = bz >> 4;
                int minCX = chunkX - half;
                int minCZ = chunkZ - half;
                int maxCX = minCX + chunkSize;
                int maxCZ = minCZ + chunkSize;
                double minBX = minCX * 16.0;
                double minBZ = minCZ * 16.0;
                double maxBX = maxCX * 16.0;
                double maxBZ = maxCZ * 16.0;
                double y = by + 1.0;

                for (double x = minBX; x <= maxBX; x += borderStep) {
                    world.spawnParticle(borderParticle, x, y, minBZ, 1, 0, 0, 0, 0);
                    world.spawnParticle(borderParticle, x, y, maxBZ, 1, 0, 0, 0, 0);
                }
                for (double z = minBZ; z <= maxBZ; z += borderStep) {
                    world.spawnParticle(borderParticle, minBX, y, z, 1, 0, 0, 0, 0);
                    world.spawnParticle(borderParticle, maxBX, y, z, 1, 0, 0, 0, 0);
                }
            }
        }
    }

    private void emitPlaceEffect(Block block) {
        World world = block.getWorld();
        double cx = block.getX() + 0.5;
        double cy = block.getY() + 1.0;
        double cz = block.getZ() + 0.5;
        world.spawnParticle(Particle.END_ROD, cx, cy, cz, 40, 0.4, 0.4, 0.4, 0.1);
        world.spawnParticle(Particle.PORTAL, cx, cy, cz, 60, 0.6, 0.6, 0.6, 0.4);
    }

    private void emitBreakEffect(Block block) {
        World world = block.getWorld();
        double cx = block.getX() + 0.5;
        double cy = block.getY() + 0.5;
        double cz = block.getZ() + 0.5;
        world.spawnParticle(Particle.SMOKE_LARGE, cx, cy, cz, 30, 0.4, 0.4, 0.4, 0.05);
        world.spawnParticle(Particle.CRIT_MAGIC, cx, cy, cz, 25, 0.4, 0.4, 0.4, 0.2);
    }

    private boolean anyPlayerWithin(List<Player> players, int x, int z, double r2) {
        for (Player p : players) {
            Location loc = p.getLocation();
            double dx = loc.getX() - (x + 0.5);
            double dz = loc.getZ() - (z + 0.5);
            if (dx * dx + dz * dz <= r2) return true;
        }
        return false;
    }

    // ==================== Commands ====================

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!command.getName().equalsIgnoreCase("chunkloader")) return false;
        if (!sender.hasPermission("chunkloader.admin")) {
            sender.sendMessage(ChatColor.RED + "У вас нет прав использовать эту команду.");
            return true;
        }
        if (args.length == 0) { sendUsage(sender); return true; }

        switch (args[0].toLowerCase()) {
            case "give":   return handleGive(sender, args);
            case "list":   return handleList(sender);
            case "reload":  return handleReload(sender);
            default:        sendUsage(sender); return true;
        }
    }

    private boolean handleGive(CommandSender sender, String[] args) {
        Player target;
        if (args.length >= 2) {
            target = Bukkit.getPlayerExact(args[1]);
            if (target == null) {
                sender.sendMessage(ChatColor.RED + "Игрок не найден: " + args[1]);
                return true;
            }
        } else {
            if (!(sender instanceof Player)) {
                sender.sendMessage(ChatColor.RED + "Укажите игрока: /chunkloader give <игрок>");
                return true;
            }
            target = (Player) sender;
        }
        ItemStack item = createChunkLoaderItem(target);
        target.getInventory().addItem(item);
        sender.sendMessage(ChatColor.AQUA + "Прогружатель чанков выдан игроку "
                + ChatColor.WHITE + target.getName() + ChatColor.AQUA + ".");
        return true;
    }

    private boolean handleList(CommandSender sender) {
        if (loadersByWorld.isEmpty()) {
            sender.sendMessage(ChatColor.GRAY + "Активных прогружателей чанков нет.");
            return true;
        }
        sender.sendMessage(ChatColor.AQUA + "Активные прогружатели чанков:");
        for (Map.Entry<String, Set<Long>> entry : loadersByWorld.entrySet()) {
            sender.sendMessage(ChatColor.GRAY + " - " + ChatColor.WHITE + entry.getKey()
                    + ChatColor.GRAY + ": " + ChatColor.GREEN + entry.getValue().size()
                    + ChatColor.GRAY + " шт.");
            for (Long packed : entry.getValue()) {
                sender.sendMessage("    " + ChatColor.DARK_GRAY
                        + "x=" + unpackX(packed) + ", y=" + unpackY(packed) + ", z=" + unpackZ(packed));
            }
        }
        return true;
    }

    private boolean handleReload(CommandSender sender) {
        removeAllPluginChunkTickets();
        reloadConfig();
        readConfigValues();
        loadLoadersFromDisk();
        applyAllForceLoads();
        startParticleTasks();
        sender.sendMessage(ChatColor.AQUA + "Конфигурация ChunkLoaderBlock перезагружена.");
        return true;
    }

    private void sendUsage(CommandSender sender) {
        sender.sendMessage(ChatColor.AQUA + "/chunkloader give [игрок]"
                + ChatColor.GRAY + " — выдать предмет-прогружатель");
        sender.sendMessage(ChatColor.AQUA + "/chunkloader list"
                + ChatColor.GRAY + " — список активных прогружателей");
        sender.sendMessage(ChatColor.AQUA + "/chunkloader reload"
                + ChatColor.GRAY + " — перезагрузить конфиг и переприменить прогрузку");
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!command.getName().equalsIgnoreCase("chunkloader")) return Collections.emptyList();
        if (args.length == 1) {
            List<String> base = new ArrayList<>(Arrays.asList("give", "list", "reload"));
            String prefix = args[0].toLowerCase();
            base.removeIf(s -> !s.startsWith(prefix));
            return base;
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("give")) {
            List<String> names = new ArrayList<>();
            for (Player p : Bukkit.getOnlinePlayers()) {
                if (p.getName().toLowerCase().startsWith(args[1].toLowerCase())) {
                    names.add(p.getName());
                }
            }
            return names;
        }
        return Collections.emptyList();
    }

    // ==================== Item creation / checks ====================

    private ItemStack createChunkLoaderItem(OfflinePlayer owner) {
        ItemStack stack = new ItemStack(loaderMaterial, 1);
        ItemMeta meta = stack.getItemMeta();
        if (meta == null) return stack;

        meta.setDisplayName(displayName);
        if (!lore.isEmpty()) meta.setLore(new ArrayList<>(lore));

        PersistentDataContainer pdc = meta.getPersistentDataContainer();
        pdc.set(loaderItemKey, PersistentDataType.BYTE, (byte) 1);
        if (owner != null && owner.getUniqueId() != null) {
            pdc.set(ownerKey, PersistentDataType.STRING, owner.getUniqueId().toString());
        }
        stack.setItemMeta(meta);
        return stack;
    }

    private boolean isChunkLoaderItem(ItemStack stack) {
        if (stack == null || stack.getType() != loaderMaterial) return false;
        ItemMeta meta = stack.getItemMeta();
        if (meta == null) return false;
        Byte tag = meta.getPersistentDataContainer().get(loaderItemKey, PersistentDataType.BYTE);
        return tag != null && tag == 1;
    }

    // ==================== Key packing ====================

    private static long packBlockKey(int x, int y, int z) {
        long lx = (long) x & 0xFFFFFFFL;
        long lz = (long) z & 0xFFFFFFFL;
        long ly = (long) y & 0xFFL;
        return (lx << 36) | (lz << 8) | ly;
    }

    private static int unpackX(long key) {
        long raw = (key >> 36) & 0xFFFFFFFL;
        return (int) signExtend(raw, 28);
    }

    private static int unpackZ(long key) {
        long raw = (key >> 8) & 0xFFFFFFFL;
        return (int) signExtend(raw, 28);
    }

    private static int unpackY(long key) {
        return (int) (key & 0xFFL);
    }

    private static long signExtend(long raw, int bits) {
        long signBit = 1L << (bits - 1);
        long mask = (1L << bits) - 1L;
        raw &= mask;
        if ((raw & signBit) != 0) raw -= (1L << bits);
        return raw;
    }

    private static long packChunkKey(int cx, int cz) {
        return ((long) cx & 0xFFFFFFFFL) << 32 | ((long) cz & 0xFFFFFFFFL);
    }

    private String formatBlockKey(long packed) {
        return unpackX(packed) + "," + unpackY(packed) + "," + unpackZ(packed);
    }

    private Long parseBlockKey(String raw) {
        if (raw == null) return null;
        String[] parts = raw.split(",");
        if (parts.length != 3) return null;
        try {
            int x = Integer.parseInt(parts[0].trim());
            int y = Integer.parseInt(parts[1].trim());
            int z = Integer.parseInt(parts[2].trim());
            return packBlockKey(x, y, z);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static String describeBlock(Block block) {
        return block.getWorld().getName() + " " + block.getX() + "/" + block.getY() + "/" + block.getZ();
    }

    UUID computeOwnerId(ItemStack stack) {
        ItemMeta meta = (stack == null) ? null : stack.getItemMeta();
        if (meta == null) return null;
        String raw = meta.getPersistentDataContainer().get(ownerKey, PersistentDataType.STRING);
        if (raw == null) return null;
        try { return UUID.fromString(raw); }
        catch (IllegalArgumentException ex) { return null; }
    }
}
