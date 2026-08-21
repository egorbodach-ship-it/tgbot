package Polfg.Polfg;

import org.bukkit.Bukkit;
import org.bukkit.entity.Entity;

import java.lang.reflect.Method;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Мостик к ModelEngine R4 целиком на рефлексии.
 *
 * Почему рефлексия, а не зависимость в pom.xml: ME лежит в приватном репозитории
 * Lumine, до которого GitHub Actions не достаёт, а в этом репозитории и так все
 * межплагинные вызовы сделаны через Bukkit.getPluginManager() + рефлексию.
 * Плюс так один и тот же jar работает и с ME, и без него: нет плагина — мобы
 * просто остаются ванильными.
 *
 * Сигнатуры между R4.0.x и R4.1.0 местами разъехались (где-то double, где-то
 * float, addModel то возвращает Optional, то сам ActiveModel), поэтому методы
 * ищутся по имени и числу аргументов, а типы подставляются под то, что реально
 * объявлено в найденном методе.
 */
public final class ModelEngineHook {

    private static final String API_CLASS = "com.ticxo.modelengine.api.ModelEngineAPI";
    private static final String LOG = "[BRAINROT/ME] ";

    private static boolean probed = false;
    private static boolean available = false;

    private static Class<?> apiClass;
    private static Method mCreateActiveModel;
    private static Method mCreateModeledEntity;
    private static Method mRemoveModeledEntity;

    /** UUID сущности → ActiveModel */
    private static final Map<UUID, Object> MODELS = new ConcurrentHashMap<>();
    /** UUID сущности → ModeledEntity */
    private static final Map<UUID, Object> RIGS = new ConcurrentHashMap<>();

    private ModelEngineHook() {}

    // ── доступность ───────────────────────────────────────────────────────

    public static boolean isAvailable() {
        if (!probed) probe();
        return available;
    }

    private static synchronized void probe() {
        if (probed) return;
        probed = true;
        try {
            if (Bukkit.getPluginManager().getPlugin("ModelEngine") == null) {
                Bukkit.getLogger().info(LOG + "плагин ModelEngine не найден, модели отключены");
                return;
            }
            apiClass = Class.forName(API_CLASS);
            mCreateActiveModel = findStatic(apiClass, "createActiveModel", 1);
            mCreateModeledEntity = findStatic(apiClass, "createModeledEntity", 1);
            mRemoveModeledEntity = findStatic(apiClass, "removeModeledEntity", 1);
            if (mCreateActiveModel == null || mCreateModeledEntity == null) {
                Bukkit.getLogger().warning(LOG + "ModelEngine есть, но API незнакомый "
                        + "(нет createActiveModel/createModeledEntity) — модели отключены");
                return;
            }
            available = true;
            Bukkit.getLogger().info(LOG + "ModelEngine подключён");
        } catch (ClassNotFoundException e) {
            Bukkit.getLogger().warning(LOG + "класс " + API_CLASS + " не найден — нужен ModelEngine R4");
        } catch (Throwable t) {
            Bukkit.getLogger().warning(LOG + "не удалось подключиться к ModelEngine: " + t);
        }
    }

    // ── навесить и снять модель ───────────────────────────────────────────

    /**
     * Навешивает блюпринт на сущность и прячет её саму.
     *
     * @param blueprint id блюпринта = имя файла в plugins/ModelEngine/blueprints
     *                  без расширения, например "samovarus_maximus"
     * @return true, если модель реально навесилась
     */
    public static boolean attach(Entity mob, String blueprint) {
        if (mob == null || blueprint == null || blueprint.isEmpty()) return false;
        if (!isAvailable()) return false;
        UUID id = mob.getUniqueId();
        try {
            Object model = mCreateActiveModel.invoke(null, blueprint.toLowerCase(Locale.ROOT));
            if (model == null) {
                Bukkit.getLogger().warning(LOG + "блюпринт \"" + blueprint + "\" не загружен — "
                        + "проверь plugins/ModelEngine/blueprints и сделай /meg reload");
                return false;
            }
            Object rig = mCreateModeledEntity.invoke(null, mob);
            if (rig == null) {
                Bukkit.getLogger().warning(LOG + "createModeledEntity вернул null для " + mob.getType());
                return false;
            }

            // addModel(model, true) — второй аргумент «дублировать на клиентов сразу».
            // В части сборок метод возвращает Optional<ActiveModel> или сам ActiveModel:
            // если вернул живой объект, дальше анимации надо крутить именно на нём.
            Object attached = null;
            Method add2 = findMethod(rig.getClass(), "addModel", 2);
            if (add2 != null) {
                attached = add2.invoke(rig, buildAddModelArgs(add2.getParameterTypes(), model, true));
            } else {
                Method add1 = findMethod(rig.getClass(), "addModel", 1);
                if (add1 == null) {
                    Bukkit.getLogger().warning(LOG + "у ModeledEntity нет addModel — версия ME не поддерживается");
                    return false;
                }
                attached = add1.invoke(rig, model);
            }
            Object live = unwrap(attached);
            if (live != null && live.getClass() == model.getClass()) model = live;

            // Ванильную сущность-подложку убираем с глаз: она нужна только как
            // якорь позиции и хитбокс под клики игрока.
            Method vis = findMethod(rig.getClass(), "setBaseEntityVisible", 1);
            if (vis != null) vis.invoke(rig, false);

            MODELS.put(id, model);
            RIGS.put(id, rig);
            return true;
        } catch (Throwable t) {
            Bukkit.getLogger().warning(LOG + "не удалось навесить \"" + blueprint + "\": " + rootCause(t));
            MODELS.remove(id);
            RIGS.remove(id);
            return false;
        }
    }

    /** Снимает модель. Дёргать обязательно, иначе ME оставит висеть рига без хозяина. */
    public static void detach(Entity mob) {
        if (mob == null) return;
        UUID id = mob.getUniqueId();
        Object rig = RIGS.remove(id);
        MODELS.remove(id);
        if (rig == null) return;
        try {
            Method destroy = findMethod(rig.getClass(), "destroy", 0);
            if (destroy != null) {
                destroy.invoke(rig);
                return;
            }
            if (mRemoveModeledEntity != null) mRemoveModeledEntity.invoke(null, id);
        } catch (Throwable t) {
            Bukkit.getLogger().warning(LOG + "не удалось снять модель: " + rootCause(t));
        }
    }

    /** Есть ли на этой сущности наша модель. */
    public static boolean hasModel(Entity mob) {
        return mob != null && MODELS.containsKey(mob.getUniqueId());
    }

    // ── анимации ──────────────────────────────────────────────────────────

    /** Плавно, с обычной скоростью, не перебивая то же самое, если уже играет. */
    public static boolean play(Entity mob, String animation) {
        return play(mob, animation, 0.2, 0.2, 1.0, false);
    }

    /** Перебить текущую анимацию этой (для hurt/death, где ждать нельзя). */
    public static boolean playForced(Entity mob, String animation) {
        return play(mob, animation, 0.0, 0.2, 1.0, true);
    }

    /**
     * @param lerpIn  секунды плавного входа
     * @param lerpOut секунды плавного выхода
     * @param speed   1.0 — как в блокбенче
     * @param force   перебить уже играющую анимацию с тем же именем
     */
    public static boolean play(Entity mob, String animation, double lerpIn, double lerpOut,
                               double speed, boolean force) {
        if (mob == null || animation == null) return false;
        Object model = MODELS.get(mob.getUniqueId());
        if (model == null) return false;
        try {
            Method getHandler = findMethod(model.getClass(), "getAnimationHandler", 0);
            if (getHandler == null) return false;
            Object handler = getHandler.invoke(model);
            if (handler == null) return false;
            for (int argc = 5; argc >= 1; argc--) {
                Method play = findMethod(handler.getClass(), "playAnimation", argc);
                if (play == null) continue;
                Object[] args = buildArgs(play.getParameterTypes(), animation,
                        new double[]{lerpIn, lerpOut, speed}, force);
                if (args == null) continue;
                play.invoke(handler, args);
                return true;
            }
            return false;
        } catch (Throwable t) {
            Bukkit.getLogger().warning(LOG + "анимация \"" + animation + "\" не проигралась: " + rootCause(t));
            return false;
        }
    }

    public static void stop(Entity mob, String animation) {
        if (mob == null || animation == null) return;
        Object model = MODELS.get(mob.getUniqueId());
        if (model == null) return;
        try {
            Method getHandler = findMethod(model.getClass(), "getAnimationHandler", 0);
            if (getHandler == null) return;
            Object handler = getHandler.invoke(model);
            if (handler == null) return;
            Method stop = findMethod(handler.getClass(), "stopAnimation", 1);
            if (stop != null) stop.invoke(handler, animation);
        } catch (Throwable ignored) {
        }
    }

    // ── рефлексивная мелочь ───────────────────────────────────────────────

    private static Method findStatic(Class<?> owner, String name, int argc) {
        Method m = findMethod(owner, name, argc);
        return (m != null && java.lang.reflect.Modifier.isStatic(m.getModifiers())) ? m : null;
    }

    private static Method findMethod(Class<?> owner, String name, int argc) {
        Method best = null;
        for (Method m : owner.getMethods()) {
            if (!m.getName().equals(name) || m.getParameterCount() != argc) continue;
            // из перегрузок берём ту, у которой аргументы попроще: меньше шансов
            // напороться на вариант с внутренними типами ME
            if (best == null || simpler(m.getParameterTypes(), best.getParameterTypes())) best = m;
        }
        if (best != null) {
            try { best.setAccessible(true); } catch (Throwable ignored) {}
        }
        return best;
    }

    private static boolean simpler(Class<?>[] a, Class<?>[] b) {
        return score(a) < score(b);
    }

    private static int score(Class<?>[] types) {
        int s = 0;
        for (Class<?> t : types) {
            if (t == String.class || t.isPrimitive()) continue;
            s += t.getName().startsWith("com.ticxo") ? 2 : 1;
        }
        return s;
    }

    /**
     * Раскладывает наши значения по объявленным типам аргументов: строка идёт в
     * String, флаг — в boolean, числа — по порядку в любые числовые слоты, всё
     * прочее (объекты вроде ActiveModel) берётся из extras.
     * Возвращает null, если под какой-то аргумент нечего подставить.
     */
    private static Object[] buildArgs(Class<?>[] types, String text, double[] nums, boolean flag) {
        Object[] out = new Object[types.length];
        int ni = 0;
        for (int i = 0; i < types.length; i++) {
            Class<?> t = types[i];
            if (t == String.class) {
                if (text == null) return null;
                out[i] = text;
            } else if (t == boolean.class || t == Boolean.class) {
                out[i] = flag;
            } else if (t == double.class || t == Double.class) {
                out[i] = ni < nums.length ? nums[ni++] : 1.0;
            } else if (t == float.class || t == Float.class) {
                out[i] = (float) (ni < nums.length ? nums[ni++] : 1.0);
            } else if (t == int.class || t == Integer.class) {
                out[i] = (int) Math.round(ni < nums.length ? nums[ni++] : 1.0);
            } else {
                return null;
            }
        }
        return out;
    }

    /** Аргументы для addModel: объект модели + флаг, порядок берём из объявления. */
    private static Object[] buildAddModelArgs(Class<?>[] types, Object obj, boolean flag) {
        Object[] out = new Object[types.length];
        boolean objUsed = false;
        for (int i = 0; i < types.length; i++) {
            Class<?> t = types[i];
            if (t == boolean.class || t == Boolean.class) {
                out[i] = flag;
            } else if (!objUsed) {
                out[i] = obj;
                objUsed = true;
            } else {
                out[i] = null;
            }
        }
        return out;
    }

    private static Object unwrap(Object value) {
        if (value instanceof Optional<?> opt) return opt.orElse(null);
        return value;
    }

    private static String rootCause(Throwable t) {
        Throwable c = t;
        while (c.getCause() != null && c.getCause() != c) c = c.getCause();
        return c.getClass().getSimpleName() + ": " + c.getMessage();
    }
}
