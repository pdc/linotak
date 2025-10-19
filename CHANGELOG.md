# Change log

## 0.2.0 (2025-10-19)

Added:

- Use oEmbed resources to get poster for YouTube videos. (#45)
- Add image descriptions. Make editor complain if there is no description. (#38)
- Added mentions app to send and receive WebMention notifications.
    - Records incoming mentions but does not process them further yet.

Changed:

- When `img` src is a `data:` URL, ‘download’ it immediately.
- Allow for spurious `px` in `width` and `height` attributes (Instagram).
- Links to prev, next, and feed are duplicated in the HTTP headers.
- Swap Google-hosted fonts for self-hosted alternatives.
- Build with Poetry rather than Pipenv.
- Upgrade to Django 4.0.10.

## 0.1.0 (2025-06-15)

- Web site with notes that may contain links.
- Upgrade to Django 2.2.2
