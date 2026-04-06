# -*- coding: utf-8 -*-
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class ZohoSecurityManager:
    """
    Gerenciador de integracao com Zoho Directory API.
    Verifica se um e-mail @anagma.com.br existe e esta ATIVO no servidor Zoho.
    """

    @staticmethod
    def _get_access_token():
        """Obtem um novo Access Token usando o Refresh Token configurado."""
        url = "https://accounts.zoho.com/oauth/v2/token"
        params = {
            "refresh_token": getattr(settings, 'ZOHO_REFRESH_TOKEN', ''),
            "client_id": getattr(settings, 'ZOHO_CLIENT_ID', ''),
            "client_secret": getattr(settings, 'ZOHO_CLIENT_SECRET', ''),
            "grant_type": "refresh_token"
        }
        try:
            response = requests.post(url, params=params, timeout=10)
            data = response.json()
            return data.get("access_token")
        except Exception as e:
            logger.error(f"Erro ao renovar Token Zoho: {e}")
            return None

    @classmethod
    def validar_usuario_ativo(cls, email):
        """
        Consulta o Zoho Directory para confirmar a existencia e status do usuario.
        Retorna True apenas se o usuario for localizado e estiver 'Active'.
        """
        # Se for um superusuario ou ambiente de teste sem chaves, podemos ignorar (opcional)
        if not getattr(settings, 'ZOHO_ORG_ID', None):
            logger.warning("ZOHO_ORG_ID nao configurado. Ignorando validacao Zoho.")
            return True

        token = cls._get_access_token()
        if not token:
            return False

        org_id = settings.ZOHO_ORG_ID
        # Endpoint oficial do Zoho Directory para consulta de usuario unico
        url = f"https://directory.zoho.com/api/v1/organization/{org_id}/users/{email}"
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {token}"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # O Zoho retorna o status da conta. Verificamos se e 'Active'
                status = data.get("status", "").lower()
                return status == "active"
            elif response.status_code == 404:
                logger.warning(f"Usuario {email} nao encontrado no Zoho.")
                return False
            else:
                logger.error(f"Erro na API Zoho ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"Falha de conexao com Zoho API: {e}")
            return False
