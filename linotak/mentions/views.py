"""Views for webmentjons.

The only essential one is the one for creating incoming mentions.
"""

from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView

from .forms import IncomingForm
from .models import Incoming


class IncomingDetail(DetailView):
    """View of an individual mention. Mostly useful for debugging!"""

    model = Incoming


@method_decorator(csrf_exempt, name="dispatch")
class IncomingCreate(FormView):
    form_class = IncomingForm
    template_name = "mentions/incoming_form.html"

    def form_valid(self, form):
        """Caller has submitted reasonable stuff."""
        self.instance = form.save(self.request.META.get("HTTP_USER_AGENT"))
        response = TemplateResponse(
            self.request,
            "mentions/incoming_detail.html",
            {"incoming": self.instance},
            status=201,
        )
        response["Location"] = self.instance.get_absolute_url()
        return response
