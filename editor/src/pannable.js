


/**
 * Svelte action to emit events when user tries to drag element about. 
 * 
 * Originally taken from <https://svelte.dev/tutorial/actions>.
 * TODO. Touch events. 
 * 
 * @param {Element} node 
 */
export function pannable(node) {
    let x;
    let y;
    const touches = []

    function handleMousedown(event) {
        x = event.clientX;
        y = event.clientY;

        node.dispatchEvent(new CustomEvent('panstart', {
            detail: { x, y }
        }));

        window.addEventListener('mousemove', handleMousemove);
        window.addEventListener('mouseup', handleMouseup);
    }

    function handleMousemove(event) {
        const dx = event.clientX - x;
        const dy = event.clientY - y;
        x = event.clientX;
        y = event.clientY;

        node.dispatchEvent(new CustomEvent('panmove', {
            detail: { x, y, dx, dy }
        }));
    }

    function handleMouseup(event) {
        x = event.clientX;
        y = event.clientY;

        node.dispatchEvent(new CustomEvent('panend', {
            detail: { x, y }
        }));

        window.removeEventListener('mousemove', handleMousemove);
        window.removeEventListener('mouseup', handleMouseup);
    }


    /**
     * @param {TouchEvent} event 
     */
    function handleTouchStart(event) {
        // TODO cancel existing panning 
        for (const touch of event.changedTouches) {
            touches.push(copyTouch(touch));
        }
        if (touches.length === 1) {
            event.preventDefault();

            const { clientX, clientY } = touches[0];
            x = clientX;
            y = clientY;

            node.dispatchEvent(new CustomEvent('panstart', { detail: { x, y } }));

            window.addEventListener('touchmove', handleTouchMove);
            window.addEventListener('touchend', handleTouchEnd);
            window.addEventListener('touchcancel', handleTouchCancel);
        }
    }

    function handleTouchMove(event) {
        for (const touch of event.changedTouches) {
            const i = findTouch(touch.identifier);
            if (i >= 0) {
                touches[i] = copyTouch(touch);
            }
        }
        if (touches.length === 1) {
            // TODO check in
            event.preventDefault();

            const { clientX, clientY } = touches[0];
            const dx = clientX - x;
            const dy = clientY - y;
            x = clientX;
            y = clientY;
            node.dispatchEvent(new CustomEvent('panmove', {
                detail: { x, y, dx, dy }
            }));
        }
    }

    function handleTouchEnd(event) {
        terminateTouches(event, 'panend');
    }

    function handleTouchCancel(event) {
        terminateTouches(event, 'pancancel');
    }

    function terminateTouches(event, eventName) {
        if (touches.length === 1 && event.changedTouches.length >= 1 && event.changedTouches[0].identifier === touches[0].identifier) {
            event.preventDefault();

            const { clientX, clientY } = event.changedTouches[0];
            x = clientX;
            y = clientY;

            node.dispatchEvent(new CustomEvent('pancancel', {
                detail: { x, y }
            }));

            window.removeEventListener('touchmove', handleTouchMove);
            window.removeEventListener('touchend', handleTouchEnd);
            window.removeEventListener('touchcancel', handleTouchCancel);
        }

        for (const touch of event.changedTouches) {
            const i = findTouch(touch.identifier);
            if (i >= 0) {
                touches.splice(i, 1);
            }
        }
    }

    function copyTouch({ clientX, clientY, identifier }) {
        return { clientX, clientY, identifier };
    }

    function findTouch(identifier) {
        for (let i = 0; i < touches.length; ++i) {
            if (touches[i].identifier === identifier) {
                return i;
            }
        }
        return -1;
    }

    node.addEventListener('mousedown', handleMousedown);
    node.addEventListener('touchstart', handleTouchStart);

    return {
        destroy() {
            node.removeEventListener('mousedown', handleMousedown);
            node.removeEventListener('touchstart', handleTouchStart);
        }
    };
}