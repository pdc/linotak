<script>
    import { createEventDispatcher, onMount } from "svelte";
    import { pannable } from "./pannable.js";

    export let src; // URL reference to a representation of the image being edited.
    export let width; // Dimensions of the source image.
    export let height;
    export let focusX = 0.5; // Initial or corrent value of the focus point.
    export let focusY = 0.5;

    const r = 32; // Size of target circle.

    const dispatch = createEventDispatcher();
    let image; // Bound to the image element.

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
        const availableHeight = document.documentElement.clientHeight;
        /* - numbersDiv.clientHeight */
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

    function handlePanMove(e) {
        focusX += e.detail.dx / width;
        focusY += e.detail.dy / height;
        focusX = Math.max(Math.min(1, focusX), 0);
        focusY = Math.max(Math.min(1, focusY), 0);
        dispatch("focuspointchange", { focusX, focusY });
    }
</script>

<!-- the SVG has to be wrapped in DIV otherwise we don’t seem to get the image element bound. -->
<div class="focus-point">
    <svg class="im" {width} {height} viewBox="0 0 {width} {height}">
        <image xlink:href={src} {width} {height} bind:this={image} />
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
        <circle
            use:pannable
            cx={focusX * width}
            cy={focusY * height}
            r={32}
            stroke-width="1"
            stroke="#B0A"
            fill="rgba(187, 0, 170, 0.1)"
            on:panmove={handlePanMove} />
    </svg>
</div>
