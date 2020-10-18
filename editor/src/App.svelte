<script>
  import { onMount } from "svelte";

  export let src;
  export let width;
  export let height;
  export let label;
  export let focusX = 0.5;
  export let focusY = 0.5;

  const r = 32; // Size of target circle.

  let image;
  let numbersDiv;

  // Size of Ooble crop preview.
  $: [cropWidth, cropHeight] = cropSize(1.0, width, height);
  let cropX, cropY;
  $: cropX = focusX * (width - cropWidth) + 0.5;
  $: cropY = focusY * (height - cropHeight) + 0.5;

  // Mastodon has a different way to determine the crop rectangle.
  $: [mastoWidth, mastoHeight] = cropSize(16.0 / 9.0, width, height);
  let mastoX, mastoY;
  $: if (mastoWidth === width) {
    mastoX = 0;
    mastoY = Math.min(
      height - mastoHeight,
      Math.max(0, focusY * height - 0.5 * mastoHeight)
    );
  } else {
    mastoX = Math.min(
      width - mastoWidth,
      Math.max(0, focusX * width - 0.5 * mastoWidth)
    );
    mastoY = 0;
  }

  /**
   * Calculate dimensions of crop rectangle.
   */
  function cropSize(ratio, width, height) {
    return width > height * ratio
      ? [height * ratio, height]
      : [width, width / ratio];
  }

  onMount(() => {
    const availableWidth = document.documentElement.clientWidth;
    const availableHeight = document.documentElement.clientHeight - numbersDiv.clientHeight;
    if (width > availableWidth || height > availableHeight) {
      // Scale down to fit.
      if (width / height < availableWidth / availableHeight) {
        width *= availableHeight / height;
        height = availableHeight;
      } else {
        height *= availableWidth / width;
        width = availableWidth;
      }
    }
  });

  function handleMouseDown(e) {
    const { left, top } = image.getBoundingClientRect();
    const dX = e.clientX - left - focusX * width;
    const dY = e.clientY - top - focusY * height;
    if (dX * dX + dY * dY <= r * r) {
      // It it inside the focus circle?
      e.preventDefault();
      const handleMousemove = (e) => {
        const { left, top } = image.getBoundingClientRect();
        focusX = Math.max(Math.min(1, (e.clientX - left - dX) / width), 0);
        focusY = Math.max(Math.min(1, (e.clientY - top - dY) / height), 0);
      };
      const handleMouseUp = (e) => {
        e.target.removeEventListener("mousemove", handleMousemove);
        e.target.removeEventListener("mouseup", handleMouseUp);
      };

      e.target.addEventListener("mousemove", handleMousemove);
      e.target.addEventListener("mouseup", handleMouseUp);
    }
  }
</script>

<style>
  main {
    height: 100vh;
    display: grid;
    grid-template-rows: max-content 1fr;
  }

  @media (min-width: 640px) {
    main {
      max-width: none;
    }
  }
</style>

<div class="focus-editor">
  <svg
    class="im"
    {width}
    {height}
    viewBox="0 0 {width} {height}"
    on:mousedown={handleMouseDown}>
    <image xlink:href={src} {width} {height} bind:this={image} />
    <circle
      cx={focusX * width}
      cy={focusY * height}
      r={32}
      stroke-width="1"
      stroke="#B0A"
      fill="none" />
    <rect
      x={mastoX + 0.5}
      y={mastoY + 0.5}
      width={mastoWidth - 1}
      height={mastoHeight - 1}
      stroke-width="1"
      stroke="#F56"
      fill="none" />
    <rect
      x={cropX + 0.5}
      y={cropY + 0.5}
      width={cropWidth - 1}
      height={cropHeight - 1}
      stroke-width="1"
      stroke="#0BA"
      fill="none" />
  </svg>
  <div bind:this={numbersDiv}>
    {#if label}<label for="id_focus_x">{label}</label>{/if}
    <input
      name="focus_x"
      id="id_focus_x"
      bind:value={focusX}
      type="number"
      step="any"
      required />
    <input
	  name="focus_y"
	  id="id_focus_y"
      bind:value={focusY}
      type="number"
      step="any"
      required />
  </div>
</div>
