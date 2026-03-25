from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserRegistrationForm(UserCreationForm):
    nome_completo = forms.CharField(max_length=255, required=True, label="Como quer ser chamado")
    email = forms.EmailField(required=True, label="E-mail Anagma")

    class Meta:
        model = CustomUser
        fields = ('username', 'nome_completo', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        # Regra de Negócio Estrita: Apenas domínio oficial Anagma
        if not email.lower().endswith('@anagma.com.br'):
            raise forms.ValidationError("Apenas e-mails corporativos oficiais (terminados em '@anagma.com.br') são permitidos para auto-cadastro.")
        return email
