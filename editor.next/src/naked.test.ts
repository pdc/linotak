import { describe, it, expect } from "vitest";
import { CurrentState, nextDynamic } from "./naked";

// If we keep coordinates as mupliples of (1/2)**n for small n we can use exact comparisons.

describe("nextDynamic", () => {
  it("returns crop when cropTopLeft is moving", () => {
    const currentState: CurrentState = {
      width: 960,
      height: 540,
      crop: { left: 0.125, top: 0.25, width: 0.5, height: 0.625 },
      focus: { x: 0.3, y: 0.4 },
      which: "cropTopLeft",
    };

    const event = { dx: 0, dy: 0 };
    const result = nextDynamic(currentState, event);

    expect(result?.crop).toEqual({
      left: 0.125,
      top: 0.25,
      width: 0.5,
      height: 0.625,
    });
    expect(result?.focus).toBeUndefined();
  });

  it("clips crop bottom ", () => {
    const currentState: CurrentState = {
      width: 960,
      height: 540,
      crop: { left: 0.125, top: 0.25, width: 0.5, height: 0.625 },
      focus: { x: 0.3, y: 0.4 },
      which: "cropBottomRight",
    };

    // When dragged outside of the image area …
    const event = { dx: 960, dy: 960 };
    const result = nextDynamic(currentState, event);

    // Then the crop width & height clipped to stay within image.
    expect(result?.crop).toEqual({
      left: 0.125,
      top: 0.25,
      width: 0.875,
      height: 0.75,
    });
    expect(result?.focus).toBeUndefined();
  });

  it("requires at least 32 screen pixels between control points when dragging top left", () => {
    // Given dragging top left corner …
    const currentState: CurrentState = {
      width: 512,
      height: 1024,
      crop: {
        left: 64 / 512,
        top: 256 / 1024,
        width: (320 - 64) / 512,
        height: (768 - 256) / 1024,
      },
      focus: { x: 0.3, y: 0.4 },
      which: "cropTopLeft",
    };

    // When dragged to within 32 screen pixels distance of bottom right …
    const event = { dx: 320 - 31 - 64, dy: 896 - 31 - 320 };
    const result = nextDynamic(currentState, event);

    // Then the crop width & height clipped to stay within image.
    // (Left is 288 / 512 which is 0.5625; top is 864 / 1024 = 0.84375 )
    expect(result?.crop).toEqual({
      left: (320 - 32) / 512,
      top: (768 - 32) / 1024,
      width: 32 / 512,
      height: 32 / 1024,
    });
    expect(result?.focus).toBeUndefined();
  });

  it("requires at least 32 screen pixels between control points when dragging bottom right", () => {
    // Given dragging bottom right corner …
    // And screen top left is 64, 256 …
    // And screen bottom right is 320, 896 …
    const currentState: CurrentState = {
      width: 512,
      height: 1024,
      crop: { left: 0.125, top: 0.25, width: 0.5, height: 0.625 },
      focus: { x: 0.3, y: 0.4 },
      which: "cropBottomRight",
    };

    // When dragged too far leftwards and topwards …
    const event = { dx: -320, dy: -896 };
    const result = nextDynamic(currentState, event);

    // Then left and top remain unchanged and the width is set to minimum.
    expect(result?.crop).toEqual({
      left: 0.125,
      top: 0.25,
      width: 32 / 512,
      height: 32 / 1024,
    });
    expect(result?.focus).toBeUndefined();
  });
});
