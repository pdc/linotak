import App from './App.svelte';

// Extract info from original form …
const form = document.getElementById('focus-ui-form');
const focusX = form.focus_x.value;
const focusY = form.focus_y.value;
const elt = document.getElementById('focus-ui');
const labelElt = elt.querySelector('label');
const label = labelElt.innerText;
const imgElt = elt.querySelector('img');
const src = imgElt.src;
const width = imgElt.width;
const height = imgElt.height;

// … and replace it with editor UI.
labelElt.remove();
imgElt.remove();
form.focus_x.remove();
form.focus_y.remove();
const app = new App({
    target: elt,
    props: {
        src,
        width,
        height,
        focusX,
        focusY,
        label,
    }
});

export default app;
