from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import WorkerForm
from .models import Worker


@login_required
def dashboard(request):
    return render(request, "ValdytiAPP/dashboard.html")


class WorkerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Worker
    permission_required = "valdyti.view_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_list.html"
    context_object_name = "workers"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(job_title__icontains=query)
            )
        return queryset


class WorkerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Worker
    form_class = WorkerForm
    permission_required = "valdyti.add_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_form.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojas pridėtas.")
        return super().form_valid(form)


class WorkerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Worker
    form_class = WorkerForm
    permission_required = "valdyti.change_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_form.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojo informacija atnaujinta.")
        return super().form_valid(form)


class WorkerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Worker
    permission_required = "valdyti.delete_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_confirm_delete.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojas ištrintas.")
        return super().form_valid(form)
