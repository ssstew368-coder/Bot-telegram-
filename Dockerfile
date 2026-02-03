# Utilise une image Python officielle légère
FROM python:3.11-slim

# Définit le répertoire de travail
WORKDIR /app

# Copie tous les fichiers de ton repo dans le conteneur
COPY . .

# Installe les dépendances (si tu as un requirements.txt)
# Si tu n'en as pas encore → crée-le avec : pip freeze > requirements.txt (depuis ton ordi local)
RUN pip install --no-cache-dir -r requirements.txt

# Si ton bot a besoin de paquets système (ex: pour certaines libs comme cryptography, pillow, etc.)
# RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Lance ton script (remplace pa.py par le vrai nom si différent)
CMD ["python", "pa.py"]
