#!/bin/bash
# ==============================================================================
# SCRIPT DE DEPLOY - ANAGMA IA (DIGIANA) - ALMALINUX 9 (VPS NVMe 8)
# ==============================================================================
# Autor: Arquiteta e Engenheira Sênior
# Descrição: Instalação e otimização do ambiente Digiana IA.
# ==============================================================================

echo "[1/7] Atualizando sistema e instalando dependências base..."
sudo dnf update -y
sudo dnf install -y epel-release
sudo dnf install -y python3.12 python3.12-devel gcc gcc-c++ make cmake git nginx redis
sudo dnf groupinstall -y "Development Tools"

echo "[2/7] Instalando dependências de Álgebra Linear (Otimização CPU)..."
sudo dnf install -y openblas-devel

echo "[3/7] Configurando Banco de Dados PostgreSQL..."
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql

echo "[4/7] Preparando Ambiente Virtual Python..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[5/7] Compilando Llama-CPP com Otimização OpenBLAS para 4 vCPUs..."
# Isso garante que a Digiana responda com velocidade máxima no AlmaLinux
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python --force-reinstall --upgrade --no-cache-dir

echo "[6/7] Configurando Permissões e Diretórios NVMe..."
mkdir -p assets/models assets/vector_store
chmod -R 755 assets/

echo "[7/7] Configurando Segurança (Firewalld & SELinux)..."
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
# Ajuste do SELinux para permitir que o Nginx converse com o Django
sudo setsebool -P httpd_can_network_connect 1

echo "=============================================================================="
echo " AMBIENTE PRONTO! "
echo " Próximos passos: "
echo " 1. Subir os modelos para assets/models/"
echo " 2. Rodar: python src/manage.py migrate"
echo " 3. Iniciar Gunicorn e Nginx."
echo "=============================================================================="
