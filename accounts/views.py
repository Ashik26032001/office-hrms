from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, ProfileUpdateForm
from .models import CustomUser


def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect_by_role(user)
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'accounts/login.html', {'form': form})


def redirect_by_role(user):
    if user.is_admin_or_hr():
        return redirect('/dashboard/')
    return redirect('/employee/dashboard/')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('/accounts/login/')


@login_required
def profile_view(request):
    form = ProfileUpdateForm(instance=request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')

    return render(request, 'accounts/profile.html', {'form': form})
