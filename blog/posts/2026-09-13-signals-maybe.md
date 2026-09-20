title: Naked signals?
author: Damian Cugley
tags:
- JavaScript

Do I want to rewrite the picture editor using naked Signals?

## Why rewrite?

The picture editor does two things: it lets the editor drag points
about to set the crop and focus point of an image, and it updates
a form that can be submitted to the Django backend to use this data.

The current code was written in [Svelte] but in an old version of the
language. Svelte has changed unrecognizably since then and so
I started rewriting it. Now I have returned and I have forgotten
how to write in Svelte again so the partially rewritten code is
more or less illegible and I am effectively starting over.

The problem is that I do not use Svelte in my daily work, so I am not
keeping up with the incremental changes to the framework over time, and
also the framework has a lot of internal lore that I do not retain.

Perhaps the solution is to write in plain JavaScript (or TypeScript),
avoiding using a framework at all. It’s a simple enough widget that
it might not be so bad, and the advantage will be that the code
will still be reasonably comprehensible to future me.


## What is Signals

[Signals] is an emergent JavaScript API to handle dependent, reactive
state in web frameworks. Frameworks like Vue and Svelt and the rest
need a mechanism where you set a value for some state in one
place and it knows which bits of the DOM to update in response;
Signals is an
attempt to create a common API for this sort of thing.

So the gist of my plan for the editor is that the mouse handler
events update state signals. The position of the control points on the page
is calculated in computed signals. The writing of the coordinates
in to the SVG elements happens in an ‘effect’ function, which is
automatically rerun when the signals it depends on are updated.


## Building with naked signals

To start with we create `Signal.State` instances for the things that
the user can edit, and supply starting values. For example,
the crop & focus point, which start out with values acquired from
the form:

```TypeScript
const crop = new Signal.State<Rect>({
  left: acquire("crop_left", 0.0),
  top: acquire("crop_top", 0.0),
  width: acquire("crop_width", 1.0),
  height: acquire("crop_height", 1.0),
});
const focus = new Signal.State<Point>({
  x: acquire("focus_x", 0.5),
  y: acquire("focus_y", 0.5),
});
```

Where the function `acquire` wraps access to the text
items in the form.

We supply an `effect` function which executes a function to update some part
of the page, and then watches the signals it depends on so it can rerun it
when they are updated.

```TypeScript
effect(() => {
  const { left, top, width, height } = crop.get();
  assign("crop_left", left);
  assign("crop_top", top);
  assign("crop_width", width);
  assign("crop_height", height);
});
effect(() => {
  const { x, y } = focus.get();
  assign("focus_x", x);
  assign("focus_y", y);
});
```

Similar functions the translucent grey rectangle (with `id` value `cropTop`) that masks
out some of the cropped image:

```TypeScript
effect(() => {
  const { height } = sizePixels.get();
  const { top: cropTop } = crop.get();
  const rectElt = document.getElementById("cropTop");
  if (!rectElt) {
    return;
  }
  rectElt.setAttribute("height", cropTop * height);
});
```


## Rendering the UI

With Vue and Svelte the programmer supplies an HTML template and the compiler
splits in to a skeleton that can be rendered once and the mutable parts that
are updated in response to changes in state. For this app we are doing this
division by hand.

The user interface consists of an SVG element with the source image (or part of it)
and the control points and two frames superimposed on it. Our interaction does
not require adding or removing elements—the control points are directly manipulated
by the user. This will work by updating attributes on the SVG elements that
control their position.

THe simplest way to render a UI is to assign a templated string to
`outerElt.outerHTML`:

```TypeScript
function render() {
  const { width, height } = sizePixels.get();

  const outerElt = document.getElementById("focusPoint") || imageElt;
  outerElt.outerHTML = `
    <div class="focus-point" id="focusPoint">
      <svg class="im" width=${width} height=${height} viewBox="0 0 ${width} ${height}" style="display: block">
        <rect width=${width} height=${height} fill="${placeholder}" />
        … more SVG goes here …
      </svg>
    </div>
  `;

  … add event listeners …

  return () => { … remove event listeners … }
}
```

The dimensions of the UI are acquired from a signal `sizePixels`. This allows it to change
automatically when the window is resized. This creates a fresh UI
each time, but we expect this to be rare. In normal usage this function is called
exactly once.

The function intentionally does not depend on any other signals. The control points
here have their default positions.
We do not want to be rerunning the whole render function continually
while the user drags a crop corner.


## Interaction

The convention of direct-manipulation user interfaces is that the user sees a
preview of the outcome while they drag the control points, but it can be cancelled,
reverting back to how it was before. We will do this by having an ‘active’ crop
value that is set only while the points are being moved. When the mouse button
is released, the active value is copied in to the `crop` state.

In this simple app this means the event handlers have one job: calculating a new
valid state for the crop and focus point. They have no display code.

We already have code for draggable control points in the old implementation.
That version raised custom events; we just need to change it to instead set state
signals.

To do

- Port across the touch-event handlers
- Add change-event handlers to form items
- Cancel


## Interface with Django

Most web frameworks expect to be the whole app—the enclosing HTML page is
little more than a shell for loading the JavaScript and rendering the `App`
component.

We are doing something like this but a little different. The page starts with the
source image and a Django form where the crop and focus point dimensions can
be edited. This way if the JavaScript fails to load the form is still usable.
The code in `main.ts` will find the HTML elements and create the UI, replacing
the image with the SVG element. As the user manipulates the control points in
the UI, the form is updated with the new coordinates.

As a result when the user clicks the Submit button the values are uploaded to the
server and processed as a normal Django form. No need for separate API!

To do

- Deployment
- Test on real server


## Tests

Ahem.

Without a framework we don’t really have components that can be used by Storybook.
So the UI testing consists of the `index.html` which is faked up to be like the
locator-image-edit form of the main site. Luckily we only have the one ‘component‘.

The code that calculates new valid crop / focus status given a change in one of
the control points is probably the most in need of unit testing. It is currently
buried several layers deep in functions within functions, but it could be factored
out in to a testable pure function.

To do

- Spin out a geometry-calculating module that can be unit tested
- Tests for calculating the next crop+focus
- Tests for calculating Mastodon and Linotak frame coordinates


[Signals]: https://github.com/tc39/proposal-signals
[Svelte]: https://svelte.dev
