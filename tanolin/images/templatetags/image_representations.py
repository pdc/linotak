"""Template tags for image representations."""

from django import template

from ..size_spec import SizeSpec


register = template.Library()


IMAGE_TEMPLATE = template.Template("""{% spaceless %}
    {% if representation %}
        <img src="{{ representation.content.url }}" {% if srcset %}srcset="{{srcset}}" sizes="{{sizes}}"{% endif %}
            {% if image.with_class %}class="{{ image.with_class }}" {% endif %}width="{{ representation.width }}" height="{{ representation.height }}"
            alt="">
    {% endif %}
{% endspaceless %}""")

SVG_TEMPLATE = template.Template("""{% spaceless %}
    <svg width="{{ width }}px" height="{{ height }}px" viewBox="0 0 {{ width }} {{ height }}">
        <image width="{{ width }}" height="{{ height }}" xlink:href="{{ image.data_url }}"/>
    </svg>
{% endspaceless %}""")


@register.filter
def square_representation(value, arg):
    """Tag filter that renders an image as a square of a given size.

    Value is am Image instance or None. Arg is the size in CSS pixels.

    Usage: {{ someimage|square_representation:75 }}
    """
    return _image_representation(value, SizeSpec.of_square(arg))


@register.filter
def representation(value, arg):
    """Tag filter that renders an image at a given CSS size

    Value is a string encoding a size spec.

    Usage: {{ someimage|representation:"300x400" }}
    """
    return _image_representation(value, SizeSpec.parse(arg))


def _image_representation(image, spec):
    if image and image.media_type in ('image/svg+xml', 'image/svg'):
        context = template.Context({
            'image': image,
            'width': spec.width,
            'height': spec.height
        })
        return SVG_TEMPLATE.render(context)
    representations = image and sorted(
        {r for r in (image.find_representation(spec.enlarged(f)) for f in [1, 2, 3]) if r},
        key=lambda r: r.width)
    srcset_needed = representations and len(representations) > 1
    context = template.Context({
        'image': image,
        'representations': representations,
        'representation': representations and representations[0],
        'srcset': ', '.join('%s %dw' % (r.content.url, r.width) for r in representations) if srcset_needed else None,
        'sizes': (
            '@media (max-width: %dpx) 100vh, %dpx' % (representations[0].width, representations[0].width)
            if srcset_needed else None
        ),
    })
    return IMAGE_TEMPLATE.render(context)


@register.filter
def with_class(value, arg):
    """Tag filter that adds a class to an image entity.

    Value is am Image instance or None. Arg is the CSS class(s) separated by spaces.

    Usage: {{ someimage|with_class:"loc-fine" }}
    """
    if value:
        value.with_class = arg
    return value
