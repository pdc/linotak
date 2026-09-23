import { Signal } from "signal-polyfill";

// I am copy/pasting the warning to not copy/paste!

// This function would usually live in a library/framework, not application code
// NOTE: This scheduling logic is too basic to be useful. Do not copy/paste.
let pending = false;

// A watcher that simply calls the `get()` method of the signals whenever they are dirty.
let w = new Signal.subtle.Watcher(() => {
  if (!pending) {
    pending = true;

    // They are carefully NOT executed inside the Watcher callback because that is not allowed.
    queueMicrotask(() => {
      pending = false;
      for (let s of w.getPending()) {
        // The assumption is that these signals have a side-effect that updates the DOM.
        s.get();
      }
      w.watch(); // This arranges that the same signals be watched again.
    });
  }
});

// An effect effect Signal which evaluates to cb, which schedules a read of
// itself on the microtask queue whenever one of its dependencies might change.
// The callback can return a clean-up function which will be called
// before calling the callback again, or when unwatching the signal.
export default function effect(cb) {
  let destructor;
  let c = new Signal.Computed(() => {
    destructor?.();
    destructor = cb();
  });
  w.watch(c);
  c.get();
  return () => {
    destructor?.();
    w.unwatch(c);
  };
}
