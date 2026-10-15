import { polish } from "./Chart";

test("bars with long names lie flat, the legend is one slim row on top, value axes use short numbers", () => {
  const rows = [{ entity: "Evergreen Family Trust", view_type: "administrator", cash_usd: 1 }, { entity: "Entity B", view_type: "trading export", cash_usd: 2 }];
  const spec = { mark: { type: "bar" }, encoding: { x: { field: "entity", type: "nominal" }, y: { field: "cash_usd", type: "quantitative" },
    color: { field: "view_type", type: "nominal" }, xOffset: { field: "view_type" } } };
  const enc = polish(spec, rows).encoding as Record<string, Record<string, unknown>>;
  expect(enc.y!.field).toBe("entity");
  expect(enc.x!.field).toBe("cash_usd");
  expect(enc.yOffset).toEqual({ field: "view_type" });
  expect(enc.xOffset).toBeUndefined();
  expect((enc.x!.axis as Record<string, unknown>).format).toBe("~s");
  expect((enc.color!.legend as Record<string, unknown>).orient).toBe("top");
});

test("short names stay as upright bars and a person's own axis setting wins", () => {
  const rows = [{ m: "Jan", v: 1 }, { m: "Feb", v: 2 }];
  const spec = { mark: "bar", encoding: { x: { field: "m", type: "nominal" }, y: { field: "v", type: "quantitative", axis: { title: "Value" } } } };
  const enc = polish(spec, rows).encoding as Record<string, Record<string, unknown>>;
  expect(enc.x!.field).toBe("m");
  expect((enc.y!.axis as Record<string, unknown>).title).toBe("Value");
});
