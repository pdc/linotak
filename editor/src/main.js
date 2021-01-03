import FocusPoint from './FocusPoint.svelte';

// Extract info from original form …
const form = document.getElementById('focus-ui-form');
const elt = document.getElementById('focus-ui');

const imgElt = elt.querySelector('img');
const src = imgElt.src;
imgElt.remove();

const { width, height, placeholder } = JSON.parse(document.getElementById("imageData").text);

const handleFocusPointChange = (e) => {
    const { detail: { focusX, focusY } } = e;
    console.log('focuschange', focusX, focusY);
    form.focus_x.value = focusX;
    form.focus_y.value = focusY;
}
const handleCropChange = (e) => {
    const { detail: { cropLeft, cropTop, cropWidth, cropHeight } } = e;
    console.log('cropchange', cropLeft, cropTop, cropWidth, cropHeight);
    form.crop_left.value = cropLeft;
    form.crop_top.value = cropTop;
    form.crop_width.value = cropWidth;
    form.crop_height.value = cropHeight;
}

const focus = {
    focusX: form.focus_x.value,
    focusY: form.focus_y.value,
}
const crop = {
    cropLeft: form.crop_left.value,
    cropTop: form.crop_top.value,
    cropWidth: form.crop_width.value,
    cropHeight: form.crop_height.value,
}

const app = new FocusPoint({
    target: elt,
    props: {
        src,
        width,
        height,
        ...focus,
        ...crop,
        placeholder,
    },
});
app.$on('focuspointchange', handleFocusPointChange);
app.$on('cropchange', handleCropChange);

export default app;
