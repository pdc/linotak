import { Signal } from "signal-polyfill";
import effect from "./fw/effect";

/**
 * Extra information about the image not stored in the form.
 */
export interface ImageData {
  /// Natural width of the source image, in pixels.
  width?: number;

  /// Natural height of the source image, in pixels.
  height?: number;

  /// CSS colour expression
  placeholder?: string;
}

/** Coordinates are fractions of the width or height of the image, range 0.0 to 1.0. */
interface Point {
  x: number;
  y: number;
}

/** Coordinates are fractions of the width or height of the image, range 0.0 to 1.0. */
interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export default function wireUp(
  imageElt: HTMLImageElement,
  formElt: HTMLFormElement,
  imageData: ImageData,
) {
  if (!imageElt) {
    console.error("Cannot create image editor without image element!");
    return;
  }
  if (!formElt) {
    console.error("Cannot create image editor without form element!");
    return;
  }

  const r = 32;

  // Image elt can have data-* attributes,
  // used when the image has been resized or cropped.
  const naturalWidth = imageData.width ?? imageElt.width;
  const naturalHeight = imageData.height ?? imageElt.height;

  // Colour used for the part of the image that is missing because
  // the image source is cropped.
  const placeholder: string = imageData.placeholder ?? "#888";
  const src = imageElt.src;

  // Get a number out of the form.
  const acquire = (name: string, defaultValue: number): number => {
    const itemElt = formElt.elements.namedItem(name);
    if (itemElt && "value" in itemElt) {
      return +(itemElt?.value ?? defaultValue);
    }
    return defaultValue;
  };

  // Copy this number in to the form.
  const assign = (name: string, value: string | number) => {
    const itemElt = formElt.elements.namedItem(name);
    if (itemElt && "value" in itemElt) {
      itemElt.value = "" + value;
    }
  };

  // Create Signal instances.

  // The area available for rendering the UI. Changes when window resized.
  const availableSize = new Signal.State({
    width: document.documentElement.clientWidth,
    height: document.documentElement.clientHeight,
    /* - numbersDiv.clientHeight */
  });

  // Size of the UI, in pixels. Depends on size of containing element.
  const sizePixels = new Signal.Computed(() => {
    const { width: availableWidth, height: availableHeight } =
      availableSize.get();

    let result: { width: number; height: number };
    if (naturalWidth <= availableWidth && naturalHeight <= availableHeight) {
      result = { width: naturalWidth, height: naturalHeight };
    } else if (
      naturalWidth / naturalHeight
      < availableWidth / availableHeight
    ) {
      // Shrink to fit vertical space.
      result = {
        width: (naturalWidth * availableHeight) / naturalHeight,
        height: availableHeight,
      };
    } else {
      // Shrink to fit horizontal space.
      result = {
        width: availableWidth,
        height: (naturalHeight * availableWidth) / naturalWidth,
      };
    }
    return result;
  });

  // The crop already applied to the image. Coordinates are in range 0 to 1.
  // We assume the image element covers this portion of the image area.
  const imageCrop: Rect = {
    left: acquire("crop_left", 0.0),
    top: acquire("crop_top", 0.0),
    width: acquire("crop_width", 1.0),
    height: acquire("crop_height", 1.0),
  };

  // User-selected crop. Coordinates are in range 0 to 1
  const crop = new Signal.State<Rect>(imageCrop);

  // User-selected focus point. Coordinates are in the range 0 to 1 relative to the crop rect.
  const focus = new Signal.State<Point>({
    x: acquire("focus_x", 0.5),
    y: acquire("focus_y", 0.5),
  });

  // This is set while the user is dragging one of the points about.
  const dynamic = new Signal.State<{ crop?: Rect; focus?: Point } | undefined>(
    undefined,
  );

  // The crop that is currently being displayed.
  const displayedCrop = new Signal.Computed(() => {
    const fallback = crop.get();
    const active = dynamic.get();

    return active?.crop ?? fallback;
  });
  // The focus that is currently being displayed.
  const displayedFocus = new Signal.Computed(() => {
    const fallback = focus.get();
    const active = dynamic.get();

    return active?.focus ?? fallback;
  });

  // Effect definitions.
  // These are functions that are automatically re-executed when their dependencies
  // change. They can retrurn a function that is called to undo the effect; this
  // is called before re-executing the function.

  /// Create the user interface and add event listeners.
  // Depends on the size of the available area only.
  // Don’t add dependencies on other signals; we don’t want to be
  // continually re-rendering the UI.
  function render() {
    // Don’t forget to reference any signals we depend on.
    const { width, height } = sizePixels.get();

    const outerElt = document.getElementById("focusPoint") || imageElt;

    // The SVG has to be wrapped in DIV otherwise we don’t seem to get the image element bound.
    outerElt.outerHTML = `
      <div class="focus-point" id="focusPoint">
        <svg class="im" width=${width} height=${height} viewBox="0 0 ${width} ${height}" style="display: block">
          <rect width=${width} height=${height} fill="${placeholder}" />
          <image
            xlink:href="${src}"
            x=${imageCrop.left * width}
            y=${imageCrop.top * height}
            width=${imageCrop.width * width}
            height=${imageCrop.height * height}
          />
          <g fill="rgba(0,0,0, 0.25)" id="focusPointCrop"  >
            <rect id="cropTop" width=${width} height=0 />
            <rect id="cropBottom" width=${width} y=${height} height=0 />
            <rect id="cropLeft" width=0 y=0 height=0 />
            <rect id="cropRight" x=${width} width=0 y=0 height=0 />
          </g>
          <g stroke-width="1">
            <circle id="cropTopLeft" cx=0 cy=0 r=32 stroke="#F30" fill="rgba(255, 51, 0, 0.1)" cursor="move" />
            <circle id="cropBottomRight" cx=${width} cy=${height} r=32 stroke="#EF0" fill="rgba(238, 255, 0, 0.1)" cursor="nwse-resize" />
          </g>
          <g stroke-width="1">
            <rect id="mastoFrame" x=0 y=0 width=${width} height=${height} stroke="#F56" fill="none"/>
            <rect id="linotakFrame" x=0 y=0 width=${width} height=${height} stroke="#0BA" fill="none"/>
            <circle id="focus" cx=${0.5 * width} cy=${0.5 * height} r=${r} stroke="#B0A" fill="rgba(187, 0, 170, 0.1)"/>
          </g>
        </svg>
      </div>
    `;

    // Event handler for dragging circle.
    const handleMouseDown = (event: MouseEvent) => {
      const node = event.currentTarget as SVGCircleElement;
      const x = event.clientX;
      const y = event.clientY;
      const which = node?.id;
      let dx: number = 0;
      let dy: number = 0;

      const nextDynamic = () => {
        const prevCrop = crop.get();
        const prevFocus = focus.get();

        const right = prevCrop.left + prevCrop.width;
        const bottom = prevCrop.top + prevCrop.height;

        if (which == "focus") {
          return {
            focus: {
              x: Math.max(
                Math.min(1, prevFocus.x + dx / (prevCrop.width * width)),
                0,
              ),
              y: Math.max(
                Math.min(1, prevFocus.y + dy / (prevCrop.height * height)),
                0,
              ),
            },
          };
        } else if (which === "cropTopLeft") {
          const newLeft = prevCrop.left + dx / width;
          const newTop = prevCrop.top + dy / height;
          return {
            crop: {
              ...prevCrop,
              left: Math.max(Math.min(1.0 - r / width, newLeft), 0.0),
              top: Math.max(Math.min(1.0 - r / height, newTop), 0.0),
              width: Math.max(right - newLeft, r / width),
              height: Math.max(bottom - newTop, r / height),
            },
          };
        } else if (which == "cropBottomRight") {
          const newWidth = prevCrop.width + dx / width;
          const newHeight = prevCrop.height + dy / height;
          return {
            crop: {
              ...prevCrop,
              width: Math.max(
                Math.min(1.0 - prevCrop.left, newWidth),
                r / width,
              ),
              height: Math.max(
                Math.min(1.0 - prevCrop.top, newHeight),
                r / height,
              ),
            },
          };
        }
      };

      dynamic.set(nextDynamic());

      const handleMouseMove = (e: MouseEvent) => {
        dx = e.clientX - x;
        dy = e.clientY - y;
        dynamic.set(nextDynamic());
      };
      const handleMouseUp = (e: MouseEvent) => {
        dx = e.clientX - x;
        dy = e.clientY - y;
        const next = nextDynamic();
        if (next?.crop) {
          crop.set(next.crop);
        }
        if (next?.focus) {
          focus.set(next.focus);
        }
        dynamic.set(undefined);

        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    };
    const handleTouchStart = e => {};

    // Add event handlers.
    for (const which of ["cropTopLeft", "cropBottomRight", "focus"]) {
      const node = document.getElementById(which);
      node?.addEventListener("mousedown", handleMouseDown);
      node?.addEventListener("touchstart", handleTouchStart);
    }

    // Return the destructor.
    return () => {
      for (const which of ["cropTopLeft", "cropBottomRight", "focus"]) {
        const node = document.getElementById(which);
        node?.removeEventListener("mousedown", handleMouseDown);
        node?.removeEventListener("touchstart", handleTouchStart);
      }
    };
  }
  effect(render);

  // Effects that update individual SVG elements in the UI.
  // Each SVG element has its own effect function.

  effect(() => {
    const { height } = sizePixels.get();
    const { top: cropTop } = displayedCrop.get();
    const rectElt = document.getElementById("cropTop");
    if (!rectElt) {
      return;
    }
    rectElt.setAttribute("height", "" + cropTop * height);
  });
  effect(() => {
    const { height } = sizePixels.get();
    const { top: cropTop, height: cropHeight } = displayedCrop.get();
    const rectElt = document.getElementById("cropBottom");
    if (!rectElt) {
      return;
    }
    rectElt.setAttribute("y", "" + (+cropTop + +cropHeight) * height);
    rectElt.setAttribute("height", "" + (1 - cropTop - cropHeight) * height);
  });
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      height: cropHeight,
    } = displayedCrop.get();
    const rectElt = document.getElementById("cropLeft");
    if (!rectElt) {
      return;
    }
    rectElt.setAttribute("width", "" + cropLeft * width);
    rectElt.setAttribute("y", "" + cropTop * height);
    rectElt.setAttribute("height", "" + cropHeight * height);
  });
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      width: cropWidth,
      height: cropHeight,
    } = displayedCrop.get();
    const rectElt = document.getElementById("cropRight");
    if (!rectElt) {
      return;
    }
    rectElt.setAttribute("x", "" + (+cropLeft + +cropWidth) * width);
    rectElt.setAttribute("width", "" + (1 - cropLeft - cropWidth) * width);
    rectElt.setAttribute("y", "" + cropTop * height);
    rectElt.setAttribute("height", "" + cropHeight * height);
  });
  effect(() => {
    const { width, height } = sizePixels.get();
    const { left: cropLeft, top: cropTop } = displayedCrop.get();
    const circleElt = document.getElementById("cropTopLeft");
    if (!circleElt) {
      return;
    }
    circleElt.setAttribute("cx", "" + cropLeft * width);
    circleElt.setAttribute("cy", "" + cropTop * height);
  });
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      width: cropWidth,
      height: cropHeight,
    } = displayedCrop.get();
    const circleElt = document.getElementById("cropBottomRight");
    if (!circleElt) {
      return;
    }
    circleElt.setAttribute("cx", "" + (+cropLeft + +cropWidth) * width);
    circleElt.setAttribute("cy", "" + (+cropTop + +cropHeight) * height);
  });
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      width: cropWidth,
      height: cropHeight,
    } = displayedCrop.get();
    const { x: focusX, y: focusY } = displayedFocus.get();
    const circleElt = document.getElementById("focus");
    if (!circleElt) {
      return;
    }
    circleElt.setAttribute("cx", "" + (cropLeft + focusX * cropWidth) * width);
    circleElt.setAttribute("cy", "" + (cropTop + focusY * cropHeight) * height);
  });
  // Frame showing how we expect Mastodon to crop the image.
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      width: cropWidth,
      height: cropHeight,
    } = displayedCrop.get();
    const { x: focusX, y: focusY } = displayedFocus.get();
    const rectElt = document.getElementById("mastoFrame");
    if (!rectElt) {
      return;
    }

    const ratio = 16 / 9;

    if (cropWidth * width < cropHeight * height * ratio) {
      // Frame extends from left to eight edges.
      const frameHeight = (cropWidth * width) / ratio;
      const frameTop = Math.min(
        (cropTop + cropHeight) * height - frameHeight,
        Math.max(
          cropTop * height,
          (cropTop + focusY * cropHeight) * height - 0.5 * frameHeight,
        ),
      );
      rectElt.setAttribute("x", "" + cropLeft * width);
      rectElt.setAttribute("y", "" + frameTop);
      rectElt.setAttribute("width", "" + cropWidth * width);
      rectElt.setAttribute("height", "" + frameHeight);
    } else {
      // Frame extends from top to bottom.
      const frameWidth = cropHeight * height * ratio;
      const frameLeft = Math.min(
        (cropLeft + cropWidth) * width - frameWidth,
        Math.max(
          cropLeft * width,
          (cropLeft + focusX * cropWidth) * width - 0.5 * frameWidth,
        ),
      );
      rectElt.setAttribute("x", "" + frameLeft);
      rectElt.setAttribute("y", "" + cropTop * height);
      rectElt.setAttribute("width", "" + frameWidth);
      rectElt.setAttribute("height", "" + cropHeight * height);
    }
  });
  // Frame showing how we intend Linotak to crop the thumbnail.
  effect(() => {
    const { width, height } = sizePixels.get();
    const {
      left: cropLeft,
      top: cropTop,
      width: cropWidth,
      height: cropHeight,
    } = displayedCrop.get();
    const { x: focusX, y: focusY } = displayedFocus.get();
    const rectElt = document.getElementById("linotakFrame");
    if (!rectElt) {
      return;
    }

    const ratio = 1 / 1;

    if (cropWidth * width < cropHeight * height * ratio) {
      // Frame extends from left to eight edges.
      // Dimensions of frame in pixels.
      const frameHeight = (cropWidth * width) / ratio;
      const frameTop =
        cropTop * height
        + Math.min(
          cropHeight * height - frameHeight,
          Math.max(0, focusY * (cropHeight * height - frameHeight)),
        );
      rectElt.setAttribute("x", "" + cropLeft * width);
      rectElt.setAttribute("y", "" + frameTop);
      rectElt.setAttribute("width", "" + cropWidth * width);
      rectElt.setAttribute("height", "" + frameHeight);
    } else {
      // Frame extends from top to bottom.
      // Dimensions of frame in pixels.
      const frameWidth = cropHeight * height * ratio;
      const frameLeft =
        cropLeft * width
        + Math.min(
          cropWidth * width - frameWidth,
          Math.max(0, focusX * (cropWidth * width - frameWidth)),
        );
      rectElt.setAttribute("x", "" + frameLeft);
      rectElt.setAttribute("y", "" + cropTop * height);
      rectElt.setAttribute("width", "" + frameWidth);
      rectElt.setAttribute("height", "" + cropHeight * height);
    }
  });

  // Copy updated crop & focus to the form.

  effect(() => {
    const { left, top, width, height } = displayedCrop.get();
    assign("crop_left", left);
    assign("crop_top", top);
    assign("crop_width", width);
    assign("crop_height", height);
  });
  effect(() => {
    const { x, y } = displayedFocus.get();
    assign("focus_x", x);
    assign("focus_y", y);
  });

  // Now event handlers that change state.
  //
  //

  // Temporary fudging of the number.

  // const randomize = () => {
  //   const left = Math.random() * 0.1;
  //   const top = Math.random() * 0.2;
  //   const width = Math.random() * (1 - left);
  //   const height = Math.random() * (1 - top);
  //   const x = Math.random();
  //   const y = Math.random();
  //   crop.set({ left, top, width, height });
  //   focus.set({ x, y });
  // };
  // window.setInterval(randomize, 1500);
}
