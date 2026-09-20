---
title: Image editor interface
author: Damian Cugley
tags:
- JavaScript
---

Linotak creates thumbnails from images. We want them to be specific sizes, so
we will be cropping to the desired aspect ratio and resizing. Cropping an image
automatically is not great because it probably ruins the composition and might
crop out the important part of the image.

To try to mitigate this Linotak enables the editor to choose a _focus point_ for
the image. This is used select which part of the image is used, hopefully allowing
it to create a better thumbnail.


## Crop and focus point

The information required is a *crop* and a *focus point*. Both are specified
as fractions of the width or height of the image. The default focus point
is at (50% 50%). The default crop starts at top left (0% 0%) and extends
the full width and height (100% 100%).

The focus point controls how the thumbnail is extracted. The algorithm Linotak
uses is to extract a square such that the focus point has the same
relative position. For example, given an image and a focus point at (33% 67%),
the thumbnail will have the same part of the image at its position (33% 67%).

This is different from the Mastodon algorithm. This extracts a 16:9 proportioned
area that is as close to centred on the focus point as possible while staying
inside the image boundaries.

The thumbnail section will extend from left to right edge of the image when the
image is taller than it is wide, and from top to bottom otherwise. This is usually
what we want. Sometimes it will be convenient to crop out an area of dead space
first. This is what the crop setting is used for. It crops the source image before
the thumbnail is extracted.


## Interfacing with Django

The interface with
the backend code is the Django form itself: the JavaScript updates form items
corresponding to the point that the user has dragged in the UI. This means

- No need for additional UI elements to tell user the coordinates, since they
  will be visible in the form;
- Data is sent to the to the backend through Django’s normal form-handling
  mechanism.

The UI is initialized from the form as well, so it shows the existing crop and
focus point, if any, from the start. It gets the image source needed to display
the image in the UI from the image element on the page.
