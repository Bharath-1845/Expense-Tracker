from django import forms
from django.contrib.auth.models import User
from .models import MemberProfile


class MemberProfileForm(forms.ModelForm):

    first_name = forms.CharField(
        max_length=100,
        required=True
    )

    last_name = forms.CharField(
        max_length=100,
        required=False
    )

    email = forms.EmailField(
        required=True
    )

    class Meta:
        model = MemberProfile
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address'
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']

            if commit:
                self.user.save()
                profile.save()

        return profile