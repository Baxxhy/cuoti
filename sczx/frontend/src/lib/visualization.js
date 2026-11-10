const actions = [
  "left_add",
  "right_add",
  "both_add",
  "left_subtract",
  "right_subtract",
  "both_subtract",
  "reset",
];
export function balanceSpec(config) {
  const value = config.initial
    ? config
    : {
        version: 1,
        type: "balance",
        initial: { left: config.base, right: config.base },
        step: config.step,
        minimum: 0,
        maximum: config.base + config.step * config.max,
        actions,
        learningGoal: "比较单侧变化与两边共同变化",
        completion: "balanced_with_explanation",
      };
  if (
    !["balance", "equality_operations"].includes(value.type) ||
    !value.initial ||
    ![
      value.initial.left,
      value.initial.right,
      value.step,
      value.minimum,
      value.maximum,
    ].every(Number.isFinite) ||
    value.step <= 0 ||
    value.minimum < 0 ||
    value.maximum > 10000 ||
    value.maximum <= value.minimum ||
    Object.values(value.initial).some(
      (x) => x < value.minimum || x > value.maximum,
    ) ||
    !Array.isArray(value.actions) ||
    value.actions.some((a) => !actions.includes(a))
  )
    throw new Error("互动参数无效");
  return value;
}
export function applyBalance(spec, state, action) {
  if (!spec.actions.includes(action)) throw new Error("不支持的操作");
  if (action === "reset") return { ...spec.initial };
  const d = spec.step * (action.endsWith("subtract") ? -1 : 1),
    next = { ...state };
  for (const side of ["left", "right"])
    if (action.startsWith(side) || action.startsWith("both")) next[side] += d;
  if (
    Object.values(next).some(
      (x) => !Number.isFinite(x) || x < spec.minimum || x > spec.maximum,
    )
  )
    throw new Error("操作超出边界");
  return next;
}
