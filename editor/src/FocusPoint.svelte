<script>
    import { createEventDispatcher, onMount } from "svelte";
    import { pannable } from "./pannable.js";

    export let src; // URL reference to a representation of the image being edited.
    export let width; // Dimensions of the source image.
    export let height;
    // Initial or corrent value of the focus point.
    export let focusX = 0.5;
    export let focusY = 0.5;
    // Initial size of crop rectangle, if known. These are all fractions of width or height respectively.
    export let cropLeft = 0.0;
    export let cropTop = 0.0;
    export let cropWidth = 1.0;
    export let cropHeight = 1.0;
    export let placeholder = "#999";

    const cropLeft0 = cropLeft;
    const cropTop0 = cropTop;
    const cropWidth0 = cropWidth;
    const cropHeight0 = cropHeight;

    const r = 32; // Size of target circle.

    const dispatch = createEventDispatcher();

    // Size of Ooble crop preview.
    $: [oobleWidth, oobleHeight] = cropSize(
        1.0,
        cropWidth * width,
        cropHeight * height
    );
    $: oobleX = focusX * (cropWidth * width - oobleWidth);
    $: oobleY = focusY * (cropHeight * height - oobleHeight);

    // Mastodon has a different way to determine the crop rectangle.
    $: [mastoWidth, mastoHeight] = cropSize(
        16.0 / 9.0,
        cropWidth * width,
        cropHeight * height
    );
    let mastoX, mastoY;
    $: if (mastoWidth === cropWidth * width) {
        mastoX = 0;
        mastoY = Math.min(
            cropHeight * height - mastoHeight,
            Math.max(0, focusY * cropHeight * height - 0.5 * mastoHeight)
        );
    } else {
        mastoX = Math.min(
            cropWidth * width - mastoWidth,
            Math.max(0, focusX * cropWidth * width - 0.5 * mastoWidth)
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
        focusX = Math.max(Math.min(1, +focusX + e.detail.dx / width), 0);
        focusY = Math.max(Math.min(1, +focusY + e.detail.dy / height), 0);
        dispatch("focuspointchange", { focusX, focusY });
    }

    const handleCropLeftTopPanMove = (e) => {
        const newLeft = +cropLeft + e.detail.dx / width;
        cropLeft = Math.max(Math.min(1.0 - r / width, newLeft), 0.0);
        const newTop = +cropTop + e.detail.dy / height;
        cropTop = Math.max(Math.min(1.0 - r / height, newTop), 0.0);
        cropWidth = Math.max(Math.min(1.0 - cropLeft, +cropWidth), r / width);
        cropHeight = Math.max(Math.min(1.0 - cropTop, +cropHeight), r / width);
    };
    const handleCropWidthHeightPanMove = (e) => {
        const newWidth = +cropWidth + e.detail.dx / width;
        cropWidth = Math.max(Math.min(1.0 - cropLeft, newWidth), r / width);
        const newHeight = +cropHeight + e.detail.dy / height;
        cropHeight = Math.max(Math.min(1.0 - cropTop, newHeight), r / height);
    };
    const handeCropPanEnd = (e) => {
        dispatch("cropchange", { cropLeft, cropTop, cropWidth, cropHeight });
    };
</script>

<!-- the SVG has to be wrapped in DIV otherwise we don’t seem to get the image element bound. -->
<div class="focus-point">
    <svg class="im" {width} {height} viewBox="0 0 {width} {height}">
        <rect {width} {height} fill={placeholder} />
        <image
            xlink:href={src}
            x={cropLeft0 * width}
            y={cropTop0 * height}
            width={cropWidth0 * width}
            height={cropHeight0 * height} />
        <rect {width} height={cropTop * height} fill="rgba(0, 0, 0, 0.25)" />
        <rect
            {width}
            y={(+cropTop + +cropHeight) * height}
            height={(1 - cropTop - cropHeight) * height}
            fill="rgba(0, 0, 0, 0.25)" />
        <rect
            width={cropLeft * width}
            y={cropTop * height}
            height={cropHeight * height}
            fill="rgba(0, 0, 0, 0.25)" />
        <rect
            x={(+cropLeft + +cropWidth) * width}
            width={(1 - cropLeft - cropWidth) * width}
            y={cropTop * height}
            height={cropHeight * height}
            fill="rgba(0, 0, 0, 0.25)" />
        <circle
            use:pannable
            cx={cropLeft * width}
            cy={cropTop * height}
            {r}
            stroke-width="1"
            stroke="#F30"
            fill="rgba(255, 51, 0, 0.1)"
            on:panmove={handleCropLeftTopPanMove}
            on:panend={handeCropPanEnd}
            cursor="move" />
        <circle
            use:pannable
            cx={(+cropLeft + +cropWidth) * width}
            cy={(+cropTop + +cropHeight) * height}
            {r}
            stroke-width="1"
            stroke="#EF0"
            fill="rgba(238, 255, 0, 0.1)"
            cursor="nwse-resize"
            on:panend={handeCropPanEnd}
            on:panmove={handleCropWidthHeightPanMove} />
        <g transform="translate({cropLeft * width}, {cropTop * height})">
            <rect
                x={mastoX + 0.5}
                y={mastoY + 0.5}
                width={mastoWidth - 1}
                height={mastoHeight - 1}
                stroke-width="1"
                stroke="#F56"
                fill="none" />
            <rect
                x={oobleX + 0.5}
                y={oobleY + 0.5}
                width={oobleWidth - 1}
                height={oobleWidth - 1}
                stroke-width="1"
                stroke="#0BA"
                fill="none" />
            <circle
                use:pannable
                cx={focusX * cropWidth * width}
                cy={focusY * cropHeight * height}
                {r}
                stroke-width="1"
                stroke="#B0A"
                fill="rgba(187, 0, 170, 0.1)"
                on:panmove={handlePanMove} />
        </g>
    </svg>
</div>
