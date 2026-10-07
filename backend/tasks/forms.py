from django import forms
from .models import Income


class IncomeForm(forms.ModelForm):

    class Meta:
        model = Income
        fields = ['source', 'amount', 'date', 'description']

        widgets = {
            'source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter income source'
            }),

            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount',
                'step': '0.01',
                'min': '0'
            }),

            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description (optional)',
                'rows': 4
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']

        if amount <= 0:
            raise forms.ValidationError(
                'Income amount must be greater than zero.'
            )

        return amount