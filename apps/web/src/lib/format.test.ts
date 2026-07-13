import { describe, expect, it } from "vitest";

import { formatDelta, formatTick, formatValue, signed } from "@/lib/format";

describe("formatValue", () => {
  it("renders the delta of a rate in points, never in percent", () => {
    // The trap the API's `percent_point` format exists to prevent: 20% -> 24% gained four
    // points. Rendering the same 0.04 as a percent says "4%", which is a different claim.
    expect(formatValue(0.04, "percent_point")).toBe("+4.0 pts");
    expect(formatValue(0.04, "percent")).toBe("4%");
  });

  it("signs a delta so it reads as a direction", () => {
    expect(formatValue(-0.032, "percent_point")).toBe("−3.2 pts");
  });

  it("renders a rate as a percent", () => {
    expect(formatValue(0.2417, "percent")).toBe("24.2%");
  });

  it("renders currency without cents", () => {
    expect(formatValue(6000, "currency")).toBe("$6,000");
  });

  it("groups counts", () => {
    expect(formatValue(86973, "number")).toBe("86,973");
  });

  it("renders a gap as a dash, not a zero", () => {
    // A null is a bucket with no rows, or the first bucket of a comparison. Zero is a claim.
    expect(formatValue(null, "number")).toBe("—");
    expect(formatValue(null, "currency")).toBe("—");
  });
});

describe("formatDelta", () => {
  it("signs a percent change and keeps it a percent", () => {
    // A count's delta comes back as a ratio: -0.44 is a 44% drop.
    expect(formatDelta(-0.44, "percent")).toBe("−44.0%");
    expect(formatDelta(0.2, "percent")).toBe("+20.0%");
  });

  it("keeps a rate's delta in points, always signed", () => {
    expect(formatDelta(0.04, "percent_point")).toBe("+4.0 pts");
  });

  it("signs a currency change", () => {
    expect(formatDelta(-6000, "currency")).toBe("−$6,000");
  });

  it("renders a missing delta as a dash", () => {
    expect(formatDelta(null, "percent")).toBe("—");
  });
});

describe("signed", () => {
  it("uses a minus sign rather than a hyphen so figures align in a column", () => {
    expect(signed(-4)).toBe("−4");
    expect(signed(-4).charCodeAt(0)).toBe(0x2212);
  });

  it("leaves zero unsigned", () => {
    expect(signed(0)).toBe("0");
  });
});

describe("formatTick", () => {
  it("abbreviates a cramped axis", () => {
    expect(formatTick(86973, "number")).toBe("87K");
    expect(formatTick(1500000, "currency")).toBe("$1.5M");
  });

  it("drops fractional percent on ticks", () => {
    expect(formatTick(0.2417, "percent")).toBe("24%");
  });
});
