package Polfg.Polfg;

import net.milkbowl.vault.economy.Economy;
import org.bukkit.*;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.*;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Vector;
import org.bukkit.DyeColor;

import java.lang.reflect.Method;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import java.util.stream.Collectors;

import de.oliver.fancyholograms.api.FancyHologramsPlugin;
import de.oliver.fancyholograms.api.HologramManager;
import de.oliver.fancyholograms.api.data.TextHologramData;
import de.oliver.fancyholograms.api.hologram.Hologram;

class SpawnerConfig {
    private final String id;
    private final String worldName;
    private Location spawnLoc;
    private Location despawnLoc;
    private Location hologramLoc;
    private double speed;
    private String direction;
    private long cooldownTicks;
    private boolean enabled;
    private boolean paused;

    public SpawnerConfig(String id, String worldName) {
        this.id = id;
        this.worldName = worldName;
        this.speed = 0.2;
        this.direction = "forward";
        this.cooldownTicks = 600;
        this.enabled = true;
        this.paused = false;
    }

    public String getId() { return id; }
    public String getWorldName() { return worldName; }
    public Location getSpawnLoc() { return spawnLoc; }
    public void setSpawnLoc(Location loc) { this.spawnLoc = loc; }
    public Location getDespawnLoc() { return despawnLoc; }
    public void setDespawnLoc(Location loc) { this.despawnLoc = loc; }
    public Location getHologramLoc() { return hologramLoc; }
    public void setHologramLoc(Location loc) { this.hologramLoc = loc; }
    public double getSpeed() { return speed; }
    public void setSpeed(double speed) { this.speed = speed; }
    public String getDirection() { return direction; }
    public void setDirection(String dir) { this.direction = dir; }
    public long getCooldownTicks() { return cooldownTicks; }
    public void setCooldownTicks(long ticks) { this.cooldownTicks = ticks; }
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public boolean isPaused() { return paused; }
    public void setPaused(boolean paused) { this.paused = paused; }
    public World getWorld() { return Bukkit.getWorld(worldName); }
    public boolean isValid() { return getWorld() != null && spawnLoc != null && despawnLoc != null; }
}

public class BrainrotSpawner extends JavaPlugin implements Listener {

    private final Map<String, SpawnerConfig> spawnerConfigs = new HashMap<>();
    private final Map<String, BukkitRunnable> spawnerTasks = new HashMap<>();
    private final Map<String, Deque<MobData>> spawnQueues = new HashMap<>();
    private final Map<Entity, String> mobToSpawner = new HashMap<>();

    private static BrainrotSpawner instance;

    private final Map<Entity, List<ArmorStand>> mobNameTags = new HashMap<>();
    private final Map<Entity, Long> mobClickCooldown = new HashMap<>();
    private final Map<Entity, MobData> mobDataMap = new HashMap<>();
    private final Map<Entity, BukkitRunnable> movementTasks = new HashMap<>();
    private final Map<Entity, Double> mobHoloHeights = new HashMap<>();

    private final Map<Entity, BukkitRunnable> deliveryTasks = new HashMap<>();
    private final Map<Entity, Player> mobBuyers = new HashMap<>();
    private final Map<Entity, Location> deliveryDestinations = new HashMap<>();
    private final Map<UUID, Integer> playerComboCounter = new HashMap<>();
    private final Map<Entity, Location> luckyVirtualLoc = new HashMap<>();
    private final Map<UUID, Long> lastHitTime = new HashMap<>();
    private final Map<UUID, Long> playerHitCooldown = new HashMap<>();

    private final Set<UUID> bedrockPlayerCache = new HashSet<>();
    private boolean floodgateAvailable = false;

    private Economy economy;
    private final Random random = new Random();
    private int spawnCount = 0;

    private static final double NAME_TAG_LINE_HEIGHT = 0.28;
    private static final long CLICK_COOLDOWN = 500;

    private static final int LEGENDARY_GUARANTEE_TICKS = 5 * 60 * 20;
    private static final int MYTHICAL_GUARANTEE_TICKS = 15 * 60 * 20;

    private final Map<String, Integer> legendaryTicksLeft = new HashMap<>();
    private final Map<String, Integer> mythicalTicksLeft = new HashMap<>();

    private final Map<String, Hologram> spawnerHolograms = new HashMap<>();
    private HologramManager hologramManager;
    private BukkitRunnable hologramUpdateTask;

    private final Map<Entity, Entity> spongeHitboxMap = new HashMap<>();
    private final Map<Entity, Long> luckyBlockOpenTime = new ConcurrentHashMap<>();
    private final Map<Entity, Boolean> luckyBlockReady = new ConcurrentHashMap<>();
    private static final long LUCKY_BLOCK_TIMER = 15 * 60 * 1000L;
    private final Map<Entity, Mutation> mobMutations = new HashMap<>();
    private final Map<Entity, BukkitRunnable> rainbowAnimationTasks = new HashMap<>();

    private final Map<Entity, List<ItemDisplay>> luckyBlockWings = new HashMap<>();
    private final Map<Entity, BukkitRunnable> wingAnimations = new HashMap<>();

    // Кэш набора «стакающихся» мутаций (тегов) для перерисовки нейм-тегов при изменении.
    private final Map<Entity, String> mobExtrasCache = new HashMap<>();

    // Клиент игнорирует обычные пакеты перемещения для Эндер Дракона (EnderDragon#lerpTo пустой),
    // поэтому дракон визуально стоит на месте, хотя на сервере он двигается. Обход: невидимый
    // маркер-армостенд как транспорт, дракон — принудительный пассажир. Пассажира клиент ставит
    // напрямую от позиции транспорта, так что дракон едет вместе с ним.
    private final Map<Entity, Entity> dragonCarriers = new HashMap<>();
    private static final String DRAGON_CARRIER_TAG = "BRAINROT_DRAGON_CARRIER";
    private static final double DRAGON_CARRIER_Y_OFFSET = 0.0;
    // Разворот модели дракона относительно направления конвейера (config: dragon.yaw-offset).
    private float dragonYawOffset = -90.0f;
    // Инверсия знака yaw (config: dragon.yaw-invert). Нужна, потому что клиент рисует дракона зеркально.
    private boolean dragonYawInvert = false;

    private final Map<Entity, Entity> rotWalkerHitboxMap = new HashMap<>();
    private final Map<Entity, BukkitRunnable> rotWalkerAnimTasks = new HashMap<>();
    private static final String ROT_WALKER_ROOT_TAG = "aj.rotwalker.root";
    private static final String ROT_WALKER_ENTITY_TAG = "aj.rotwalker.entity";

    private enum Mutation {
        NONE("", "", 1.0, 92),
        GOLD("Золотой", "§6", 1.25, 6),
        DIAMOND("Алмазный", "§b", 1.5, 1.8),
        RAINBOW("Радужный", "§f", 10.0, 0.2),
        // Ивентовые (chance = 0 -> никогда не выпадают при спавне, выдаются извне).
        SNOWY("Снежный", "§b", 5.0, 0),
        ELECTRIC("Электрический", "§e", 3.0, 0),
        METEOR("Метеоритный", "§c", 4.0, 0),
        EXPLOSIVE("Взрывной", "§a", 3.5, 0);

        final String displayName;
        final String format;
        final double incomeMultiplier;
        final double chance;

        Mutation(String displayName, String format, double incomeMultiplier, double chance) {
            this.displayName = displayName;
            this.format = format;
            this.incomeMultiplier = incomeMultiplier;
            this.chance = chance;
        }
    }

    private enum Rarity {
        COMMON("Обычный", "§a", 55.0),
        RARE("Редкий", "§9", 25.0),
        EPIC("Эпический", "§5", 13.0),
        LEGENDARY("Легендарный", "§6§l", 5.0),
        MYTHICAL("✦ Мифический ✦", "§d§l", 1.89),
        BRAINROT_GOD("✧ Божественный ✧", "§b§l", 0.10),
        SECRET("☠ Секретный ☠", "§8§l", 0.01),
        EVENT("Ивентовый", "§2§l", 0.0);

        final String displayName;
        final String format;
        final double chance;

        Rarity(String displayName, String format, double chance) {
            this.displayName = displayName;
            this.format = format;
            this.chance = chance;
        }
    }

    private enum MobData {
        CHICKEN("Курица", EntityType.CHICKEN, 250, 3, 40, Rarity.COMMON),
        COW("Корова", EntityType.COW, 500, 5, 20, Rarity.COMMON),
        SHEEP("Овца", EntityType.SHEEP, 750, 7, 15, Rarity.COMMON),
        PIG("Свинья", EntityType.PIG, 1000, 9, 15, Rarity.COMMON),
        RABBIT("Кролик", EntityType.RABBIT, 1200, 10, 10, Rarity.COMMON),
        PARROT("Попугай", EntityType.PARROT, 1500, 13, 10, Rarity.COMMON),
        TURTLE("Черепаха", EntityType.TURTLE, 1800, 15, 10, Rarity.COMMON),

        FOX("Лиса", EntityType.FOX, 2000, 15, 15, Rarity.RARE),
        PANDA("Панда", EntityType.PANDA, 4000, 30, 12, Rarity.RARE),
        WOLF("Бульбульдог", EntityType.WOLF, 4500, 35, 12, Rarity.RARE),
        DOLPHIN("Дельфин", EntityType.DOLPHIN, 5000, 40, 12, Rarity.RARE),
        HORSE("Лошадь", EntityType.HORSE, 6500, 50, 12, Rarity.RARE),
        LLAMA("Лама", EntityType.LLAMA, 7500, 55, 10, Rarity.RARE),
        POLAR_BEAR("Белый медведь", EntityType.POLAR_BEAR, 9000, 65, 10, Rarity.RARE),
        RAVAGER("Разоритель", EntityType.RAVAGER, 9200, 67, 8, Rarity.RARE),
        CAT_KUZYA("Кот Кузя", EntityType.CAT, 5500, 45, 9, Rarity.RARE),

        ENDERMAN("Эндермен", EntityType.ENDERMAN, 10000, 75, 12, Rarity.EPIC),
        BLAZE("Ифрит", EntityType.BLAZE, 12500, 90, 12, Rarity.EPIC),
        WITHER_SKELETON("Визер-скелет", EntityType.WITHER_SKELETON, 15000, 100, 10, Rarity.EPIC),
        IRON_GOLEM("Железный голем", EntityType.IRON_GOLEM, 17500, 115, 10, Rarity.EPIC),
        GUARDIAN("Страж", EntityType.GUARDIAN, 22500, 135, 10, Rarity.EPIC),
        ENDERMITE("Эндермит", EntityType.ENDERMITE, 23500, 140, 8, Rarity.EPIC),
        EVOKER("Заклинатель", EntityType.EVOKER, 25000, 150, 8, Rarity.EPIC),
        VINDICATOR("Поборник", EntityType.VINDICATOR, 27500, 160, 8, Rarity.EPIC),
        HUSK("Кадавр", EntityType.HUSK, 30000, 175, 8, Rarity.EPIC),
        STRAY("Зимогор", EntityType.STRAY, 35000, 225, 7, Rarity.EPIC),
        ELDER_GUARDIAN("Древний страж", EntityType.ELDER_GUARDIAN, 37500, 250, 7, Rarity.EPIC),

        MOOSHROOM("Грибная корова", EntityType.MOOSHROOM, 35000, 200, 8, Rarity.LEGENDARY),
        ZOMBIE_HORSE("Зомби-лошадь", EntityType.ZOMBIE_HORSE, 50000, 300, 8, Rarity.LEGENDARY),
        SKELETON_HORSE("Скелет-лошадь", EntityType.SKELETON_HORSE, 75000, 450, 7, Rarity.LEGENDARY),
        STRIDER("Страйдер", EntityType.STRIDER, 100000, 500, 7, Rarity.LEGENDARY),
        PHANTOM("Фантом", EntityType.PHANTOM, 150000, 600, 6, Rarity.LEGENDARY),
        VEX("Векс", EntityType.VEX, 200000, 750, 6, Rarity.LEGENDARY),
        MAGMA_CUBE("Магмовый куб", EntityType.MAGMA_CUBE, 250000, 1000, 5, Rarity.LEGENDARY),
        HOGLIN("Хоглин", EntityType.HOGLIN, 255000, 1000, 5, Rarity.LEGENDARY),
        PIGLIN_BRUTE("Пиглин-воин", EntityType.PIGLIN_BRUTE, 256000, 1100, 5, Rarity.LEGENDARY),
        PILLAGER("Разбойник", EntityType.PILLAGER, 275000, 1100, 5, Rarity.LEGENDARY),
        SILVERFISH("Чешуйница", EntityType.SILVERFISH, 285000, 1200, 5, Rarity.LEGENDARY),
        WITCH("Ведьма", EntityType.WITCH, 300000, 1200, 5, Rarity.LEGENDARY),
        CAVE_SPIDER("Пещерный паук", EntityType.CAVE_SPIDER, 310000, 1200, 5, Rarity.LEGENDARY),
        SPIDER("Паук", EntityType.SPIDER, 315000, 1200, 5, Rarity.LEGENDARY),
        ILLUSIONER("Иллюзионист", EntityType.ILLUSIONER, 320000, 1300, 4, Rarity.LEGENDARY),
        OCELOT("Оцелот", EntityType.OCELOT, 325000, 1300, 4, Rarity.LEGENDARY),
        BAT("Летучая мышь", EntityType.BAT, 325000, 1800, 3, Rarity.LEGENDARY),
        BEE("Пчела", EntityType.BEE, 345000, 1400, 2, Rarity.LEGENDARY),

        CAMEL("Верблюд", EntityType.CAMEL, 300000, 1200, 15, Rarity.MYTHICAL),
        BROWN_PANDA("Коричневая панда", EntityType.PANDA, 400000, 1700, 12, Rarity.MYTHICAL),
        CREEPER("Крипер", EntityType.CREEPER, 450000, 2100, 12, Rarity.MYTHICAL),
        DROWNED("Утопленник", EntityType.DROWNED, 500000, 2500, 10, Rarity.MYTHICAL),
        FROG("Лягушка", EntityType.FROG, 600000, 3000, 10, Rarity.MYTHICAL),
        SPONGE("Лаки-Блок", EntityType.ITEM_DISPLAY, 750000, 0, 5, Rarity.MYTHICAL),
        GOAT("Козёл", EntityType.GOAT, 1000000, 5000, 7, Rarity.MYTHICAL),
        GLOW_SQUID("Светящийся кальмар", EntityType.GLOW_SQUID, 1000000, 6000, 6, Rarity.MYTHICAL),
        WANDERING_TRADER("Странствующий торговец", EntityType.WANDERING_TRADER, 1200000, 7500, 5, Rarity.MYTHICAL),
        SNOW_GOLEM("Снеговик", EntityType.SNOW_GOLEM, 1500000, 7500, 4, Rarity.MYTHICAL),
        PIGLIN("Пиглин", EntityType.PIGLIN, 1800000, 8000, 3, Rarity.MYTHICAL),
        MYTHIC_SKELETON_HORSE("Скелет-лошадь", EntityType.SKELETON_HORSE, 2000000, 8500, 2, Rarity.MYTHICAL),
        ZOMBIFIED_PIGLIN("Зомби-пиглин", EntityType.ZOMBIFIED_PIGLIN, 2200000, 9000, 2, Rarity.MYTHICAL),
        ALLAY("Аллей", EntityType.ALLAY, 2500000, 9500, 1.5, Rarity.MYTHICAL),
        SNIFFER("Сниффер", EntityType.SNIFFER, 2800000, 10000, 1, Rarity.MYTHICAL),
        ZOGLIN("Зоглин", EntityType.ZOGLIN, 3000000, 11000, 0.7, Rarity.MYTHICAL),
        AXOLOTL("Аксолотль", EntityType.AXOLOTL, 3500000, 12000, 0.5, Rarity.MYTHICAL),
        WARDEN("Варден", EntityType.WARDEN, 5000000, 15000, 0.3, Rarity.MYTHICAL),

        // ── Божественный ──────────────────────────────────────────────────
        // Подложка — HUSK: не горит на солнце (в отличие от зомби), живая
        // сущность, поэтому setupMob гасит ей ИИ и гравитацию как всем прочим,
        // и по ней исправно приходит PlayerInteractAtEntityEvent. Саму её
        // ModelEngine прячет, игрок видит только модель самовара.
        SAMOVARUS("Самоварус Максимус", EntityType.HUSK, 40_000_000L, 120_000L, 100, Rarity.BRAINROT_GOD),

        ENDER_DRAGON("Эндер Дракон", EntityType.ENDER_DRAGON, 250_000_000_000L, 1_000_000_000L, 100, Rarity.SECRET),

        ROT_WALKER("Гнилоход", EntityType.ITEM_DISPLAY, 9999999, 50000, 0.0, Rarity.EVENT);

        final String displayName;
        final EntityType entityType;
        final long price;
        final long incomePerSecond;
        final double weight;
        final Rarity rarity;

        MobData(String displayName, EntityType entityType, long price, long incomePerSecond, double weight, Rarity rarity) {
            this.displayName = displayName;
            this.entityType = entityType;
            this.price = price;
            this.incomePerSecond = incomePerSecond;
            this.weight = weight;
            this.rarity = rarity;
        }

        public boolean isFlyingBlock() {
            return this == SPONGE || this == ROT_WALKER;
        }

        /**
         * id блюпринта ModelEngine или null, если моб ванильный.
         * Держим отдельным методом, а не полем в конструкторе, чтобы не
         * переписывать все шесть десятков существующих строк enum'а.
         */
        public String modelEngineBlueprint() {
            return this == SAMOVARUS ? "samovarus_maximus" : null;
        }

        public double getEntityHeight() {
            return switch (this) {
                case STRAY -> 1.99; case HUSK -> 1.95; case RAVAGER -> 2.2; case IRON_GOLEM -> 2.7;
                case PHANTOM -> 0.5; case ENDERMAN -> 2.9;
                case HORSE, ZOMBIE_HORSE, SKELETON_HORSE, MYTHIC_SKELETON_HORSE -> 1.6;
                case POLAR_BEAR -> 1.4; case LLAMA -> 1.87; case PANDA, BROWN_PANDA -> 1.25;
                case COW, MOOSHROOM -> 1.4; case SHEEP -> 1.3; case PIG -> 0.9; case FOX -> 0.7;
                case WOLF -> 0.85; case CAT_KUZYA -> 0.7; case RABBIT -> 0.5;
                case PARROT -> 0.9; case TURTLE -> 0.4; case CHICKEN -> 0.7; case DOLPHIN -> 0.6;
                case BLAZE -> 1.8; case WITHER_SKELETON -> 2.4; case GUARDIAN -> 0.85;
                case ENDERMITE -> 0.3; case EVOKER, VINDICATOR, PILLAGER, WITCH, ILLUSIONER -> 1.95;
                case STRIDER -> 1.7; case VEX -> 0.8; case MAGMA_CUBE -> 2.04;
                case HOGLIN, ZOGLIN -> 1.4; case PIGLIN_BRUTE, PIGLIN, ZOMBIFIED_PIGLIN -> 1.95;
                case SILVERFISH -> 0.3; case CAVE_SPIDER -> 0.5; case SPIDER -> 0.9;
                case OCELOT -> 0.7; case BAT -> 0.9; case BEE -> 0.6; case CAMEL -> 2.375;
                case DROWNED -> 1.95; case SPONGE -> 1.5; case GOAT -> 1.3; case SNOW_GOLEM -> 1.9;
                case ALLAY -> 0.6; case SNIFFER -> 1.75; case WARDEN -> 2.9; case AXOLOTL -> 0.42;
                case FROG -> 0.55; case CREEPER -> 1.7; case GLOW_SQUID -> 0.8;
                case WANDERING_TRADER -> 1.95; case ELDER_GUARDIAN -> 1.9975;
                case ROT_WALKER -> 2.0;
                case SAMOVARUS -> 2.9;   // высота из кости hitbox блюпринта
                case ENDER_DRAGON -> 2.6;
                default -> 1.0;
            };
        }
    }

    private String getRainbowText(String text, int offset) {
        String[] colors = {"§c", "§6", "§e", "§a", "§b", "§9", "§d"};
        StringBuilder result = new StringBuilder();
        int colorIndex = offset % colors.length;
        for (char c : text.toCharArray()) {
            if (c == ' ') {
                result.append(' ');
            } else {
                result.append(colors[colorIndex]).append("§l").append(c);
                colorIndex = (colorIndex + 1) % colors.length;
            }
        }
        return result.toString();
    }

    private Mutation selectMutation() {
        double rand = random.nextDouble() * 100;
        double cumulative = 0;
        for (Mutation m : Mutation.values()) {
            cumulative += m.chance;
            if (rand <= cumulative) return m;
        }
        return Mutation.NONE;
    }

    private void setupFancyHolograms() {
        try {
            hologramManager = FancyHologramsPlugin.get().getHologramManager();
            getLogger().info("§a✓ FancyHolograms подключен!");
            for (SpawnerConfig config : spawnerConfigs.values()) {
                if (config.getHologramLoc() != null) {
                    createSpawnerHologram(config);
                }
            }
            startHologramUpdateTask();
        } catch (Exception e) {
            getLogger().warning("§c✗ FancyHolograms не найден или ошибка: " + e.getMessage());
            hologramManager = null;
        }
    }

    private void createSpawnerHologram(SpawnerConfig config) {
        if (hologramManager == null || config.getHologramLoc() == null) return;
        String holoName = "brainrot_timer_" + config.getId();
        removeSpawnerHologram(config.getId());
        try {
            Location loc = config.getHologramLoc().clone();
            loc.setYaw(loc.getYaw() + -90f);
            TextHologramData data = new TextHologramData(holoName, loc);
            data.setScale(new Vector3f(1.9f, 1.9f, 1.9f));
            data.setBillboard(Display.Billboard.FIXED);
            data.setBackground(Hologram.TRANSPARENT);
            data.setSeeThrough(false);
            data.setVisibilityDistance(100);
            List<String> lines = new ArrayList<>();
            lines.add("§fГарантированный §6§lЛегендарный");
            lines.add("§eЗагрузка...");
            lines.add("");
            lines.add("§fГарантированный §d§l✦ Мифический ✦");
            lines.add("§eЗагрузка...");
            data.setText(lines);
            Hologram hologram = hologramManager.create(data);
            hologramManager.addHologram(hologram);
            hologram.createHologram();
            spawnerHolograms.put(config.getId(), hologram);
            getLogger().info("§a✓ Голограмма создана для спавнера: " + config.getId());
        } catch (Exception e) {
            getLogger().severe("Ошибка создания голограммы: " + e.getMessage());
            org.bukkit.Bukkit.getLogger().warning("Brainrot: " + e.getMessage());
        }
    }

    private void removeSpawnerHologram(String spawnerId) {
        Hologram hologram = spawnerHolograms.remove(spawnerId);
        if (hologram != null && hologramManager != null) {
            try { hologramManager.removeHologram(hologram); } catch (Exception ignored) {}
        }
    }

    private void initializeTimers(String spawnerId) {
        legendaryTicksLeft.put(spawnerId, LEGENDARY_GUARANTEE_TICKS);
        mythicalTicksLeft.put(spawnerId, MYTHICAL_GUARANTEE_TICKS);
    }

    private void resetLegendaryTimer(String spawnerId) {
        legendaryTicksLeft.put(spawnerId, LEGENDARY_GUARANTEE_TICKS);
    }

    private void resetMythicalTimer(String spawnerId) {
        mythicalTicksLeft.put(spawnerId, MYTHICAL_GUARANTEE_TICKS);
    }

    private boolean isLegendaryGuaranteed(String spawnerId) {
        Integer ticks = legendaryTicksLeft.get(spawnerId);
        return ticks != null && ticks <= 0;
    }

    private boolean isMythicalGuaranteed(String spawnerId) {
        Integer ticks = mythicalTicksLeft.get(spawnerId);
        return ticks != null && ticks <= 0;
    }

    private void startHologramUpdateTask() {
        if (hologramUpdateTask != null) {
            try { hologramUpdateTask.cancel(); } catch (Exception ignored) {}
        }
        hologramUpdateTask = new BukkitRunnable() {
            private int tickCounter = 0;
            @Override
            public void run() {
                tickCounter++;
                for (String spawnerId : spawnerConfigs.keySet()) {
                    SpawnerConfig config = spawnerConfigs.get(spawnerId);
                    if (config == null || config.isPaused() || !hasPlayersInWorld(config.getWorldName())) continue;
                    legendaryTicksLeft.computeIfPresent(spawnerId, (k, v) -> Math.max(0, v - 1));
                    mythicalTicksLeft.computeIfPresent(spawnerId, (k, v) -> Math.max(0, v - 1));
                }
                if (tickCounter % 20 == 0) updateAllHolograms();
            }
        };
        hologramUpdateTask.runTaskTimer(this, 1L, 1L);
    }

    private void updateAllHolograms() {
        if (hologramManager == null) return;
        for (String spawnerId : spawnerHolograms.keySet()) {
            Hologram hologram = spawnerHolograms.get(spawnerId);
            if (hologram == null) continue;
            int legendaryTicks = legendaryTicksLeft.getOrDefault(spawnerId, LEGENDARY_GUARANTEE_TICKS);
            int mythicalTicks = mythicalTicksLeft.getOrDefault(spawnerId, MYTHICAL_GUARANTEE_TICKS);
            int legendarySecondsLeft = legendaryTicks / 20;
            int mythicalSecondsLeft = mythicalTicks / 20;
            String legendaryTime = formatTime(legendarySecondsLeft);
            String mythicalTime = formatTime(mythicalSecondsLeft);
            boolean blink = (System.currentTimeMillis() % 1000) < 500;
            String legendaryDisplay;
            if (legendarySecondsLeft <= 0) {
                legendaryDisplay = (blink ? "§a§l" : "§2§l") + "ГОТОВ!";
            } else if (legendarySecondsLeft <= 30) {
                legendaryDisplay = (blink ? "§c" : "§6") + legendaryTime;
            } else {
                legendaryDisplay = "§e" + legendaryTime;
            }
            String mythicalDisplay;
            if (mythicalSecondsLeft <= 0) {
                mythicalDisplay = (blink ? "§a§l" : "§2§l") + "ГОТОВ!";
            } else if (mythicalSecondsLeft <= 60) {
                mythicalDisplay = (blink ? "§c" : "§d") + mythicalTime;
            } else {
                mythicalDisplay = "§e" + mythicalTime;
            }
            List<String> lines = new ArrayList<>();
            lines.add("§fГарантированный §6§lЛегендарный");
            lines.add(legendaryDisplay);
            lines.add("");
            lines.add("§fГарантированный §d§l✦ Мифический ✦");
            lines.add(mythicalDisplay);
            try {
                if (hologram.getData() instanceof TextHologramData textData) {
                    textData.setText(lines);
                    hologram.refreshForViewers();
                }
            } catch (Exception ignored) {}
        }
    }

    private String formatTime(int totalSeconds) {
        if (totalSeconds <= 0) return "00:00";
        int minutes = totalSeconds / 60;
        int seconds = totalSeconds % 60;
        return String.format("%02d:%02d", minutes, seconds);
    }

    private Entity spawnLuckyBlockWithWings(Location loc, String spawnerId) {
        World world = loc.getWorld();
        ItemDisplay mainBlock = (ItemDisplay) world.spawnEntity(loc, EntityType.ITEM_DISPLAY);
        ItemStack mainItem = new ItemStack(Material.WHITE_DYE);
        ItemMeta mainMeta = mainItem.getItemMeta();
        mainMeta.setItemModel(NamespacedKey.fromString("animated_java:blueprint/luckyblock/bone"));
        mainItem.setItemMeta(mainMeta);
        mainBlock.setItemStack(mainItem);
        mainBlock.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.HEAD);
        mainBlock.setBillboard(Display.Billboard.FIXED);
        mainBlock.setTransformation(new Transformation(
            new Vector3f(0f, 0f, 0f),
            new AxisAngle4f(0, 0, 0, 1),
            new Vector3f(1f, 1f, 1f),
            new AxisAngle4f(0, 0, 0, 1)
        ));
        ItemDisplay leftWing = (ItemDisplay) world.spawnEntity(loc, EntityType.ITEM_DISPLAY);
        ItemStack leftItem = new ItemStack(Material.WHITE_DYE);
        ItemMeta leftMeta = leftItem.getItemMeta();
        leftMeta.setItemModel(NamespacedKey.fromString("animated_java:blueprint/luckyblock/wing_left"));
        leftItem.setItemMeta(leftMeta);
        leftWing.setItemStack(leftItem);
        leftWing.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.HEAD);
        leftWing.setBillboard(Display.Billboard.FIXED);
        ItemDisplay rightWing = (ItemDisplay) world.spawnEntity(loc, EntityType.ITEM_DISPLAY);
        ItemStack rightItem = new ItemStack(Material.WHITE_DYE);
        ItemMeta rightMeta = rightItem.getItemMeta();
        rightMeta.setItemModel(NamespacedKey.fromString("animated_java:blueprint/luckyblock/wing_right"));
        rightItem.setItemMeta(rightMeta);
        rightWing.setItemStack(rightItem);
        rightWing.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.HEAD);
        rightWing.setBillboard(Display.Billboard.FIXED);
        mainBlock.addScoreboardTag("LUCKY_BLOCK");
        mainBlock.addScoreboardTag("FLYING_BLOCK");
        mainBlock.addScoreboardTag("NO_DESPAWN");
        mainBlock.addScoreboardTag("MOB_" + MobData.SPONGE.name());
        mainBlock.addScoreboardTag("MOB_RARITY_" + Rarity.MYTHICAL.name());
        mainBlock.addScoreboardTag("SPAWNER_" + spawnerId);
        leftWing.addScoreboardTag("LUCKY_BLOCK_WING");
        leftWing.addScoreboardTag("NO_DESPAWN");
        rightWing.addScoreboardTag("LUCKY_BLOCK_WING");
        rightWing.addScoreboardTag("NO_DESPAWN");
        Interaction hitbox = (Interaction) world.spawnEntity(loc.clone().add(0, 0.5, 0), EntityType.INTERACTION);
        hitbox.setInteractionWidth(1.5f);
        hitbox.setInteractionHeight(1.5f);
        hitbox.addScoreboardTag("SPONGE_HITBOX");
        hitbox.addScoreboardTag("NO_DESPAWN");
        spongeHitboxMap.put(mainBlock, hitbox);
        luckyBlockWings.put(mainBlock, Arrays.asList(leftWing, rightWing));
        startLuckyBlockAnimation(mainBlock, leftWing, rightWing);
        return mainBlock;
    }

    private void startLuckyBlockAnimation(ItemDisplay mainBlock, ItemDisplay leftWing, ItemDisplay rightWing) {
        BukkitRunnable anim = new BukkitRunnable() {
            double time = 0;
            @Override
            public void run() {
                if (!mainBlock.isValid() || mainBlock.isDead()) {
                    cancel();
                    wingAnimations.remove(mainBlock);
                    return;
                }
                time += 0.1;
                float bobY = (float) (Math.sin(time * 2) * 0.05f);
                mainBlock.setTransformation(new Transformation(
                    new Vector3f(0f, bobY, 0f),
                    new AxisAngle4f(0, 0, 0, 1),
                    new Vector3f(1f, 1f, 1f),
                    new AxisAngle4f(0, 0, 0, 1)
                ));
                mainBlock.setInterpolationDelay(0);
                mainBlock.setInterpolationDuration(2);
                float flapAngle = (float) (Math.sin(time * 4) * 0.3f);
                if (leftWing != null && leftWing.isValid()) {
                    leftWing.setTransformation(new Transformation(
                        new Vector3f(0.5f, 0.7188f + bobY, 0.25f),
                        new AxisAngle4f(0, 0, 0, 1),
                        new Vector3f(1f, 1f, 1f),
                        new AxisAngle4f(0.19509399f + flapAngle, 0, 0.9807846f, 0)
                    ));
                    leftWing.setInterpolationDelay(0);
                    leftWing.setInterpolationDuration(2);
                }
                if (rightWing != null && rightWing.isValid()) {
                    rightWing.setTransformation(new Transformation(
                        new Vector3f(-0.5f, 0.7188f + bobY, 0.25f),
                        new AxisAngle4f(0, 0, 0, 1),
                        new Vector3f(1f, 1f, 1f),
                        new AxisAngle4f(0.19509399f + flapAngle, 0, -0.9807846f, 0)
                    ));
                    rightWing.setInterpolationDelay(0);
                    rightWing.setInterpolationDuration(2);
                }
            }
        };
        anim.runTaskTimer(this, 0L, 1L);
        wingAnimations.put(mainBlock, anim);
    }

    @Override
    public void onEnable() {
        instance = this;
        saveDefaultConfig();
        loadConfigSettings();
        setupEconomy();
        checkFloodgate();
        Bukkit.getPluginManager().registerEvents(this, this);
        try {
            if (getCommand("brainrotspawn") != null)
                getCommand("brainrotspawn").setExecutor(new BrainrotSpawnCommand());
            if (getCommand("brainrotspawner") != null)
                getCommand("brainrotspawner").setExecutor(new BrainrotSpawnerCommand());
        } catch (Exception e) {
            getLogger().warning("Ошибка регистрации команд: " + e.getMessage());
        }
        Bukkit.getScheduler().runTaskLater(this, () -> {
            for (SpawnerConfig config : spawnerConfigs.values()) {
                if (config.getSpawnLoc() != null && config.getSpawnLoc().getWorld() != null) {
                    config.getSpawnLoc().getChunk().load();
                }
                initializeTimers(config.getId());
            }
        }, 20L);
        Bukkit.getScheduler().runTaskLater(this, this::setupFancyHolograms, 40L);
        startAllSpawners();
        new BukkitRunnable() {
            @Override
            public void run() {
                for (SpawnerConfig config : spawnerConfigs.values()) {
                    if (!hasPlayersInWorld(config.getWorldName())) cleanupMobsInWorld(config.getWorldName());
                }
            }
        }.runTaskTimer(this, 200L, 200L);
        Bukkit.getScheduler().runTaskLater(this, () -> {
            for (Player player : Bukkit.getOnlinePlayers()) {
                if (isBedrockPlayer(player)) bedrockPlayerCache.add(player.getUniqueId());
            }
        }, 40L);
        logMobChances();
        Bukkit.getScheduler().runTaskLater(this, this::cleanupOrphanDragonRigs, 60L);
    }

    // После рестарта задачи движения не восстанавливаются, а мобы persistent — дракон и его
    // носитель остались бы висеть в мире навсегда. Чистим обоих на старте.
    private void cleanupOrphanDragonRigs() {
        int removed = 0;
        for (SpawnerConfig config : spawnerConfigs.values()) {
            World world = Bukkit.getWorld(config.getWorldName());
            if (world == null) continue;
            for (Entity e : new ArrayList<>(world.getEntities())) {
                boolean carrier = e.getScoreboardTags().contains(DRAGON_CARRIER_TAG);
                boolean staleDragon = e.getType() == EntityType.ENDER_DRAGON
                        && e.getScoreboardTags().contains("MOB_ENDER_DRAGON")
                        && !isBaseMobEntity(e)
                        && !mobDataMap.containsKey(e);
                if (!carrier && !staleDragon) continue;
                try { e.eject(); } catch (Throwable ignored) {}
                try { e.remove(); removed++; } catch (Throwable ignored) {}
            }
        }
        if (removed > 0) getLogger().info("[BRAINROT] Убрано зависших сущностей дракона: " + removed);
    }

    private MobData selectRandomMob() {
        Rarity selectedRarity = selectRarity();
        MobData mob = selectMobFromRarity(selectedRarity);
        return mob != null ? mob : MobData.CHICKEN;
    }

    private boolean hasMobs(Rarity rarity) {
        for (MobData mob : MobData.values()) {
            if (mob.rarity == rarity && mob.weight > 0) return true;
        }
        return false;
    }

    private Rarity selectRarity() {
        double totalChance = 0;
        for (Rarity r : Rarity.values()) {
            if (r.chance > 0 && hasMobs(r)) totalChance += r.chance;
        }
        if (totalChance <= 0) return Rarity.COMMON;
        double rand = random.nextDouble() * totalChance;
        double cumulative = 0;
        for (Rarity r : Rarity.values()) {
            if (r.chance <= 0 || !hasMobs(r)) continue;
            cumulative += r.chance;
            if (rand <= cumulative) return r;
        }
        return Rarity.COMMON;
    }

    private MobData selectMobFromRarity(Rarity rarity) {
        List<MobData> mobsInRarity = new ArrayList<>();
        double totalWeight = 0;
        for (MobData mob : MobData.values()) {
            if (mob.rarity == rarity && mob.weight > 0) {
                mobsInRarity.add(mob);
                totalWeight += mob.weight;
            }
        }
        if (mobsInRarity.isEmpty() || totalWeight <= 0) return null;
        double rand = random.nextDouble() * totalWeight;
        double cumulative = 0;
        for (MobData mob : mobsInRarity) {
            cumulative += mob.weight;
            if (rand <= cumulative) return mob;
        }
        return mobsInRarity.get(0);
    }

    private void createNameTags(Entity mob, MobData data, double baseHeight, Mutation mutation) {
        createNameTags(mob, data, baseHeight, mutation, getExtraMutations(mob));
    }

    private void createNameTags(Entity mob, MobData data, double baseHeight, Mutation mutation, boolean snowy) {
        createNameTags(mob, data, baseHeight, mutation, snowy ? List.of(Mutation.SNOWY) : List.of());
    }

    private void createNameTags(Entity mob, MobData data, double baseHeight, Mutation mutation, List<Mutation> extras) {
        List<ArmorStand> tags = new ArrayList<>();
        Location baseLoc = mob.getLocation().clone();
        String[] lines = getNameTagLines(data, mutation, extras);
        for (int i = 0; i < lines.length; i++) {
            double yOffset = baseHeight + ((lines.length - 1 - i) * NAME_TAG_LINE_HEIGHT);
            Location tagLoc = baseLoc.clone().add(0, yOffset, 0);
            ArmorStand tag = (ArmorStand) mob.getWorld().spawnEntity(tagLoc, EntityType.ARMOR_STAND);
            tag.setVisible(false);
            tag.setGravity(false);
            tag.setInvulnerable(true);
            tag.setSilent(true);
            tag.setCollidable(false);
            tag.setSmall(true);
            tag.setMarker(true);
            tag.setBasePlate(false);
            tag.setCustomName(lines[i]);
            tag.setCustomNameVisible(true);
            tag.addScoreboardTag("NAME_TAG");
            tag.addScoreboardTag("NO_DESPAWN");
            tags.add(tag);
        }
        mobNameTags.put(mob, tags);
    }

    private String[] getNameTagLines(MobData data, Mutation baseMutation, boolean snowy) {
        return getNameTagLines(data, baseMutation, snowy ? List.of(Mutation.SNOWY) : List.of());
    }

    private String[] getNameTagLines(MobData data, Mutation baseMutation, List<Mutation> extras) {
        if (extras == null) extras = List.of();
        String namePrefix = "";
        String priceSuffix = "§6";
        if (data.rarity == Rarity.MYTHICAL) {
            namePrefix = "§d✦ ";
            priceSuffix = "§d";
        }
        if (data.rarity == Rarity.BRAINROT_GOD) {
            namePrefix = "§b✧ ";
            priceSuffix = "§b";
        }
        if (data.rarity == Rarity.SECRET) {
            namePrefix = "§8☠ ";
            priceSuffix = "§8";
        }
        if (data.rarity == Rarity.EVENT) {
            namePrefix = "§2☣ ";
            priceSuffix = "§2";
        }
        double mult = (baseMutation != null ? baseMutation.incomeMultiplier : 1.0);
        for (Mutation extra : extras) mult *= extra.incomeMultiplier;
        long actualIncome = Math.round(data.incomePerSecond * mult);
        String nameLine = namePrefix + "§f" + data.displayName + (data.rarity == Rarity.MYTHICAL ? " §d✦" : data.rarity == Rarity.BRAINROT_GOD ? " §b✧" : data.rarity == Rarity.SECRET ? " §8☠" : "");
        String rarityLine = data.rarity.format + data.rarity.displayName;
        String incomeLine = "§a+" + formatNumber(actualIncome) + "§2$§a/сек";
        String priceLine = priceSuffix + formatNumber(data.price) + "$";
        List<String> out = new ArrayList<>();
        for (Mutation extra : extras) out.add(extra.format + extra.displayName);
        if (baseMutation != null && baseMutation != Mutation.NONE) {
            if (baseMutation == Mutation.RAINBOW) out.add("§fРадужный");
            else out.add(baseMutation.format + baseMutation.displayName);
        }
        out.add(nameLine);
        out.add(rarityLine);
        out.add(incomeLine);
        out.add(priceLine);
        return out.toArray(new String[0]);
    }

    private void startRainbowAnimation(Entity mob, MobData data) {
        startRainbowAnimation(mob, data, getExtraMutations(mob));
    }

    private void startRainbowAnimation(Entity mob, MobData data, boolean snowy) {
        startRainbowAnimation(mob, data, snowy ? List.of(Mutation.SNOWY) : List.of());
    }

    private void startRainbowAnimation(Entity mob, MobData data, List<Mutation> extras) {
        final List<Mutation> extraList = (extras == null) ? List.of() : extras;
        List<ArmorStand> tags = mobNameTags.get(mob);
        if (tags == null || tags.isEmpty()) return;
        int rainbowIndex = extraList.size();
        int incomeIndex = tags.size() - 2;
        ArmorStand rainbowTag = (rainbowIndex < tags.size()) ? tags.get(rainbowIndex) : null;
        ArmorStand incomeTag = (incomeIndex < tags.size()) ? tags.get(incomeIndex) : null;
        double mult = Mutation.RAINBOW.incomeMultiplier;
        StringBuilder extraSuffix = new StringBuilder();
        for (Mutation extra : extraList) {
            mult *= extra.incomeMultiplier;
            extraSuffix.append(" §7+ ").append(extra.format).append("×")
                    .append(trimMultiplier(extra.incomeMultiplier));
        }
        final String extraSuffixStr = extraSuffix.toString();
        long actualIncome = Math.round(data.incomePerSecond * mult);
        BukkitRunnable animTask = new BukkitRunnable() {
            int tick = 0;
            @Override
            public void run() {
                if (!mob.isValid() || mob.isDead() || !mobNameTags.containsKey(mob)) {
                    cancel();
                    rainbowAnimationTasks.remove(mob);
                    return;
                }
                int offset = tick % 7;
                if (rainbowTag != null && rainbowTag.isValid()) {
                    rainbowTag.setCustomName(getRainbowText("Радужный", offset));
                }
                String incomeLine = "§a+" + formatNumber(actualIncome) + "§2$§a/сек §7(" + getRainbowText("×10", offset) + "§7)";
                incomeLine += extraSuffixStr;
                if (incomeTag != null && incomeTag.isValid()) {
                    incomeTag.setCustomName(incomeLine);
                }
                tick++;
            }
        };
        animTask.runTaskTimer(this, 0L, 2L);
        rainbowAnimationTasks.put(mob, animTask);
    }

    private void updateNameTagsPosition(Entity mob, Location newLoc, double baseHeight) {
        List<ArmorStand> tags = mobNameTags.get(mob);
        if (tags == null || tags.isEmpty()) return;
        int lineCount = tags.size();
        for (int i = 0; i < lineCount; i++) {
            ArmorStand tag = tags.get(i);
            if (tag != null && tag.isValid()) {
                double yOffset = baseHeight + ((lineCount - 1 - i) * NAME_TAG_LINE_HEIGHT);
                tag.teleport(newLoc.clone().add(0, yOffset, 0));
            }
        }
    }

    private void removeNameTags(Entity mob) {
        List<ArmorStand> tags = mobNameTags.remove(mob);
        if (tags != null) for (ArmorStand tag : tags) if (tag != null && tag.isValid()) tag.remove();
    }

    private void applyMutationVisual(Entity mob, Mutation mutation) {
        if (mutation == null || mutation == Mutation.NONE) return;
        mob.addScoreboardTag("MUTATION_" + mutation.name());
    }

    // Мутации, которые стакаются с базовой (выдаются ивентами, а не при спавне).
    private static final List<Mutation> STACKABLE_MUTATIONS =
            List.of(Mutation.SNOWY, Mutation.ELECTRIC, Mutation.METEOR, Mutation.EXPLOSIVE);

    /** Порядок фиксирован (Снежный, Электрический, Метеоритный, Взрывной) — от него зависит порядок строк нейм-тега. */
    private List<Mutation> getExtraMutations(Entity mob) {
        if (mob == null) return List.of();
        Set<String> tags = mob.getScoreboardTags();
        List<Mutation> out = new ArrayList<>();
        for (Mutation m : STACKABLE_MUTATIONS) if (tags.contains("MUTATION_" + m.name())) out.add(m);
        return out;
    }

    private String extrasKey(Entity mob) {
        StringBuilder sb = new StringBuilder();
        for (Mutation m : getExtraMutations(mob)) sb.append(m.name()).append(',');
        return sb.toString();
    }

    private static String trimMultiplier(double mult) {
        if (mult == Math.rint(mult)) return String.valueOf((long) mult);
        return String.valueOf(mult);
    }

    private void tickMutationParticles(Entity mob, Mutation mutation, long tick) {
        if (mutation == null || mutation == Mutation.NONE) return;
        Location p = mob.getLocation().add(0, 0.8, 0);
        switch (mutation) {
            case GOLD -> {
                if (tick % 6 == 0)
                    mob.getWorld().spawnParticle(Particle.DUST, p, 2, 0.25, 0.25, 0.25, 0,
                            new Particle.DustOptions(Color.fromRGB(255, 210, 40), 1.0f));
            }
            case DIAMOND -> {
                if (tick % 6 == 0)
                    mob.getWorld().spawnParticle(Particle.DUST, p, 2, 0.25, 0.25, 0.25, 0,
                            new Particle.DustOptions(Color.fromRGB(80, 255, 255), 1.0f));
            }
            case SNOWY -> {
                if (tick % 4 == 0)
                    mob.getWorld().spawnParticle(Particle.SNOWFLAKE, p, 2, 0.25, 0.25, 0.25, 0.0);
            }
            case ELECTRIC -> {
                if (tick % 3 == 0)
                    mob.getWorld().spawnParticle(Particle.ELECTRIC_SPARK, p, 4, 0.3, 0.35, 0.3, 0.02);
            }
            case METEOR -> {
                if (tick % 3 == 0)
                    mob.getWorld().spawnParticle(Particle.FLAME, p, 2, 0.28, 0.3, 0.28, 0.005);
                if (tick % 10 == 0) {
                    mob.getWorld().spawnParticle(Particle.LAVA, p, 1, 0.2, 0.2, 0.2, 0.0);
                    mob.getWorld().spawnParticle(Particle.LARGE_SMOKE, p.clone().add(0, 0.3, 0), 1, 0.2, 0.1, 0.2, 0.01);
                }
            }
            case EXPLOSIVE -> {
                if (tick % 4 == 0)
                    mob.getWorld().spawnParticle(Particle.DUST, p, 3, 0.28, 0.3, 0.28, 0,
                            new Particle.DustOptions(Color.fromRGB(60, 220, 90), 1.0f));
                if (tick % 12 == 0)
                    mob.getWorld().spawnParticle(Particle.EXPLOSION, p.clone().add(0, 0.3, 0), 1, 0.15, 0.1, 0.15, 0.0);
            }
            case RAINBOW -> {
                if (tick % 2 == 0) {
                    Color[] colors = {Color.RED, Color.ORANGE, Color.YELLOW, Color.GREEN, Color.AQUA, Color.BLUE, Color.PURPLE};
                    Color c = colors[(int) ((System.currentTimeMillis() / 120) % colors.length)];
                    mob.getWorld().spawnParticle(Particle.DUST, p, 2, 0.25, 0.25, 0.25, 0,
                            new Particle.DustOptions(c, 1.0f));
                }
            }
        }
    }

    private void checkFloodgate() {
        try {
            Class.forName("org.geysermc.floodgate.api.FloodgateApi");
            floodgateAvailable = true;
            getLogger().info("§b✓ Floodgate найден");
        } catch (ClassNotFoundException e) { floodgateAvailable = false; }
    }

    private boolean isBedrockPlayer(Player player) {
        if (player == null) return false;
        if (bedrockPlayerCache.contains(player.getUniqueId())) return true;
        String uuid = player.getUniqueId().toString();
        if (uuid.startsWith("00000000-0000-0000")) { bedrockPlayerCache.add(player.getUniqueId()); return true; }
        String name = player.getName();
        if (name.startsWith(".") || name.startsWith("*")) { bedrockPlayerCache.add(player.getUniqueId()); return true; }
        if (floodgateAvailable) {
            try {
                Class<?> api = Class.forName("org.geysermc.floodgate.api.FloodgateApi");
                Object inst = api.getMethod("getInstance").invoke(null);
                Object result = api.getMethod("isFloodgatePlayer", UUID.class).invoke(inst, player.getUniqueId());
                if (result instanceof Boolean && (Boolean) result) { bedrockPlayerCache.add(player.getUniqueId()); return true; }
            } catch (Exception ignored) { floodgateAvailable = false; }
        }
        return false;
    }

    private void loadConfigSettings() {
        FileConfiguration cfg = getConfig();
        if (!cfg.contains("dragon.yaw-offset")) {
            cfg.set("dragon.yaw-offset", -90);
            saveConfig();
        }
        if (!cfg.contains("dragon.yaw-invert")) {
            cfg.set("dragon.yaw-invert", false);
            saveConfig();
        }
        dragonYawOffset = (float) cfg.getDouble("dragon.yaw-offset", -90);
        dragonYawInvert = cfg.getBoolean("dragon.yaw-invert", false);
        if (cfg.contains("spawners")) {
            for (String id : cfg.getConfigurationSection("spawners").getKeys(false)) {
                String path = "spawners." + id + ".";
                String worldName = cfg.getString(path + "world", "world");
                SpawnerConfig config = new SpawnerConfig(id, worldName);
                if (cfg.contains(path + "spawn.x")) {
                    World w = Bukkit.getWorld(worldName);
                    if (w != null) config.setSpawnLoc(new Location(w, cfg.getDouble(path + "spawn.x"), cfg.getDouble(path + "spawn.y"), cfg.getDouble(path + "spawn.z")));
                }
                if (cfg.contains(path + "despawn.x")) {
                    World w = Bukkit.getWorld(worldName);
                    if (w != null) config.setDespawnLoc(new Location(w, cfg.getDouble(path + "despawn.x"), cfg.getDouble(path + "despawn.y"), cfg.getDouble(path + "despawn.z")));
                }
                if (cfg.contains(path + "hologram.x")) {
                    World w = Bukkit.getWorld(worldName);
                    if (w != null) {
                        Location holoLoc = new Location(w,
                            cfg.getDouble(path + "hologram.x"),
                            cfg.getDouble(path + "hologram.y"),
                            cfg.getDouble(path + "hologram.z"),
                            (float) cfg.getDouble(path + "hologram.yaw", 0), 0);
                        config.setHologramLoc(holoLoc);
                    }
                }
                config.setSpeed(cfg.getDouble(path + "speed", 0.2));
                config.setDirection(cfg.getString(path + "direction", "forward"));
                config.setCooldownTicks(cfg.getLong(path + "cooldown", 30) * 20);
                config.setEnabled(cfg.getBoolean(path + "enabled", true));
                config.setPaused(cfg.getBoolean(path + "paused", false));
                spawnerConfigs.put(id, config);
                spawnQueues.put(id, new LinkedList<>());
            }
        }
        if (spawnerConfigs.isEmpty()) {
            SpawnerConfig config = new SpawnerConfig("main", Bukkit.getWorlds().get(0).getName());
            spawnerConfigs.put("main", config);
            spawnQueues.put("main", new LinkedList<>());
        }
    }

    private void saveSpawnerConfig(SpawnerConfig config) {
        String path = "spawners." + config.getId() + ".";
        getConfig().set(path + "world", config.getWorldName());
        if (config.getSpawnLoc() != null) {
            getConfig().set(path + "spawn.x", config.getSpawnLoc().getX());
            getConfig().set(path + "spawn.y", config.getSpawnLoc().getY());
            getConfig().set(path + "spawn.z", config.getSpawnLoc().getZ());
        }
        if (config.getDespawnLoc() != null) {
            getConfig().set(path + "despawn.x", config.getDespawnLoc().getX());
            getConfig().set(path + "despawn.y", config.getDespawnLoc().getY());
            getConfig().set(path + "despawn.z", config.getDespawnLoc().getZ());
        }
        if (config.getHologramLoc() != null) {
            getConfig().set(path + "hologram.x", config.getHologramLoc().getX());
            getConfig().set(path + "hologram.y", config.getHologramLoc().getY());
            getConfig().set(path + "hologram.z", config.getHologramLoc().getZ());
            getConfig().set(path + "hologram.yaw", config.getHologramLoc().getYaw());
        }
        getConfig().set(path + "speed", config.getSpeed());
        getConfig().set(path + "direction", config.getDirection());
        getConfig().set(path + "cooldown", config.getCooldownTicks() / 20);
        getConfig().set(path + "enabled", config.isEnabled());
        getConfig().set(path + "paused", config.isPaused());
        saveConfig();
    }

    private void startAllSpawners() {
        for (String id : spawnerConfigs.keySet()) {
            SpawnerConfig config = spawnerConfigs.get(id);
            if (config.isEnabled() && config.isValid() && !config.isPaused()) startSpawner(id);
        }
    }

    private void startSpawner(String id) {
        SpawnerConfig config = spawnerConfigs.get(id);
        if (config == null || !config.isValid()) return;
        stopSpawner(id);
        if (config.getSpawnLoc() != null) config.getSpawnLoc().getChunk().load();
        BukkitRunnable task = new BukkitRunnable() {
            @Override public void run() {
                if (!config.isEnabled() || config.isPaused()) return;
                if (hasPlayersInWorld(config.getWorldName())) spawnBrainrot(id);
            }
        };
        task.runTaskTimer(this, config.getCooldownTicks(), config.getCooldownTicks());
        spawnerTasks.put(id, task);
    }

    private void stopSpawner(String id) {
        BukkitRunnable task = spawnerTasks.remove(id);
        if (task != null) try { task.cancel(); } catch (Exception ignored) {}
    }

    private void restartSpawner(String id) {
        stopSpawner(id);
        SpawnerConfig config = spawnerConfigs.get(id);
        if (config != null && config.isEnabled() && config.isValid() && !config.isPaused()) startSpawner(id);
    }

    private void spawnBrainrot(String spawnerId) {
        SpawnerConfig config = spawnerConfigs.get(spawnerId);
        if (config == null || !config.isValid() || config.isPaused()) return;
        spawnCount++;
        Location spawnLoc = config.getSpawnLoc().clone();
        spawnLoc.getChunk().load();
        MobData selectedMob = null;
        Deque<MobData> queue = spawnQueues.get(spawnerId);
        if (queue != null && !queue.isEmpty()) selectedMob = queue.poll();
        if (selectedMob == null) {
            if (isMythicalGuaranteed(spawnerId)) {
                selectedMob = selectMobFromRarity(Rarity.MYTHICAL);
                if (selectedMob == null) selectedMob = selectRandomMob();
                resetMythicalTimer(spawnerId);
                for (Player p : Bukkit.getOnlinePlayers()) {
                    if (p.getWorld().getName().equals(config.getWorldName())) {
                        p.sendMessage("§d§l✦ ГАРАНТИРОВАННЫЙ МИФИЧЕСКИЙ! ✦");
                        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1f);
                    }
                }
            } else if (isLegendaryGuaranteed(spawnerId)) {
                selectedMob = selectMobFromRarity(Rarity.LEGENDARY);
                if (selectedMob == null) selectedMob = selectRandomMob();
                resetLegendaryTimer(spawnerId);
                for (Player p : Bukkit.getOnlinePlayers()) {
                    if (p.getWorld().getName().equals(config.getWorldName())) {
                        p.sendMessage("§6§l★ ГАРАНТИРОВАННЫЙ ЛЕГЕНДАРНЫЙ! ★");
                        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.2f);
                    }
                }
            } else {
                selectedMob = selectRandomMob();
            }
        }
        if (selectedMob == null) return;
        final Mutation mutation = selectMutation();
        if (selectedMob.isFlyingBlock()) {
            final MobData mobType = selectedMob;
            final Mutation mut = mutation;
            if (mobType == MobData.ROT_WALKER) {
                spawnRotWalkerAnimated(spawnLoc, spawnerId, (Entity mob) -> {
                    if (mob == null) return;
                    double nameTagHeight = 2.2;
                    mobDataMap.put(mob, mobType);
                    mobToSpawner.put(mob, spawnerId);
                    mobHoloHeights.put(mob, nameTagHeight);
                    mobMutations.put(mob, mut);
                    createNameTags(mob, mobType, nameTagHeight, mut);
                    applyMutationVisual(mob, mut);
                    if (mut == Mutation.RAINBOW) startRainbowAnimation(mob, mobType);
                    spawnRarityEffects(mob, mobType);
                    startMobMovement(mob, nameTagHeight, config);
                });
            } else {
                spawnLuckyBlockAnimated(spawnLoc, spawnerId, (Entity mob) -> {
                    if (mob == null) return;
                    double nameTagHeight = 2.0;
                    mobDataMap.put(mob, mobType);
                    mobToSpawner.put(mob, spawnerId);
                    mobHoloHeights.put(mob, nameTagHeight);
                    mobMutations.put(mob, mut);
                    createNameTags(mob, mobType, nameTagHeight, mut);
                    applyMutationVisual(mob, mut);
                    if (mut == Mutation.RAINBOW) startRainbowAnimation(mob, mobType);
                    spawnRarityEffects(mob, mobType);
                    startMobMovement(mob, nameTagHeight, config);
                });
            }
            return;
        }
        try {
            Entity mob = spawnLoc.getWorld().spawnEntity(spawnLoc, selectedMob.entityType);
            setupMob(mob, selectedMob);
            String blueprint = selectedMob.modelEngineBlueprint();
            if (blueprint != null && ModelEngineHook.attach(mob, blueprint)) {
                // spawn — это падение сверху с приседанием на удар, после него
                // уходим в walk. Моб всё время едет по прямой, так что walk
                // просто крутится в цикле и переключать его больше не нужно.
                ModelEngineHook.playForced(mob, "spawn");
                final Entity meMob = mob;
                Bukkit.getScheduler().runTaskLater(this, () -> {
                    if (meMob.isValid() && !meMob.isDead()) ModelEngineHook.play(meMob, "walk");
                }, 30L);
            }
            if (selectedMob == MobData.ENDER_DRAGON) {
                // Ставим разворот в тот же тик, что и спавн: клиент получит его сразу
                // в пакете добавления сущности, дальше он поддерживается в moveDragonRig.
                applyDragonYaw(mob, getYawFromDirection(config.getDirection()));
            }
            double nameTagHeight = selectedMob.getEntityHeight() + 0.3;
            mobHoloHeights.put(mob, nameTagHeight);
            mobMutations.put(mob, mutation);
            createNameTags(mob, selectedMob, nameTagHeight, mutation);
            applyMutationVisual(mob, mutation);
            if (mutation == Mutation.RAINBOW) startRainbowAnimation(mob, selectedMob);
            spawnRarityEffects(mob, selectedMob);
            mobDataMap.put(mob, selectedMob);
            mobToSpawner.put(mob, spawnerId);
            mob.addScoreboardTag("SPAWNER_" + spawnerId);
            startMobMovement(mob, nameTagHeight, config);
        } catch (Exception e) {
            getLogger().severe("Ошибка спавна: " + e.getMessage());
            org.bukkit.Bukkit.getLogger().warning("Brainrot: " + e.getMessage());
        }
    }

    private void spawnLuckyBlockAnimated(Location loc, String spawnerId, Consumer<Entity> onReady) {
        final Location at = loc.clone();
        final World world = at.getWorld();
        if (world == null) { onReady.accept(null); return; }
        Player p = world.getPlayers().stream().findFirst().orElse(null);
        if (p == null) { onReady.accept(null); return; }
        String summonCmd = String.format(Locale.US,
                "execute as %s positioned %.3f %.3f %.3f run function animated_java:luckyblock/summon {args:{}}",
                p.getName(), at.getX(), at.getY(), at.getZ());
        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), summonCmd);
        new BukkitRunnable() {
            int tries = 0;
            @Override public void run() {
                tries++;
                Entity root = null;
                double best = Double.MAX_VALUE;
                for (Entity e : world.getNearbyEntities(at, 3, 3, 3)) {
                    if (e.getType() != EntityType.ITEM_DISPLAY) continue;
                    if (!e.getScoreboardTags().contains("aj.luckyblock.root")) continue;
                    if (e.getPassengers().isEmpty()) continue;
                    double d = e.getLocation().distanceSquared(at);
                    if (d < best) { best = d; root = e; }
                }
                if (root == null) {
                    if (tries >= 60) {
                        try { // __fix__ kill orphan model on summon timeout
                            String dim = world.getKey().toString();
                            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), String.format(Locale.US, "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[type=item_display,tag=aj.luckyblock.root,distance=..2]", dim, at.getX(), at.getY(), at.getZ()));
                            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), String.format(Locale.US, "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[tag=aj.luckyblock.entity,distance=..3]", dim, at.getX(), at.getY(), at.getZ()));
                        } catch (Throwable __t) {}
                        onReady.accept(null); cancel();
                    }
                    return;
                }
                if (root instanceof Display dr) dr.setTeleportDuration(0);
                for (Entity pass : root.getPassengers()) {
                    if (pass instanceof Display dp) dp.setTeleportDuration(0);
                }
                String uniq = "brlb_" + root.getUniqueId().toString().replace("-", "");
                root.addScoreboardTag(uniq);
                String tagGroupCmd = "execute as @e[type=item_display,tag=" + uniq + ",limit=1] at @s " +
                        "run tag @e[tag=aj.luckyblock.entity,distance=..3] add " + uniq;
                Bukkit.dispatchCommand(Bukkit.getConsoleSender(), tagGroupCmd);
                root.addScoreboardTag("FLYING_BLOCK");
                root.addScoreboardTag("NO_DESPAWN");
                root.addScoreboardTag("MOB_" + MobData.SPONGE.name());
                root.addScoreboardTag("MOB_RARITY_" + Rarity.MYTHICAL.name());
                root.addScoreboardTag("SPAWNER_" + spawnerId);
                root.addScoreboardTag("LUCKY_BLOCK_ANIMATED");
                Interaction hitbox = (Interaction) world.spawnEntity(at.clone().add(0, 0.75, 0), EntityType.INTERACTION);
                hitbox.setInteractionWidth(1.5f);
                hitbox.setInteractionHeight(1.5f);
                hitbox.addScoreboardTag("SPONGE_HITBOX");
                hitbox.addScoreboardTag("NO_DESPAWN");
                hitbox.addScoreboardTag("MOB_" + MobData.SPONGE.name());
                hitbox.addScoreboardTag("SPAWNER_" + spawnerId);
                spongeHitboxMap.put(root, hitbox);
                Bukkit.getScheduler().runTaskLater(BrainrotSpawner.this, () -> {
                    String dim = world.getKey().toString();
                    String playCmd = "execute in " + dim +
                            " as @e[type=item_display,tag=aj.luckyblock.root,tag=" + uniq + ",limit=1] at @s " +
                            "run function animated_java:luckyblock/animations/wings_move/play";
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(), playCmd);
                }, 2L);
                onReady.accept(root);
                cancel();
            }
        }.runTaskTimer(this, 1L, 1L);
    }

    private void spawnRotWalkerAnimated(Location loc, String spawnerId, Consumer<Entity> onReady) {
        final Location at = loc.clone();
        final World world = at.getWorld();
        if (world == null) { onReady.accept(null); return; }
        Player p = world.getPlayers().stream().findFirst().orElse(null);
        if (p == null) { onReady.accept(null); return; }
        String summonCmd = String.format(Locale.US,
                "execute as %s positioned %.3f %.3f %.3f run function animated_java:rotwalker/summon {args:{}}",
                p.getName(), at.getX(), at.getY(), at.getZ());
        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), summonCmd);
        new BukkitRunnable() {
            int tries = 0;
            @Override public void run() {
                tries++;
                Entity root = null;
                double best = Double.MAX_VALUE;
                for (Entity e : world.getNearbyEntities(at, 3, 3, 3)) {
                    if (e.getType() != EntityType.ITEM_DISPLAY) continue;
                    if (!e.getScoreboardTags().contains(ROT_WALKER_ROOT_TAG)) continue;
                    if (e.getScoreboardTags().stream().anyMatch(t -> t.startsWith("brw_"))) continue;
                    double d = e.getLocation().distanceSquared(at);
                    if (d < best) { best = d; root = e; }
                }
                if (root == null) {
                    if (tries >= 60) {
                        try { // __fix__ kill orphan model on summon timeout
                            String dim = world.getKey().toString();
                            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), String.format(Locale.US, "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[type=item_display,tag=" + ROT_WALKER_ROOT_TAG + ",distance=..2]", dim, at.getX(), at.getY(), at.getZ()));
                            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), String.format(Locale.US, "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[tag=" + ROT_WALKER_ENTITY_TAG + ",distance=..3]", dim, at.getX(), at.getY(), at.getZ()));
                        } catch (Throwable __t) {}
                        onReady.accept(null); cancel();
                    }
                    return;
                }
                if (root instanceof Display dr) dr.setTeleportDuration(0);
                for (Entity pass : root.getPassengers()) {
                    if (pass instanceof Display dp) dp.setTeleportDuration(0);
                }
                String uniq = "brw_" + root.getUniqueId().toString().replace("-", "");
                root.addScoreboardTag(uniq);
                String tagGroupCmd = "execute as @e[type=item_display,tag=" + uniq + ",limit=1] at @s " +
                        "run tag @e[tag=" + ROT_WALKER_ENTITY_TAG + ",distance=..3] add " + uniq;
                Bukkit.dispatchCommand(Bukkit.getConsoleSender(), tagGroupCmd);
                root.addScoreboardTag("FLYING_BLOCK");
                root.addScoreboardTag("NO_DESPAWN");
                root.addScoreboardTag("MOB_" + MobData.ROT_WALKER.name());
                root.addScoreboardTag("MOB_RARITY_" + Rarity.EVENT.name());
                root.addScoreboardTag("SPAWNER_" + spawnerId);
                root.addScoreboardTag("ROT_WALKER_ANIMATED");
                Interaction hitbox = (Interaction) world.spawnEntity(at.clone().add(0, 0.75, 0), EntityType.INTERACTION);
                hitbox.setInteractionWidth(1.2f);
                hitbox.setInteractionHeight(2.0f);
                hitbox.addScoreboardTag("SPONGE_HITBOX");
                hitbox.addScoreboardTag("NO_DESPAWN");
                hitbox.addScoreboardTag("MOB_" + MobData.ROT_WALKER.name());
                hitbox.addScoreboardTag("SPAWNER_" + spawnerId);
                spongeHitboxMap.put(root, hitbox);
                rotWalkerHitboxMap.put(root, hitbox);
                world.spawnParticle(Particle.HAPPY_VILLAGER, at.clone().add(0, 1, 0), 30, 0.5, 0.8, 0.5, 0.05);
                world.playSound(at, Sound.ENTITY_ENDERMAN_TELEPORT, 0.8f, 0.5f);
                Bukkit.getScheduler().runTaskLater(BrainrotSpawner.this, () -> {
                    String dim = world.getKey().toString();
                    String playCmd = "execute in " + dim +
                            " as @e[type=item_display,tag=" + ROT_WALKER_ROOT_TAG + ",tag=" + uniq + ",limit=1] at @s " +
                            "run function animated_java:rotwalker/animations/animation_rotwalker_walk/play";
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(), playCmd);
                }, 2L);
                onReady.accept(root);
                cancel();
            }
        }.runTaskTimer(this, 1L, 1L);
    }

    private void spawnRarityEffects(Entity mob, MobData data) {
        if (data.rarity == Rarity.SECRET) {
            mob.getWorld().spawnParticle(Particle.FIREWORK, mob.getLocation().add(0, 1, 0), 100, 0.9, 0.9, 0.9, 0.2);
            mob.getWorld().spawnParticle(Particle.SOUL_FIRE_FLAME, mob.getLocation().add(0, 1.5, 0), 60, 0.6, 0.8, 0.6, 0.05);
            mob.getWorld().playSound(mob.getLocation(), Sound.ENTITY_ENDER_DRAGON_GROWL, 1.0f, 1.4f);
        } else if (data.rarity == Rarity.BRAINROT_GOD) {
            mob.getWorld().spawnParticle(Particle.FIREWORK, mob.getLocation().add(0, 1, 0), 70, 0.8, 0.8, 0.8, 0.18);
            mob.getWorld().spawnParticle(Particle.END_ROD, mob.getLocation().add(0, 1.5, 0), 45, 0.6, 0.6, 0.6, 0.12);
            mob.getWorld().playSound(mob.getLocation(), Sound.ENTITY_WITHER_SPAWN, 0.7f, 1.6f);
        } else if (data.rarity == Rarity.MYTHICAL) {
            mob.getWorld().spawnParticle(Particle.FIREWORK, mob.getLocation().add(0, 1, 0), 50, 0.7, 0.7, 0.7, 0.15);
            mob.getWorld().spawnParticle(Particle.END_ROD, mob.getLocation().add(0, 1.5, 0), 30, 0.5, 0.5, 0.5, 0.1);
            mob.getWorld().playSound(mob.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1.0f, 1.2f);
        } else if (data.rarity == Rarity.LEGENDARY) {
            mob.getWorld().spawnParticle(Particle.FIREWORK, mob.getLocation().add(0, 1, 0), 30, 0.5, 0.5, 0.5, 0.1);
        } else if (data.rarity == Rarity.EVENT) {
            mob.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, mob.getLocation().add(0, 1, 0), 40, 0.5, 0.8, 0.5, 0.05);
            mob.getWorld().playSound(mob.getLocation(), Sound.ENTITY_ELDER_GUARDIAN_CURSE, 0.6f, 0.5f);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onPlayerHitNoDamage(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player)) return;
        e.setDamage(0.0);
    }

    private void setupMob(Entity mob, MobData data) {
        if (mob instanceof LivingEntity living) {
            // Дракону ИИ НЕ выключаем: у NoAI-дракона ванилла жёстко ставит flapTime = 0.5,
            // то есть крылья замирают. Вместо этого он висит в фазе HOVER и сидит пассажиром
            // на невидимом носителе, поэтому сам никуда не улетает.
            if (data != MobData.ENDER_DRAGON) living.setAI(false);
            living.setGravity(false);
            living.setInvulnerable(true);
            living.setSilent(true);
            living.setRemoveWhenFarAway(false);
            living.setPersistent(true);
            living.setCollidable(false);
            living.setFireTicks(0);
            living.setCanPickupItems(false);
            living.setCustomNameVisible(false);
            living.setVelocity(new Vector(0, 0, 0));
            if (mob instanceof Enderman enderman) { enderman.setTarget(null); enderman.setCarriedBlock(null); mob.addScoreboardTag("ENDERMAN_NO_TELEPORT"); }
            else if (data == MobData.STRIDER && mob instanceof Strider strider) { strider.setShivering(false); strider.setSaddle(false); }
            else if (data == MobData.CAT_KUZYA && mob instanceof Cat cat) { cat.setCatType(Cat.Type.RED); cat.setCollarColor(DyeColor.RED); cat.setTamed(true); }
            else if (mob instanceof Fox fox) { fox.setFoxType(Fox.Type.RED); }
            else if (mob instanceof Panda panda && data != MobData.BROWN_PANDA) { panda.setMainGene(Panda.Gene.NORMAL); }
            else if (mob instanceof Wolf wolf) { wolf.setAngry(false); wolf.setCollarColor(DyeColor.RED); }
            else if (mob instanceof Horse horse) { horse.setColor(Horse.Color.BROWN); horse.setStyle(Horse.Style.WHITE); }
            else if (mob instanceof Llama llama) { llama.setColor(Llama.Color.CREAMY); }
            else if (mob instanceof Hoglin hoglin) { hoglin.setImmuneToZombification(true); }
            else if (mob instanceof PiglinBrute piglin) { piglin.setImmuneToZombification(true); }
            else if (mob instanceof Bat bat) { bat.setAwake(true); }
            else if (mob instanceof Bee bee) { bee.setAnger(0); bee.setCannotEnterHiveTicks(999999); }
            else if (data == MobData.BROWN_PANDA && mob instanceof Panda panda) { panda.setMainGene(Panda.Gene.BROWN); panda.setHiddenGene(Panda.Gene.BROWN); }
            else if (data == MobData.PIGLIN && mob instanceof Piglin piglin) { piglin.setImmuneToZombification(true); piglin.setIsAbleToHunt(false); }
            else if (data == MobData.CREEPER && mob instanceof Creeper creeper) { creeper.setPowered(true); }
            else if (data == MobData.DROWNED && mob instanceof Drowned drowned) { drowned.setConversionTime(-1); }
            else if (data == MobData.ZOMBIFIED_PIGLIN && mob instanceof PigZombie pigZombie) { pigZombie.setAngry(false); pigZombie.setAnger(0); }
            else if (data == MobData.GOAT && mob instanceof Goat goat) { goat.setScreaming(random.nextBoolean()); }
            else if (data == MobData.SNOW_GOLEM && mob instanceof Snowman snowman) { snowman.setDerp(false); }
            else if (data == MobData.WARDEN && mob instanceof Warden warden) { warden.setAware(false); for (Player p : warden.getWorld().getPlayers()) warden.setAnger(p, 0); mob.addScoreboardTag("NO_WARDEN_EFFECTS"); }
            else if (data == MobData.AXOLOTL && mob instanceof Axolotl axolotl) { axolotl.setVariant(Axolotl.Variant.BLUE); }
            else if (data == MobData.FROG && mob instanceof Frog frog) { frog.setVariant(Frog.Variant.WARM); }
            else if (data == MobData.ENDER_DRAGON && mob instanceof EnderDragon dragon) {
                try { dragon.setPhase(EnderDragon.Phase.HOVER); } catch (Throwable ignored) {}
                try { if (dragon.getBossBar() != null) dragon.getBossBar().setVisible(false); } catch (Throwable ignored) {}
                try {
                    org.bukkit.attribute.AttributeInstance scale = living.getAttribute(org.bukkit.attribute.Attribute.SCALE);
                    if (scale != null) scale.setBaseValue(0.25);
                } catch (Throwable ignored) {}
                mob.addScoreboardTag("DRAGON_RIG");
                createDragonCarrier(mob);
            }
            mob.setTicksLived(1);
            mob.addScoreboardTag("NO_DESPAWN");
            mob.addScoreboardTag("MOB_" + data.name());
            mob.addScoreboardTag("MOB_RARITY_" + data.rarity.name());
        }
    }

    private Entity createDragonCarrier(Entity dragon) {
        try {
            Location loc = dragon.getLocation();
            ArmorStand carrier = (ArmorStand) dragon.getWorld().spawnEntity(loc, EntityType.ARMOR_STAND);
            carrier.setVisible(false);
            carrier.setMarker(true);
            carrier.setSmall(true);
            carrier.setBasePlate(false);
            carrier.setGravity(false);
            carrier.setInvulnerable(true);
            carrier.setSilent(true);
            carrier.setCollidable(false);
            carrier.setPersistent(true);
            carrier.setRemoveWhenFarAway(false);
            carrier.addScoreboardTag(DRAGON_CARRIER_TAG);
            carrier.addScoreboardTag("NO_DESPAWN");
            carrier.addPassenger(dragon);
            dragonCarriers.put(dragon, carrier);
            return carrier;
        } catch (Throwable t) {
            getLogger().warning("[BRAINROT] Не удалось создать носителя для дракона: " + t);
            return null;
        }
    }

    private boolean teleportDragonCarrier(Entity carrier, Location loc) {
        try {
            // Bukkit по умолчанию отказывается телепортировать транспорт с пассажирами,
            // поэтому нужен Paper-флаг RETAIN_PASSENGERS.
            return carrier.teleport(loc, org.bukkit.event.player.PlayerTeleportEvent.TeleportCause.PLUGIN,
                    io.papermc.paper.entity.TeleportFlag.EntityState.RETAIN_PASSENGERS);
        } catch (Throwable t) {
            try { return carrier.teleport(loc); } catch (Throwable ignored) { return false; }
        }
    }

    // Двигает дракона вместе с носителем. Возвращает true, если позиция реально изменилась.
    private boolean moveDragonRig(Entity dragon, Location target) {
        if (dragon instanceof EnderDragon d) {
            try { if (d.getPhase() != EnderDragon.Phase.HOVER) d.setPhase(EnderDragon.Phase.HOVER); } catch (Throwable ignored) {}
            try { d.setVelocity(new Vector(0, 0, 0)); } catch (Throwable ignored) {}
        }
        Entity carrier = dragonCarriers.get(dragon);
        if (carrier == null || !carrier.isValid() || carrier.isDead()) {
            dragonCarriers.remove(dragon);
            carrier = createDragonCarrier(dragon);
        }
        if (carrier == null) {
            try { return dragon.teleport(target); } catch (Throwable t) { return false; }
        }
        Location carrierTarget = target.clone().subtract(0, DRAGON_CARRIER_Y_OFFSET, 0);
        boolean moved = teleportDragonCarrier(carrier, carrierTarget);
        if (!moved || carrier.getLocation().distanceSquared(carrierTarget) > 0.05) {
            String dim = carrier.getWorld().getKey().toString();
            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), String.format(Locale.US,
                    "execute in %s run minecraft:tp %s %.3f %.3f %.3f %.1f 0",
                    dim, carrier.getUniqueId(),
                    carrierTarget.getX(), carrierTarget.getY(), carrierTarget.getZ(), carrierTarget.getYaw()));
            moved = carrier.getLocation().distanceSquared(carrierTarget) <= 0.05;
        }
        if (!carrier.getPassengers().contains(dragon)) {
            try { carrier.addPassenger(dragon); } catch (Throwable ignored) {}
        }
        applyDragonYaw(dragon, target.getYaw());
        return moved;
    }

    /**
     * Разворот дракона. Ключевой момент: у дракона с включённым ИИ ванильный aiStep КАЖДЫЙ тик
     * сам пересчитывает yaw — он доворачивается к «точке полёта» текущей фазы. Поэтому наш
     * setRotation затирается (планировщик пишет до тика сущности, а трекер отправляет клиенту уже
     * пересчитанное ваниллой значение). Значит с ИИ бороться бессмысленно — ему надо подсунуть
     * цель: ставим targetLocation фазы HOVER в точку в 20 блоках по нужному азимуту, и дракон
     * доворачивается туда сам. Улететь он не может: позицию каждый тик задаёт носитель.
     */
    private void applyDragonYaw(Entity dragon, float travelYaw) {
        final float norm = dragonRenderYaw(travelYaw);
        steerDragonHover(dragon, norm);
        forceDragonYawNms(dragon, norm);
        // Подстраховка через Bukkit API, если NMS-поля не нашлись.
        try {
            Method m = dragon.getClass().getMethod("setRotation", float.class, float.class);
            m.invoke(dragon, norm, 0f);
        } catch (Throwable ignored) {}
    }

    /**
     * Итоговый yaw для дракона. Клиент рисует дракона зеркально относительно обычных мобов
     * (та же причина, по которой ломаются дракон-дисгайзы), поэтому знак поворота можно
     * инвертировать флагом dragon.yaw-invert — одним смещением зеркало не исправить.
     */
    private float dragonRenderYaw(float travelYaw) {
        float y = dragonYawInvert ? -travelYaw : travelYaw;
        return Location.normalizeYaw(y + dragonYawOffset);
    }

    /** Пишем yaw/yBodyRot/yHeadRot прямо в NMS-сущность: Bukkit setRotation трогает только yRot. */
    private void forceDragonYawNms(Entity dragon, float yaw) {
        try {
            Object handle = dragon.getClass().getMethod("getHandle").invoke(dragon);
            invokeFloatSetter(handle, yaw, "setYRot", "setYHeadRot", "setYBodyRot");
            setFloatFieldIfExists(handle, yaw, "yRotO", "yBodyRot", "yBodyRotO", "yHeadRot", "yHeadRotO");
        } catch (Throwable t) {
            warnDragonSteer("NMS yaw: " + t);
        }
    }

    private void invokeFloatSetter(Object handle, float value, String... names) {
        for (String name : names) {
            try {
                Method m = handle.getClass().getMethod(name, float.class);
                m.setAccessible(true);
                m.invoke(handle, value);
            } catch (Throwable ignored) {}
        }
    }

    private void setFloatFieldIfExists(Object handle, float value, String... names) {
        for (String name : names) {
            Class<?> c = handle.getClass();
            while (c != null) {
                try {
                    java.lang.reflect.Field f = c.getDeclaredField(name);
                    f.setAccessible(true);
                    f.setFloat(handle, value);
                    break;
                } catch (NoSuchFieldException e) {
                    c = c.getSuperclass();
                } catch (Throwable t) {
                    break;
                }
            }
        }
    }

    // Цель полёта текущей фазы -> поле Vec3 внутри фазы (Paper 1.20.5+ работает на Mojang-маппингах).
    private void steerDragonHover(Entity dragon, float yaw) {
        try {
            Object handle = dragon.getClass().getMethod("getHandle").invoke(dragon);
            Object phaseManager = handle.getClass().getMethod("getPhaseManager").invoke(handle);
            Object phase = phaseManager.getClass().getMethod("getCurrentPhase").invoke(phaseManager);
            Class<?> vec3Class = Class.forName("net.minecraft.world.phys.Vec3");
            double rad = Math.toRadians(yaw);
            double dx = -Math.sin(rad), dz = Math.cos(rad);
            Location loc = dragon.getLocation();
            Object target = vec3Class.getConstructor(double.class, double.class, double.class)
                    .newInstance(loc.getX() + dx * 20.0, loc.getY(), loc.getZ() + dz * 20.0);
            boolean set = false;
            for (java.lang.reflect.Field f : phase.getClass().getDeclaredFields()) {
                if (f.getType() == vec3Class) {
                    f.setAccessible(true);
                    f.set(phase, target);
                    set = true;
                }
            }
            if (!set) warnDragonSteer("у фазы " + phase.getClass().getSimpleName() + " нет поля Vec3");
        } catch (Throwable t) {
            warnDragonSteer(String.valueOf(t));
        }
    }

    private boolean dragonSteerWarned = false;
    private String lastDragonSteerError = null;

    private void warnDragonSteer(String reason) {
        lastDragonSteerError = reason;
        if (dragonSteerWarned) return;
        dragonSteerWarned = true;
        getLogger().warning("[BRAINROT] Не удалось задать дракону цель полёта (" + reason
                + "). Разворот может не работать.");
    }

    private boolean isSpawnerDragon(Entity entity) {
        if (entity == null) return false;
        Entity e = entity;
        if (e instanceof ComplexEntityPart part) e = part.getParent();
        if (e.getType() != EntityType.ENDER_DRAGON) return false;
        return mobDataMap.containsKey(e) || e.getScoreboardTags().contains("MOB_ENDER_DRAGON");
    }

    // С включенным ИИ ванильный дракон ломает блоки вокруг себя (checkWalls) — запрещаем.
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDragonExplode(EntityExplodeEvent e) {
        if (!isSpawnerDragon(e.getEntity())) return;
        e.blockList().clear();
        e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDragonChangeBlock(org.bukkit.event.entity.EntityChangeBlockEvent e) {
        if (isSpawnerDragon(e.getEntity())) e.setCancelled(true);
    }

    // ...и бьёт/отбрасывает игроков — тоже запрещаем.
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDragonDamageOthers(EntityDamageByEntityEvent e) {
        if (isSpawnerDragon(e.getDamager())) {
            e.setDamage(0.0);
            e.setCancelled(true);
        }
    }

    private void removeDragonCarrier(Entity dragon) {
        Entity carrier = dragonCarriers.remove(dragon);
        if (carrier == null) return;
        try { carrier.eject(); } catch (Throwable ignored) {}
        try { if (carrier.isValid()) carrier.remove(); } catch (Throwable ignored) {}
    }

    private void startMobMovement(Entity mob, double nameTagHeight, SpawnerConfig config) {
        final Entity finalMob = mob;
        final Location spawnLoc = config.getSpawnLoc();
        final Location despawnLoc = config.getDespawnLoc();
        final double speed = config.getSpeed();
        final String direction = config.getDirection();
        final MobData mobData = mobDataMap.get(finalMob);
        final double savedNameTagHeight = nameTagHeight;
        final Location initialLoc = spawnLoc.clone();
        if (mobData == MobData.ENDER_DRAGON || finalMob.getType() == EntityType.ENDER_DRAGON) {
            getLogger().info("[DRAGON] movement task started: mobData=" + mobData + " speed=" + speed + " dir=" + direction);
        }
        BukkitRunnable movementTask = new BukkitRunnable() {
            private double traveledDistance = 0;
            private long tick = 0;
            @Override
            public void run() {
                try {
                    tickMove();
                } catch (Throwable t) {
                    getLogger().warning("[BRAINROT] Ошибка движения моба " + mobData + ": " + t);
                    try { cancel(); } catch (Throwable ignored) {}
                    movementTasks.remove(finalMob);
                }
            }
            private void tickMove() {
                tick++;
                String extrasNow = extrasKey(finalMob);
                if (!extrasNow.equals(mobExtrasCache.getOrDefault(finalMob, ""))) {
                    mobExtrasCache.put(finalMob, extrasNow);
                    refreshMobNameTags(finalMob);
                }
                if (!hasPlayersInWorld(config.getWorldName()) || !finalMob.isValid() || finalMob.isDead()) {
                    cleanupMob(finalMob);
                    cancel();
                    movementTasks.remove(finalMob);
                    return;
                }
                Mutation base = mobMutations.getOrDefault(finalMob, Mutation.NONE);
                tickMutationParticles(finalMob, base, tick);
                for (Mutation extra : getExtraMutations(finalMob)) tickMutationParticles(finalMob, extra, tick);
                // Раз в 12 секунд самовар вскипает: труба трясётся, крышка прыгает.
                // Дальше возвращаем walk — boil одноразовая, сама в цикл не уйдёт.
                if (ModelEngineHook.hasModel(finalMob) && tick % 240L == 120L) {
                    ModelEngineHook.playForced(finalMob, "boil");
                    Bukkit.getScheduler().runTaskLater(BrainrotSpawner.this, () -> {
                        if (finalMob.isValid() && !finalMob.isDead()) ModelEngineHook.play(finalMob, "walk");
                    }, 36L);
                }
                Vector dirVec = getDirectionVector(direction);
                double baseY = spawnLoc.getY();
                traveledDistance += speed;
                double newX = initialLoc.getX() + dirVec.getX() * traveledDistance;
                double newZ = initialLoc.getZ() + dirVec.getZ() * traveledDistance;
                double newY = baseY;
                if (isFlightMob(mobData)) newY = calculateFlightHeight(mobData, baseY);
                float yaw = getYawFromDirection(direction);
                Location targetLoc = new Location(initialLoc.getWorld(), newX, newY, newZ, yaw, 0);
                if (mobData == MobData.ROT_WALKER) {
                    String uniq = getRotWalkerUniqTag(finalMob);
                    if (uniq != null) {
                        String dim = finalMob.getWorld().getKey().toString();
                        String cmd = String.format(Locale.US,
                                "execute in %s run minecraft:tp @e[type=item_display,tag=%s,tag=%s,limit=1] %.3f %.3f %.3f %.1f 0",
                                dim, ROT_WALKER_ROOT_TAG, uniq,
                                targetLoc.getX(), targetLoc.getY(), targetLoc.getZ(), targetLoc.getYaw());
                        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
                    } else {
                        finalMob.teleport(targetLoc);
                    }
                } else if (mobData == MobData.SPONGE) {
                    String uniq = getLuckyUniqTag(finalMob);
                    if (uniq != null) {
                        String dim = finalMob.getWorld().getKey().toString();
                        String cmd = String.format(Locale.US,
                                "execute in %s run minecraft:tp @e[type=item_display,tag=aj.luckyblock.root,tag=%s,limit=1] %.3f %.3f %.3f %.1f 0",
                                dim, uniq,
                                targetLoc.getX(), targetLoc.getY(), targetLoc.getZ(), targetLoc.getYaw());
                        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
                    } else {
                        finalMob.teleport(targetLoc);
                    }
                } else if (mobData == MobData.ENDER_DRAGON) {
                    moveDragonRig(finalMob, targetLoc);
                } else {
                    finalMob.teleport(targetLoc);
                }
                Location holoBase = targetLoc;
                if (mobData == MobData.SPONGE) holoBase = getLuckyVisualCenter(targetLoc);
                Entity hitbox = spongeHitboxMap.get(finalMob);
                if (hitbox != null && hitbox.isValid()) hitbox.teleport(holoBase.clone().add(0, 0.75, 0));
                updateNameTagsPosition(finalMob, holoBase, savedNameTagHeight);
                if (despawnLoc != null) {
                    double distX = Math.abs(targetLoc.getX() - despawnLoc.getX());
                    double distZ = Math.abs(targetLoc.getZ() - despawnLoc.getZ());
                    if (distX < 2.0 && distZ < 2.0) {
                        cleanupMob(finalMob);
                        cancel();
                        movementTasks.remove(finalMob);
                        return;
                    }
                }
                if (traveledDistance > 150) {
                    cleanupMob(finalMob);
                    cancel();
                    movementTasks.remove(finalMob);
                }
            }
        };
        movementTask.runTaskTimer(this, 1L, 1L);
        movementTasks.put(finalMob, movementTask);
    }

    private double calculateFlightHeight(MobData data, double baseHeight) {
        double time = System.currentTimeMillis() / 1000.0;
        return switch (data) {
            case BLAZE -> baseHeight + 0.5 + Math.sin(time * 1.5) * 0.05;
            case PHANTOM -> baseHeight + 0.6 + Math.sin(time * 2.5) * 0.05;
            case VEX, ALLAY -> baseHeight + 0.6 + Math.sin(time * 1.8) * 0.05;
            case BAT -> baseHeight + 0.8 + Math.sin(time * 3.0) * 0.08;
            case BEE -> baseHeight + 0.5 + Math.sin(time * 2.0) * 0.04;
            case GUARDIAN, GLOW_SQUID -> baseHeight + 0.3 + Math.sin(time * 2.0) * 0.03;
            case AXOLOTL -> baseHeight + 0.2 + Math.sin(time * 2.2) * 0.03;
            case STRIDER, ENDERMAN -> baseHeight + 0.1;
            default -> baseHeight;
        };
    }

    private boolean isFlightMob(MobData data) {
        if (data == null) return false;
        return data == MobData.BLAZE || data == MobData.PHANTOM || data == MobData.VEX ||
               data == MobData.BAT || data == MobData.BEE || data == MobData.STRIDER ||
               data == MobData.ENDERMAN || data == MobData.GUARDIAN || data == MobData.ALLAY ||
               data == MobData.AXOLOTL || data == MobData.GLOW_SQUID;
    }

    private boolean hasPlayersInWorld(String worldName) {
        World world = Bukkit.getWorld(worldName);
        return world != null && !world.getPlayers().isEmpty();
    }

    private void cleanupMobsInWorld(String worldName) {
        List<Entity> toRemove = new ArrayList<>();
        for (Entity mob : mobDataMap.keySet()) if (mob.getWorld().getName().equals(worldName)) toRemove.add(mob);
        for (Entity mob : toRemove) cleanupMob(mob);
    }

    private void cleanupMob(Entity mob) {
        if (!Bukkit.getServer().isPrimaryThread()) {
            Bukkit.getScheduler().runTask(this, () -> cleanupMobSync(mob));
            return;
        }
        cleanupMobSync(mob);
    }

    private void cleanupMobSync(Entity mob) {
        try {
            BukkitRunnable mv = movementTasks.remove(mob);
            if (mv != null) try { mv.cancel(); } catch (Exception ignored) {}
            BukkitRunnable dlv = deliveryTasks.remove(mob);
            if (dlv != null) try { dlv.cancel(); } catch (Exception ignored) {}
            BukkitRunnable rb = rainbowAnimationTasks.remove(mob);
            if (rb != null) try { rb.cancel(); } catch (Exception ignored) {}
            Entity hitbox = spongeHitboxMap.remove(mob);
            if (hitbox != null && hitbox.isValid()) hitbox.remove();
            removeDragonCarrier(mob);
            // Модель ME снимаем до всех ранних return'ов ниже: иначе на сервере
            // останется висеть рига без хозяина.
            ModelEngineHook.detach(mob);
            removeNameTags(mob);
            mobBuyers.remove(mob);
            deliveryDestinations.remove(mob);
            mobToSpawner.remove(mob);
            mobHoloHeights.remove(mob);
            mobMutations.remove(mob);
            mobClickCooldown.remove(mob);
            mobDataMap.remove(mob);
            mobExtrasCache.remove(mob);
            if (mob.getScoreboardTags().contains("ROT_WALKER_ANIMATED") || mob.getScoreboardTags().contains(ROT_WALKER_ROOT_TAG)) {
                String uniq = getRotWalkerUniqTag(mob);
                String dim = mob.getWorld().getKey().toString();
                if (uniq != null) {
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            "execute in " + dim + " as @e[tag=" + uniq + ",limit=1] run function animated_java:rotwalker/remove");
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            "execute in " + dim + " run minecraft:kill @e[tag=" + uniq + "]");
                } else {
                    Location l = mob.getLocation();
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            String.format(Locale.US, "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[tag=%s,distance=..4]",
                                    dim, l.getX(), l.getY(), l.getZ(), ROT_WALKER_ENTITY_TAG));
                }
                rotWalkerHitboxMap.remove(mob);
                rotWalkerAnimTasks.remove(mob);
                return;
            }
            if (mob.getScoreboardTags().contains("LUCKY_BLOCK_ANIMATED") || mob.getScoreboardTags().contains("aj.luckyblock.root")) {
                String uniq = getLuckyUniqTag(mob);
                String dim = mob.getWorld().getKey().toString();
                if (uniq != null) {
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            "execute in " + dim + " as @e[type=item_display,tag=" + uniq + ",limit=1] run function animated_java:luckyblock/remove");
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            "execute in " + dim + " as @e[type=item_display,tag=" + uniq + ",limit=1] run function animated_java:luckyblock/remove {args:{}}");
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                            "execute in " + dim + " run minecraft:kill @e[tag=" + uniq + "]");
                } else {
                    Location l = mob.getLocation();
                    String cmd = String.format(Locale.US,
                            "execute in %s positioned %.3f %.3f %.3f run minecraft:kill @e[tag=aj.luckyblock.entity,distance=..4]",
                            dim, l.getX(), l.getY(), l.getZ());
                    Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
                }
                return;
            }
            if (mob.isValid() && !mob.isDead()) mob.remove();
        } catch (Exception e) {
            getLogger().severe("Ошибка очистки: " + e.getMessage());
        }
    }

    private boolean setupEconomy() {
        if (getServer().getPluginManager().getPlugin("Vault") == null) return false;
        RegisteredServiceProvider<Economy> rsp = getServer().getServicesManager().getRegistration(Economy.class);
        if (rsp == null) return false;
        economy = rsp.getProvider();
        return economy != null;
    }

    private Vector getDirectionVector(String dir) {
        return switch (dir.toLowerCase()) {
            case "back", "backward" -> new Vector(0, 0, -1);
            case "left" -> new Vector(-1, 0, 0);
            case "right" -> new Vector(1, 0, 0);
            default -> new Vector(0, 0, 1);
        };
    }

    private float getYawFromDirection(String dir) {
        return switch (dir.toLowerCase()) {
            case "back", "backward" -> 0f;
            case "left" -> 90f;
            case "right" -> -90f;
            default -> 180f;
        };
    }

    private String formatNumber(long num) {
        if (num >= 1_000_000_000_000L) return String.format("%.1fТ", num / 1_000_000_000_000.0).replace(",", ".");
        if (num >= 1_000_000_000L) return String.format("%.1fБ", num / 1_000_000_000.0).replace(",", ".");
        if (num >= 1_000_000L) return String.format("%.1fМ", num / 1_000_000.0).replace(",", ".");
        if (num >= 1_000L) return String.format("%.1fК", num / 1_000.0).replace(",", ".");
        return String.valueOf(num);
    }

    private void logMobChances() {
        getLogger().info("§e╔════════════════════════════════════════════════════════════╗");
        getLogger().info("§e║              СИСТЕМА ШАНСОВ СПАВНА                         ║");
        getLogger().info("§e╚════════════════════════════════════════════════════════════╝");
        for (Rarity rarity : Rarity.values()) {
            List<MobData> mobsInRarity = new ArrayList<>();
            double totalWeight = 0;
            for (MobData mob : MobData.values()) { if (mob.rarity == rarity) { mobsInRarity.add(mob); totalWeight += mob.weight; } }
            getLogger().info("");
            getLogger().info(rarity.format + "══ " + rarity.displayName + " §7(" + String.format("%.1f", rarity.chance) + "% шанс, " + mobsInRarity.size() + " мобов) " + rarity.format + "══");
            final double finalTotalWeight = totalWeight;
            mobsInRarity.sort((a, b) -> Double.compare(b.weight, a.weight));
            for (MobData mob : mobsInRarity) {
                double mobChanceInPool = finalTotalWeight > 0 ? (mob.weight / finalTotalWeight) * 100 : 0;
                double realChance = finalTotalWeight > 0 ? (rarity.chance / 100) * (mob.weight / finalTotalWeight) * 100 : 0;
                getLogger().info(String.format("  §7• §f%-22s §7вес:§e%5.1f §7пул:§a%5.1f%% §7реал:§b%.4f%%", mob.displayName, mob.weight, mobChanceInPool, realChance));
            }
        }
        getLogger().info("");
        getLogger().info("§6══ МУТАЦИИ ══");
        for (Mutation m : Mutation.values()) {
            getLogger().info(String.format("  §7• %s%-12s §7шанс:§e%.2f%% §7множитель:§a×%.2f", m.format, m.displayName.isEmpty() ? "Обычный" : m.displayName, m.chance, m.incomeMultiplier));
        }
        getLogger().info("§a════════════════════════════════════════════════════════════");
    }

    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        Bukkit.getScheduler().runTaskLater(this, () -> {
            if (isBedrockPlayer(player)) bedrockPlayerCache.add(player.getUniqueId());
        }, 20L);
    }

    @EventHandler
    public void onPlayerQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        UUID playerId = player.getUniqueId();
        bedrockPlayerCache.remove(playerId);
        playerComboCounter.remove(playerId);
        lastHitTime.remove(playerId);
        playerHitCooldown.remove(playerId);
        List<Entity> mobsToRemove = new ArrayList<>();
        for (Map.Entry<Entity, Player> entry : mobBuyers.entrySet()) {
            if (entry.getValue() != null && entry.getValue().getUniqueId().equals(playerId)) mobsToRemove.add(entry.getKey());
        }
        for (Entity mob : mobsToRemove) if (mob != null && mob.isValid()) cleanupMob(mob);
        Bukkit.getScheduler().runTaskLater(this, () -> {
            for (SpawnerConfig config : spawnerConfigs.values()) if (!hasPlayersInWorld(config.getWorldName())) cleanupMobsInWorld(config.getWorldName());
        }, 20L);
    }

    @EventHandler
    public void onMobDeath(EntityDeathEvent e) { if (mobDataMap.containsKey(e.getEntity())) cleanupMob(e.getEntity()); }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onMobCombust(EntityCombustEvent e) {
        if (mobDataMap.containsKey(e.getEntity()) || e.getEntity().getScoreboardTags().contains("NO_DESPAWN")) {
            e.setCancelled(true);
            if (e.getEntity() instanceof LivingEntity l) l.setFireTicks(0);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onEndermanTeleport(EntityTeleportEvent e) {
        if (!(e.getEntity() instanceof Enderman enderman)) return;
        if (!mobDataMap.containsKey(enderman) && !enderman.getScoreboardTags().contains("ENDERMAN_NO_TELEPORT") && !enderman.getScoreboardTags().contains("NO_DESPAWN")) return;
        Location from = e.getFrom();
        Location to = e.getTo();
        if (to == null) return;
        if (from.getWorld() != to.getWorld() || from.distanceSquared(to) > 1.0) {
            e.setCancelled(true);
            enderman.setTarget(null);
            enderman.setCarriedBlock(null);
            enderman.setVelocity(new Vector(0, 0, 0));
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onEntityTarget(EntityTargetEvent e) {
        if (e.getEntity() instanceof Enderman && (mobDataMap.containsKey(e.getEntity()) || e.getEntity().getScoreboardTags().contains("ENDERMAN_NO_TELEPORT"))) {
            e.setCancelled(true);
            e.setTarget(null);
        }
    }

    @EventHandler
    public void onPlayerInteract(PlayerInteractAtEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) return;
        Entity entity = event.getRightClicked();
        if (entity instanceof ComplexEntityPart part) entity = part.getParent();
        if (isBaseMobEntity(entity)) return;
        if (entity.getScoreboardTags().contains("SPONGE_HITBOX")) {
            boolean found = false;
            for (Map.Entry<Entity, Entity> entry : spongeHitboxMap.entrySet()) {
                if (entry.getValue().equals(entity)) {
                    Entity rootMob = entry.getKey();
                    if (isBaseMobEntity(rootMob)) return;
                    entity = rootMob;
                    found = true;
                    break;
                }
            }
            if (!found) return;
        }
        Player player = event.getPlayer();
        if (economy == null || !entity.isValid()) return;
        for (String tag : entity.getScoreboardTags()) {
            if (tag.startsWith("BASE_")) return;
            if (tag.startsWith("base_lb_")) return;
        }
        MobData data = mobDataMap.get(entity);
        if (data == null) {
            for (String tag : entity.getScoreboardTags()) {
                if (tag.startsWith("MOB_") && !tag.startsWith("MOB_RARITY_")) {
                    try { data = MobData.valueOf(tag.substring(4)); break; } catch (Exception ignored) {}
                }
            }
        }
        if (data == null) return;
        Player currentBuyer = mobBuyers.get(entity);
        if (currentBuyer != null) {
            if (currentBuyer.equals(player)) {
                player.sendMessage("§e⚠ Этот моб уже ваш и направляется к базе!");
                event.setCancelled(true);
                return;
            }
            String baseErr = getBaseBuyError(player);
            if (baseErr != null) {
                player.sendMessage(baseErr + " §cПерекуп невозможен.");
                player.playSound(player.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f);
                event.setCancelled(true);
                return;
            }
            long rebuyPrice = (long) (data.price * 1.5);
            if (economy.getBalance(player) < rebuyPrice) {
                player.sendMessage("§c✖ Для перекупа нужно: §6$" + formatNumber(rebuyPrice) + " §c(+50%)");
                player.playSound(player.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f);
                event.setCancelled(true);
                return;
            }
            economy.withdrawPlayer(player, rebuyPrice);
            economy.depositPlayer(currentBuyer, data.price);
            if (currentBuyer.isOnline()) {
                currentBuyer.sendMessage("§c⚠ Игрок §f" + player.getName() + " §cперекупил вашего §f" + data.displayName + "§c!");
                currentBuyer.playSound(currentBuyer.getLocation(), Sound.ENTITY_VILLAGER_HURT, 1f, 1f);
            }
            player.sendMessage("§a✔ §fВы перекупили §e" + data.displayName + " §fза §6$" + formatNumber(rebuyPrice) + "§f!");
            player.playSound(player.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.2f);
            BukkitRunnable oldTask = deliveryTasks.remove(entity);
            if (oldTask != null) try { oldTask.cancel(); } catch (Exception ignored) {}
            mobBuyers.put(entity, player);
            sendMobToBase(player, entity, data);
            event.setCancelled(true);
            return;
        }
        if (entity.getScoreboardTags().contains("PURCHASED_MOB")) { event.setCancelled(true); return; }
        String baseErr = getBaseBuyError(player);
        if (baseErr != null) {
            player.sendMessage(baseErr + " §cПокупка невозможна.");
            player.playSound(player.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f);
            event.setCancelled(true);
            return;
        }
        if (economy.getBalance(player) < data.price) {
            player.sendMessage("§c✖ Не хватает денег! Цена: §6$" + formatNumber(data.price));
            player.playSound(player.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f);
            event.setCancelled(true);
            return;
        }
        economy.withdrawPlayer(player, data.price);
        Mutation mutation = mobMutations.get(entity);
        String mutationPrefix = (mutation != null && mutation != Mutation.NONE) ? mutation.format + mutation.displayName + " " : "";
        String msg = switch (data.rarity) {
            case SECRET -> "§8☠ §fВы купили §8" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case BRAINROT_GOD -> "§b✧ §fВы купили §b" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case MYTHICAL -> "§d✦ §fВы купили §d" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case LEGENDARY -> "§6✔ §fВы купили §6" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case EPIC -> "§5✔ §fВы купили §5" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case RARE -> "§9✔ §fВы купили §9" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            case EVENT -> "§2☣ §fВы купили §2" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
            default -> "§a✔ §fВы купили §a" + mutationPrefix + data.displayName + "§f за §6$" + formatNumber(data.price) + "§f!";
        };
        player.sendMessage(msg);
        player.playSound(player.getLocation(), data.rarity == Rarity.MYTHICAL || data.rarity == Rarity.BRAINROT_GOD || data.rarity == Rarity.SECRET || data.rarity == Rarity.EVENT ? Sound.UI_TOAST_CHALLENGE_COMPLETE : Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.5f);
        sendMobToBase(player, entity, data);
        event.setCancelled(true);
    }

    private boolean isBaseMobEntity(Entity entity) {
        if (entity == null) return false;
        Set<String> tags = entity.getScoreboardTags();
        if (tags.contains("BASE_MOB")) return true;
        if (tags.contains("BASE_MOB_PERSISTENT")) return true;
        if (tags.contains("LUCKY_BLOCK_HITBOX")) return true;
        for (String tag : tags) {
            if (tag.startsWith("base_lb_")) return true;
        }
        return false;
    }

    private String getBaseBuyError(Player player) {
        BrainrotBases basesPlugin = BrainrotBases.getInstance();
        if (basesPlugin == null) return "§c✖ Система баз недоступна!";
        String baseName = getPlayerBaseName(player);
        if (baseName == null) return "§c✖ У вас нет базы!";
        Location submit = basesPlugin.getNearestSubmitLocation(player, baseName);
        if (submit == null) return "§c✖ На вашей базе нет точки сдачи!";
        try {
            Method m = basesPlugin.getClass().getDeclaredMethod("findFreeMobPoint", String.class);
            m.setAccessible(true);
            String freePoint = (String) m.invoke(basesPlugin, baseName);
            if (freePoint == null) return "§c✖ На вашей базе нет свободных мест!";
        } catch (Exception ex) {
            getLogger().warning("Не удалось проверить свободные места базы: " + ex.getMessage());
            return "§c✖ Ошибка проверки базы!";
        }
        return null;
    }

    private boolean isSnowy(Entity mob) {
        return mob != null && mob.getScoreboardTags().contains("MUTATION_SNOWY");
    }

    private void refreshMobNameTags(Entity mob) {
        MobData data = mobDataMap.get(mob);
        if (data == null) return;
        Mutation base = mobMutations.getOrDefault(mob, Mutation.NONE);
        List<Mutation> extras = getExtraMutations(mob);
        double h = mobHoloHeights.getOrDefault(mob, 2.0);
        removeNameTags(mob);
        createNameTags(mob, data, h, base, extras);
        BukkitRunnable rb = rainbowAnimationTasks.remove(mob);
        if (rb != null) try { rb.cancel(); } catch (Exception ignored) {}
        if (base == Mutation.RAINBOW) startRainbowAnimation(mob, data, extras);
    }

    private void sendMobToBase(Player player, Entity mob, MobData data) {
        BrainrotBases basesPlugin = BrainrotBases.getInstance();
        if (basesPlugin == null) {
            player.sendMessage("§c✖ Система баз недоступна!");
            cleanupMob(mob);
            return;
        }
        String playerBase = getPlayerBaseName(player);
        if (playerBase == null) {
            player.sendMessage("§c✖ У вас нет базы!");
            cleanupMob(mob);
            return;
        }
        Location dest = basesPlugin.getNearestSubmitLocation(player, playerBase);
        if (dest == null) {
            player.sendMessage("§c✖ Нет точки сдачи!");
            cleanupMob(mob);
            return;
        }
        BukkitRunnable task = movementTasks.remove(mob);
        if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        mob.addScoreboardTag("PURCHASED_MOB");
        mob.addScoreboardTag("BUYER_" + player.getName());
        mobBuyers.put(mob, player);
        deliveryDestinations.put(mob, dest);
        Double savedHeight = mobHoloHeights.get(mob);
        double nameTagHeight = savedHeight != null ? savedHeight : 2.0;
        startMobDelivery(mob, dest, player, data, nameTagHeight, playerBase);
    }

    private void startMobDelivery(Entity mob, Location dest, Player buyer, MobData data, double nameTagHeight, String baseName) {
        SpawnerConfig cfg = spawnerConfigs.get(mobToSpawner.get(mob));
        final double speed = cfg != null ? cfg.getSpeed() : 0.2;
        final double fixedY = mob.getLocation().getY();
        BukkitRunnable task = new BukkitRunnable() {
            long tick = 0;
            Location lastLoc = mob.getLocation().clone();
            @Override
            public void run() {
                tick++;
                String extrasNow = extrasKey(mob);
                if (!extrasNow.equals(mobExtrasCache.getOrDefault(mob, ""))) {
                    mobExtrasCache.put(mob, extrasNow);
                    refreshMobNameTags(mob);
                }
                if (buyer == null || !buyer.isOnline()) { cleanupMob(mob); cleanup(); return; }
                Player currentBuyer = mobBuyers.get(mob);
                if (currentBuyer == null || !currentBuyer.equals(buyer)) { cleanup(); return; }
                if (!mob.isValid() || mob.isDead()) { cleanup(); return; }
                Mutation base = mobMutations.getOrDefault(mob, Mutation.NONE);
                tickMutationParticles(mob, base, tick);
                for (Mutation extra : getExtraMutations(mob)) tickMutationParticles(mob, extra, tick);
                double dx = dest.getX() - lastLoc.getX();
                double dz = dest.getZ() - lastLoc.getZ();
                double dist = Math.sqrt(dx * dx + dz * dz);
                if (dist < 2.0) {
                    removeNameTags(mob);
                    completeDelivery(mob, buyer, dest, data, baseName);
                    cleanup();
                    return;
                }
                dx /= dist;
                dz /= dist;
                Location targetLoc = lastLoc.clone().add(dx * speed, 0, dz * speed);
                targetLoc.setY(fixedY);
                float yaw = (float) Math.toDegrees(Math.atan2(-dx, dz));
                targetLoc.setYaw(yaw);
                if (data == MobData.ROT_WALKER) {
                    String uniq = getRotWalkerUniqTag(mob);
                    if (uniq != null) {
                        String dim = mob.getWorld().getKey().toString();
                        String cmd = String.format(Locale.US,
                                "execute in %s run minecraft:tp @e[type=item_display,tag=%s,tag=%s,limit=1] %.3f %.3f %.3f %.1f 0",
                                dim, ROT_WALKER_ROOT_TAG, uniq,
                                targetLoc.getX(), targetLoc.getY(), targetLoc.getZ(), targetLoc.getYaw());
                        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
                    } else {
                        mob.teleport(targetLoc);
                    }
                } else if (data == MobData.SPONGE) {
                    String uniq = getLuckyUniqTag(mob);
                    if (uniq != null) {
                        String dim = mob.getWorld().getKey().toString();
                        String cmd = String.format(Locale.US,
                                "execute in %s run minecraft:tp @e[type=item_display,tag=aj.luckyblock.root,tag=%s,limit=1] %.3f %.3f %.3f %.1f 0",
                                dim, uniq,
                                targetLoc.getX(), targetLoc.getY(), targetLoc.getZ(), targetLoc.getYaw());
                        Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
                    } else {
                        mob.teleport(targetLoc);
                    }
                } else if (data == MobData.ENDER_DRAGON) {
                    moveDragonRig(mob, targetLoc);
                } else {
                    mob.teleport(targetLoc);
                }
                Location holoBase = (data == MobData.SPONGE) ? getLuckyVisualCenter(targetLoc) : targetLoc;
                Entity hitbox = spongeHitboxMap.get(mob);
                if (hitbox != null && hitbox.isValid()) hitbox.teleport(holoBase.clone().add(0, 0.75, 0));
                lastLoc = mob.getLocation().clone();
                updateNameTagsPosition(mob, holoBase, nameTagHeight);
                if (tick >= 6000) { buyer.sendMessage("§c✖ Моб не дошёл до базы!"); cleanupMob(mob); cleanup(); }
            }
            void cleanup() { cancel(); deliveryTasks.remove(mob); mobBuyers.remove(mob); deliveryDestinations.remove(mob); }
        };
        deliveryTasks.put(mob, task);
        task.runTaskTimer(this, 2L, 1L);
    }

    private static final Vector LUCKY_MODEL_OFFSET = new Vector(0.55, 0.0, 0.1);

    private Location getLuckyVisualCenter(Location rootLoc) {
        // Offset of the AnimatedJava lucky-block model relative to its root entity.
        // Standard AJ rigs are centered on the root, so default 0/0 keeps the hitbox +
        // hologram on the model. If the model still looks shifted, tweak these two
        // config values (in blocks) and /reload — no rebuild needed:
        //   lucky_block.model_offset_right   (+ = toward the mob's right)
        //   lucky_block.model_offset_forward (+ = toward the mob's facing direction)
        double right = getConfig().getDouble("lucky_block.model_offset_right", 0.0);
        double forward = getConfig().getDouble("lucky_block.model_offset_forward", 0.0);
        if (right == 0.0 && forward == 0.0) return rootLoc.clone();
        return applyYawModelOffset(rootLoc, right, forward);
    }

    // Applies a model-local offset (right = model's right side, forward = model facing)
    // rotated by the location's yaw, so custom-model holograms stay centered regardless of
    // walk/delivery direction.
    private Location applyYawModelOffset(Location loc, double right, double forward) {
        double yawRad = Math.toRadians(loc.getYaw());
        double sin = Math.sin(yawRad);
        double cos = Math.cos(yawRad);
        double worldX = -cos * right - sin * forward;
        double worldZ = -sin * right + cos * forward;
        return loc.clone().add(worldX, 0.0, worldZ);
    }

    private String getLuckyUniqTag(Entity e) {
        for (String t : e.getScoreboardTags()) { if (t.startsWith("brlb_")) return t; }
        return null;
    }

    private String getRotWalkerUniqTag(Entity e) {
        for (String t : e.getScoreboardTags()) { if (t.startsWith("brw_")) return t; }
        return null;
    }

    private String getPlayerBaseName(Player player) {
        BrainrotBases basesPlugin = BrainrotBases.getInstance();
        if (basesPlugin == null) return null;
        for (Map.Entry<String, String> e : basesPlugin.getBases().entrySet()) {
            if (e.getValue().equals(player.getName())) return e.getKey();
        }
        return null;
    }

    private void completeDelivery(Entity mob, Player buyer, Location loc, MobData data, String baseName) {
        BrainrotBases plugin = BrainrotBases.getInstance();
        if (plugin == null) {
            buyer.sendMessage("§c✖ Ошибка! Плагин баз не найден.");
            cleanupMob(mob);
            return;
        }
        try {
            Method m1 = plugin.getClass().getDeclaredMethod("findFreeMobPoint", String.class);
            m1.setAccessible(true);
            String point = (String) m1.invoke(plugin, baseName);
            if (point == null) {
                buyer.sendMessage("§c✖ Нет свободных мест на базе!");
                cleanupMob(mob);
                return;
            }
            Method m2 = plugin.getClass().getDeclaredMethod("getCollectorPoints", String.class);
            m2.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<String> cols = (List<String>) m2.invoke(plugin, baseName);
            Method m3 = plugin.getClass().getDeclaredMethod("findFreeCollectorForBase", String.class, List.class);
            m3.setAccessible(true);
            String col = (String) m3.invoke(plugin, baseName, cols);
            Method m4 = plugin.getClass().getDeclaredMethod(
                    "spawnMobAtPoint", String.class, String.class, String.class, MobType.class);
            m4.setAccessible(true);
            MobType type;
            try { type = MobType.valueOf(data.name()); }
            catch (Exception e) { type = MobType.CHICKEN; }
            m4.invoke(plugin, baseName, point, col, type);
            Mutation mutation = mobMutations.getOrDefault(mob, Mutation.NONE);
            boolean snowy = isSnowy(mob);
            // Стакающиеся мутации (кроме снежного, он едет отдельным флагом) кодируем как "GOLD+ELECTRIC".
            StringBuilder mutName = new StringBuilder(mutation.name());
            boolean hasExtras = false;
            for (Mutation extra : getExtraMutations(mob)) {
                if (extra == Mutation.SNOWY) continue;
                mutName.append('+').append(extra.name());
                hasExtras = true;
            }
            if (mutation != Mutation.NONE || snowy || hasExtras) {
                final String finalMutationName = mutName.toString();
                final String finalPoint = point;
                Bukkit.getScheduler().runTaskLater(this, () -> {
                    try {
                        Method applyMut = plugin.getClass().getMethod("applyMutationToPoint",
                            String.class, String.class, String.class, boolean.class);
                        applyMut.invoke(plugin, baseName, finalPoint, finalMutationName, snowy);
                        getLogger().info("Мутация " + finalMutationName + " передана на базу " + baseName);
                    } catch (Exception ex) {
                        getLogger().warning("Не удалось передать мутацию: " + ex.getMessage());
                    }
                }, 5L);
            }
            buyer.sendMessage("§a✔ §f" + data.displayName + " §aдоставлен на базу!");
            buyer.playSound(buyer.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 1f, 1f);
            mob.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, loc, 30, 0.5, 0.5, 0.5, 0.3);
            if (data.rarity == Rarity.MYTHICAL || data.rarity == Rarity.BRAINROT_GOD || data.rarity == Rarity.SECRET) {
                mob.getWorld().spawnParticle(Particle.END_ROD, loc, 50, 0.7, 0.7, 0.7, 0.2);
                mob.getWorld().playSound(loc, Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 1.2f);
            }
        } catch (Exception e) {
            getLogger().severe("Delivery error: " + e.getMessage());
            buyer.sendMessage("§c✖ Ошибка доставки!");
            org.bukkit.Bukkit.getLogger().warning("Brainrot: " + e.getMessage());
        } finally {
            cleanupMob(mob);
        }
    }

    private class BrainrotSpawnCommand implements org.bukkit.command.CommandExecutor {
        @Override
        public boolean onCommand(org.bukkit.command.CommandSender s, org.bukkit.command.Command c, String l, String[] a) {
            if (!s.hasPermission("brainrotspawner.admin")) { s.sendMessage("§cНет прав!"); return true; }
            if (a.length < 1) {
                s.sendMessage("§6/brainrotspawn <моб> [spawner] [force]");
                s.sendMessage("§6/brainrotspawn list");
                s.sendMessage("§6/brainrotspawn chances");
                s.sendMessage("§6/brainrotspawn dragonyaw <градусы> §7— разворот дракона (сейчас "
                        + (int) dragonYawOffset + "°)");
                s.sendMessage("§6/brainrotspawn dragoninvert §7— зеркальный поворот (сейчас "
                        + (dragonYawInvert ? "вкл" : "выкл") + ")");
                s.sendMessage("§6/brainrotspawn dragondebug §7— что сейчас с драконами");
                return true;
            }
            if (a[0].equalsIgnoreCase("dragoninvert")) {
                dragonYawInvert = !dragonYawInvert;
                getConfig().set("dragon.yaw-invert", dragonYawInvert);
                saveConfig();
                s.sendMessage("§aЗеркальный поворот дракона: §f" + (dragonYawInvert ? "включён" : "выключен")
                        + " §7(применится в течение тика)");
                return true;
            }
            if (a[0].equalsIgnoreCase("dragondebug")) {
                s.sendMessage("§6[Дракон] §7offset=§f" + (int) dragonYawOffset
                        + " §7invert=§f" + dragonYawInvert
                        + " §7ошибка рулёжки=§f" + (lastDragonSteerError == null ? "нет" : lastDragonSteerError));
                int found = 0;
                for (Map.Entry<Entity, MobData> entry : new HashMap<>(mobDataMap).entrySet()) {
                    Entity mob = entry.getKey();
                    if (entry.getValue() != MobData.ENDER_DRAGON || mob == null || !mob.isValid()) continue;
                    found++;
                    String phase = "?";
                    if (mob instanceof EnderDragon d) {
                        try { phase = String.valueOf(d.getPhase()); } catch (Throwable ignored) {}
                    }
                    Entity carrier = dragonCarriers.get(mob);
                    s.sendMessage("§7#" + found + " yaw=§f" + String.format(Locale.US, "%.1f", mob.getLocation().getYaw())
                            + " §7фаза=§f" + phase
                            + " §7носитель=§f" + (carrier != null && carrier.isValid() ? "есть" : "нет")
                            + " §7ИИ=§f" + (mob instanceof LivingEntity le && le.hasAI()));
                }
                if (found == 0) s.sendMessage("§7Живых драконов спавнера нет.");
                return true;
            }
            if (a[0].equalsIgnoreCase("dragonyaw")) {
                if (a.length < 2) {
                    s.sendMessage("§eТекущий разворот дракона: §f" + (int) dragonYawOffset + "°");
                    s.sendMessage("§7Пример: §f/brainrotspawn dragonyaw 90");
                    return true;
                }
                float val;
                try { val = Float.parseFloat(a[1]); }
                catch (NumberFormatException ex) { s.sendMessage("§cНужно число градусов."); return true; }
                dragonYawOffset = val;
                getConfig().set("dragon.yaw-offset", (double) val);
                saveConfig();
                s.sendMessage("§aРазворот дракона: §f" + (int) val + "° §7(применится в течение тика)");
                return true;
            }
            if (a[0].equalsIgnoreCase("list")) {
                for (Rarity r : Rarity.values()) {
                    List<String> names = Arrays.stream(MobData.values()).filter(m -> m.rarity == r).map(Enum::name).collect(Collectors.toList());
                    s.sendMessage(r.format + r.displayName + " §7(" + String.format("%.1f", r.chance) + "%): §f" + String.join(", ", names));
                }
                return true;
            }
            if (a[0].equalsIgnoreCase("chances")) { logMobChances(); s.sendMessage("§aШансы выведены в консоль!"); return true; }
            String spawnerId = null;
            boolean force = false;
            for (int i = 1; i < a.length; i++) {
                if (a[i].equalsIgnoreCase("force")) force = true;
                else if (spawnerConfigs.containsKey(a[i].toLowerCase())) spawnerId = a[i].toLowerCase();
            }
            if (spawnerId == null) {
                for (String id : spawnerConfigs.keySet()) {
                    if (spawnerConfigs.get(id).isValid()) { spawnerId = id; break; }
                }
            }
            if (spawnerId == null) { s.sendMessage("§cНет спавнеров!"); return true; }
            MobData mob;
            try { mob = MobData.valueOf(a[0].toUpperCase()); }
            catch (Exception e) { s.sendMessage("§cНеизвестный моб!"); return true; }
            if (force) {
                spawnQueues.get(spawnerId).addFirst(mob);
                spawnBrainrot(spawnerId);
                s.sendMessage("§aСпавн: " + mob.displayName);
            } else {
                spawnQueues.get(spawnerId).add(mob);
                s.sendMessage("§aВ очередь: " + mob.displayName);
            }
            return true;
        }
    }

    private class BrainrotSpawnerCommand implements org.bukkit.command.CommandExecutor {
        @Override
        public boolean onCommand(org.bukkit.command.CommandSender s, org.bukkit.command.Command c, String l, String[] a) {
            if (!s.hasPermission("brainrotspawner.admin")) { s.sendMessage("§cНет прав!"); return true; }
            if (a.length < 1) {
                s.sendMessage("§6=== BrainrotSpawner ===");
                s.sendMessage("§e/brainrotspawner list");
                s.sendMessage("§e/brainrotspawner create <id> <world>");
                s.sendMessage("§e/brainrotspawner setspawn <id>");
                s.sendMessage("§e/brainrotspawner setdespawn <id>");
                s.sendMessage("§e/brainrotspawner sethologram <id> [yaw]");
                s.sendMessage("§e/brainrotspawner test <id>");
                s.sendMessage("§e/brainrotspawner speed <id> <val>");
                s.sendMessage("§e/brainrotspawner cooldown <id> <sec>");
                s.sendMessage("§e/brainrotspawner pause <id>");
                s.sendMessage("§e/brainrotspawner resetlegendary <id>");
                s.sendMessage("§e/brainrotspawner resetmythical <id>");
                s.sendMessage("§e/brainrotspawner timers <id>");
                return true;
            }
            String sub = a[0].toLowerCase();
            if (sub.equals("list")) {
                s.sendMessage("§6=== Спавнеры ===");
                for (SpawnerConfig cfg : spawnerConfigs.values()) {
                    String holoStatus = cfg.getHologramLoc() != null ? "§a✓holo" : "§c✗holo";
                    s.sendMessage((cfg.isValid() ? "§a✓" : "§c✗") + " §e" + cfg.getId() + " §7[" + cfg.getWorldName() + "] " + holoStatus);
                }
                return true;
            }
            if (sub.equals("create") && a.length >= 3) {
                String id = a[1].toLowerCase();
                String world = a[2];
                if (Bukkit.getWorld(world) == null) { s.sendMessage("§cМир не найден!"); return true; }
                SpawnerConfig cfg = new SpawnerConfig(id, world);
                spawnerConfigs.put(id, cfg);
                spawnQueues.put(id, new LinkedList<>());
                initializeTimers(id);
                saveSpawnerConfig(cfg);
                s.sendMessage("§aСпавнер " + id + " создан!");
                return true;
            }
            if (sub.equals("setspawn") && a.length >= 2 && s instanceof Player p) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                cfg.setSpawnLoc(p.getLocation().clone());
                saveSpawnerConfig(cfg);
                s.sendMessage("§aТочка спавна установлена!");
                if (cfg.isValid()) restartSpawner(cfg.getId());
                return true;
            }
            if (sub.equals("setdespawn") && a.length >= 2 && s instanceof Player p) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                cfg.setDespawnLoc(p.getLocation().clone());
                saveSpawnerConfig(cfg);
                s.sendMessage("§aТочка деспавна установлена!");
                if (cfg.isValid()) restartSpawner(cfg.getId());
                return true;
            }
            if (sub.equals("sethologram") && a.length >= 2 && s instanceof Player p) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                Location loc = p.getLocation().clone();
                if (a.length >= 3) {
                    try { loc.setYaw(Float.parseFloat(a[2])); }
                    catch (NumberFormatException e) { s.sendMessage("§cНеверный угол! Использую текущий поворот игрока."); }
                }
                cfg.setHologramLoc(loc);
                saveSpawnerConfig(cfg);
                if (hologramManager != null) createSpawnerHologram(cfg);
                s.sendMessage("§aТочка голограммы установлена! Yaw: " + loc.getYaw());
                return true;
            }
            if (sub.equals("test") && a.length >= 2) {
                String id = a[1].toLowerCase();
                if (!spawnerConfigs.containsKey(id)) { s.sendMessage("§cНе найден!"); return true; }
                spawnBrainrot(id);
                s.sendMessage("§aТестовый спавн!");
                return true;
            }
            if (sub.equals("speed") && a.length >= 3) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                try {
                    double speed = Double.parseDouble(a[2]);
                    cfg.setSpeed(speed);
                    saveSpawnerConfig(cfg);
                    restartSpawner(cfg.getId());
                    s.sendMessage("§aСкорость: " + speed);
                } catch (NumberFormatException e) { s.sendMessage("§cНеверное число!"); }
                return true;
            }
            if (sub.equals("cooldown") && a.length >= 3) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                try {
                    long sec = Long.parseLong(a[2]);
                    cfg.setCooldownTicks(sec * 20);
                    saveSpawnerConfig(cfg);
                    restartSpawner(cfg.getId());
                    s.sendMessage("§aКулдаун: " + sec + "с");
                } catch (NumberFormatException e) { s.sendMessage("§cНеверное число!"); }
                return true;
            }
            if (sub.equals("pause") && a.length >= 2) {
                SpawnerConfig cfg = spawnerConfigs.get(a[1].toLowerCase());
                if (cfg == null) { s.sendMessage("§cНе найден!"); return true; }
                cfg.setPaused(!cfg.isPaused());
                saveSpawnerConfig(cfg);
                if (cfg.isPaused()) { stopSpawner(cfg.getId()); s.sendMessage("§eПриостановлено"); }
                else { restartSpawner(cfg.getId()); s.sendMessage("§aВозобновлено"); }
                return true;
            }
            if (sub.equals("resetlegendary") && a.length >= 2) {
                String id = a[1].toLowerCase();
                if (!spawnerConfigs.containsKey(id)) { s.sendMessage("§cНе найден!"); return true; }
                resetLegendaryTimer(id);
                s.sendMessage("§aТаймер легендарного сброшен на 5 минут!");
                return true;
            }
            if (sub.equals("resetmythical") && a.length >= 2) {
                String id = a[1].toLowerCase();
                if (!spawnerConfigs.containsKey(id)) { s.sendMessage("§cНе найден!"); return true; }
                resetMythicalTimer(id);
                s.sendMessage("§aТаймер мифического сброшен на 15 минут!");
                return true;
            }
            if (sub.equals("timers") && a.length >= 2) {
                String id = a[1].toLowerCase();
                if (!spawnerConfigs.containsKey(id)) { s.sendMessage("§cНе найден!"); return true; }
                int legTicks = legendaryTicksLeft.getOrDefault(id, LEGENDARY_GUARANTEE_TICKS);
                int mythTicks = mythicalTicksLeft.getOrDefault(id, MYTHICAL_GUARANTEE_TICKS);
                s.sendMessage("§6=== Таймеры " + id + " ===");
                s.sendMessage("§6Легендарный: §e" + formatTime(legTicks / 20) + " §7(" + legTicks + " тиков)");
                s.sendMessage("§dМифический: §e" + formatTime(mythTicks / 20) + " §7(" + mythTicks + " тиков)");
                return true;
            }
            return true;
        }
    }

    public static BrainrotSpawner getInstance() { return instance; }

    public long getMobIncome(Entity entity) {
        MobData data = mobDataMap.get(entity);
        Mutation base = mobMutations.get(entity);
        if (data == null) return 2;
        double mult = (base != null ? base.incomeMultiplier : 1.0);
        for (Mutation extra : getExtraMutations(entity)) mult *= extra.incomeMultiplier;
        return Math.round(data.incomePerSecond * mult);
    }

    // ===== API для BrainrotEvents: выдача стакающихся мутаций мобам на конвейере =====

    /** Живые мобы спавнера (конвейер + доставка). */
    public List<Entity> getSpawnerMobs() {
        List<Entity> out = new ArrayList<>();
        for (Entity e : mobDataMap.keySet()) if (e != null && e.isValid() && !e.isDead()) out.add(e);
        return out;
    }

    /** Точки конвейеров (спавн/despawn всех валидных спавнеров) — для расчёта области ивентов. */
    public List<Location> getConveyorPoints() {
        List<Location> out = new ArrayList<>();
        for (SpawnerConfig cfg : spawnerConfigs.values()) {
            if (!cfg.isValid()) continue;
            out.add(cfg.getSpawnLoc().clone());
            out.add(cfg.getDespawnLoc().clone());
        }
        return out;
    }

    public boolean hasStackableMutation(Entity mob, String mutationName) {
        if (mob == null || mutationName == null) return false;
        return mob.getScoreboardTags().contains("MUTATION_" + mutationName.toUpperCase(Locale.ROOT));
    }

    /**
     * Навешивает стакающуюся мутацию (SNOWY / ELECTRIC / METEOR) на моба спавнера.
     * Возвращает false, если моб не наш, мутация неизвестна или уже висит.
     */
    public boolean applyStackableMutation(Entity mob, String mutationName) {
        if (mob == null || !mob.isValid() || mutationName == null) return false;
        if (!mobDataMap.containsKey(mob)) return false;
        Mutation target = null;
        for (Mutation m : STACKABLE_MUTATIONS) {
            if (m.name().equalsIgnoreCase(mutationName)) { target = m; break; }
        }
        if (target == null) return false;
        if (mob.getScoreboardTags().contains("MUTATION_" + target.name())) return false;
        mob.addScoreboardTag("MUTATION_" + target.name());
        mobExtrasCache.put(mob, extrasKey(mob));
        refreshMobNameTags(mob);
        return true;
    }

    public String getMobName(Entity entity) {
        MobData data = mobDataMap.get(entity);
        return data != null ? data.displayName : "Моб";
    }

    @Override
    public void onDisable() {
        // __leakfix__
        try { org.bukkit.Bukkit.getScheduler().cancelTasks(this); } catch (Throwable __t) {}
        try { org.bukkit.event.HandlerList.unregisterAll((org.bukkit.plugin.Plugin) this); } catch (Throwable __t) {}
        if (hologramUpdateTask != null) try { hologramUpdateTask.cancel(); } catch (Exception ignored) {}
        for (String spawnerId : new ArrayList<>(spawnerHolograms.keySet())) removeSpawnerHologram(spawnerId);
        spawnerHolograms.clear();
        for (String id : new ArrayList<>(spawnerTasks.keySet())) stopSpawner(id);
        for (BukkitRunnable task : movementTasks.values()) if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        for (BukkitRunnable task : deliveryTasks.values()) if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        for (BukkitRunnable task : rainbowAnimationTasks.values()) if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        for (BukkitRunnable task : wingAnimations.values()) if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        for (Entity hitbox : spongeHitboxMap.values()) if (hitbox != null && hitbox.isValid()) hitbox.remove();
        spongeHitboxMap.clear();
        for (Entity hitbox : rotWalkerHitboxMap.values()) if (hitbox != null && hitbox.isValid()) hitbox.remove();
        rotWalkerHitboxMap.clear();
        for (Entity carrier : dragonCarriers.values()) {
            if (carrier == null) continue;
            try { carrier.eject(); } catch (Throwable ignored) {}
            if (carrier.isValid()) try { carrier.remove(); } catch (Throwable ignored) {}
        }
        dragonCarriers.clear();
        for (BukkitRunnable task : rotWalkerAnimTasks.values()) if (task != null) try { task.cancel(); } catch (Exception ignored) {}
        rotWalkerAnimTasks.clear();
        for (List<ItemDisplay> wings : luckyBlockWings.values()) for (ItemDisplay wing : wings) if (wing != null && wing.isValid()) wing.remove();
        luckyBlockWings.clear();
        for (Map.Entry<Entity, List<ArmorStand>> entry : mobNameTags.entrySet()) {
            for (ArmorStand tag : entry.getValue()) if (tag != null && tag.isValid()) tag.remove();
            if (entry.getKey() != null && entry.getKey().isValid()) entry.getKey().remove();
        }
        mobNameTags.clear();
        mobDataMap.clear();
        mobHoloHeights.clear();
        movementTasks.clear();
        deliveryTasks.clear();
        rainbowAnimationTasks.clear();
        wingAnimations.clear();
        mobBuyers.clear();
        deliveryDestinations.clear();
        mobToSpawner.clear();
        mobClickCooldown.clear();
        mobMutations.clear();
        mobExtrasCache.clear();
        legendaryTicksLeft.clear();
        mythicalTicksLeft.clear();
        getLogger().info("§aBrainrotSpawner отключен!");
    }
}