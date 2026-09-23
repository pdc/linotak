---
title: Naked signals?
author: Damian Cugley
tags:
- JavaScript
---

Do I want to rewrite the picture editor using naked Signals?


## Why rewrite?

The old code was written years ago in [Svelte].
Svelte has changed unrecognizably since then. So when it stopped working after
I moved the my site to a new server I thought the first step before debugging
it would be to port it to the new version. But after I came back from another
break I discovered UI had forgotten the syntax of both old and new Svelte
enough that I couldn’t even work out how far I had got with the porting.

The problem is that I do not use Svelte in my daily work, so I am not
keeping up with the Svelte-specific lore needed to keep track of my code.
Rewriting it in React (the webdev framework used in my day job) does not
solve this, since we have our own special way of using React that would
not work for this itty bitty project.

The solution I am attempting is to write in plain JavaScript (or TypeScript),
avoiding using a framework at all. It’s a simple enough widget that
it might not be so bad, and the advantage will be that the code
will still be reasonably comprehensible to future me using just my JavaScript
knowledge.


## What is Signals?

Modern JavaScript frameworks emphasize a convention that information moves
in one direction. Changes to application state flow out to the user interface
(represented by the DOM). Messages are triggered by user actions, and flow
inwards to change the state.

```
[State] → [Computed] → (Update DOM) → [DOM]
                     ↘︎
   ↑                   (Update form) → [Form]

  (Update state) ← [Event] ← (User action)
```

The React framework works by having a function re-generate (a copy of) the entire DOM
each time the state changes. Frameworks like Vue and Svelte have compiled
templates that track which state affects which bits of the DOM, so they can
react to state changes by making only the necessary changes. This is important
when changes to the DOM of an HTML document are relatively slow.

[Signals] is an emergent JavaScript API for the underlying mechanism required
to track ‘reactive’ state. One day frameworks might be reengineered to use
it as a common foundation, making them faster and perhaps allowing sharing of
components. The API is not intended to be used directly by application developers.

So my plan is to use Signals directly to develop my application.


## Building with naked signals

The brief outline is as follows:

1. Create `Signal.State` instances for the user’s current _crop_ and _focus_
1. Render the HTML + SVG for the user interface in its neutral state
1. Create effects that update the SVG when the state changes
1. Add event handlers tracking the user’s dragging of the control points
  and updating the `Signal.State` instances with new values


### Creating state

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

We have a separate state for the dynamically changing representation while the
user is dragging a control point. When this is defined it replaces the static
values. When the user operation ends, the dynamic value is copied in to the
static state.


### Initial rendering

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
automatically when the window is resized.

The function intentionally does not depend on any other signals:
we do not want to be rerunning the whole render function continually
while the user drags a crop corner.


### Effects

In this context an _effect_ is a mechanism for executing a function that depends
on one or more signals, re-executing it when the signals are updated.
This uses a cunning watch mechanism that means we can just write the function
and assume it magically gets re-run when necessary.

For example, given a function `assign` that updates a form item (inverse of the
`aquire` helper function above) the effects for updating the form as the state
changes looks like this

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

We are careful to read all the signals that this function uses at the top of the
function so that the dependency-tracking mechanism has the information it needs.

The cropped-out areas are obscured with four translucent grey rectangles.
In an attempt to avoid making the code too clever, there is one effect for each
element. The simples is the top rectangle; its `x`, `y`, and `width` attributes
never change, only its height:

```TypeScript
effect(() => {
  const { height } = sizePixels.get();
  const { top: cropTop } = crop.get();

  const rectElt = document.getElementById("cropTop");
  rectElt.setAttribute("height", cropTop * height);
});
```

There is one of these little functions for each of the rects and for the three
control points and the preview frames.

Event functions can return a function that is called to undo the effect. This will
also be called immediately before re-running the effect function. In our app
it is only used in the render effect.


## Event handlers

The convention of direct-manipulation user interfaces is that the user sees a
preview of the outcome while they drag the control points, but it can be cancelled,
reverting back to how it was before. We will do this by having an _dynamic_ crop
value that is set only while the points are being moved. When the mouse button
is released (or the touching finger lifted off the screen), the active value
is copied in to the static state.

In this simple app this means the event handlers have one job: calculating a new
valid state for the crop and focus point. They have no display code.

The `addEventListener` calls are done as part of the rendering step.


## Tests

Ahem.

Without a framework we don’t really have components that can be used by Storybook.
So the UI testing consists of the `index.html` which is faked up to be like the
locator-image-edit form of the main site. Luckily we only have the one ‘component‘
so we can get by without Storybook.

The code that calculates a new value value of crop/focus given the start state
and the changes from the user’s mouse or touch interaction is broken out in to
its own function, which allows for testing that dragging outside the UI still
results in a valid new state.



[Signals]: https://github.com/tc39/proposal-signals
[Svelte]: https://svelte.dev
