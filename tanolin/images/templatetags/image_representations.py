"""Template tags for image representations."""

from django import template

register = template.Library()


IMAGE_TEMPLATE = template.Template("""{% spaceless %}
    {% if representation %}
        <img src="{{ representation.content.url }}" {% if srcset %}srcset="{{srcset}}" sizes="{{sizes}}"{% endif %}
            {% if image.with_class %}class="{{ image.with_class }}" {% endif %}width="{{ representation.width }}" height="{{ representation.height }}"
            alt="">
    {% endif %}
{% endspaceless %}""")


@register.filter
def square_representation(value, arg):
    """Tag filter that renders an image as a square of a given size.

    Value is am Image instance or None. Arg is the size in CSS pixels.

    Usage: {{ someimage|square_representation:75 }}
    """
    representations = value and sorted(
        {
            r for r in (
                value.find_square_representation(arg * f)
                for f in [1, 2, 3]
            )
            if r
        },
        key=lambda r: r.width)
    context = template.Context({
        'image': value,
        'representations': representations,
        'representation': representations and representations[0],
        'srcset': ', '.join('%s %dw' % (r.content.url, r.width) for r in representations) if representations and len(representations) > 1 else None,
        'sizes': '%dpx' % arg,
    })
    print(context)
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
