import logging
import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Configuration du logging ---

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialisation FastAPI ---

app = FastAPI(
    title="API Certification FNE",
    description="Récupère la certification d'une facture via l'API FNE Label Impact",
    version="1.0.0"
)

# --- Modèles de données ---

class CertificationRequest(BaseModel):
    sToken: str
    sNoFacture: str

class CertificationResponse(BaseModel):
    token: str
    numero_facture: str
    reference_fne: str | None
    url_qr: str | None

# --- Logique métier ---

def recuperer_certification(sToken: str, sNoFacture: str) -> dict | None:
    url = "https://fne.label-impact.com:9006/API_FacturesCertifiées"
    payload = {"sToken": sToken, "sNoFacture": sNoFacture}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.error("Réponse non-JSON reçue : %s", response.text[:200])
            raise HTTPException(
                status_code=502,
                detail="Le serveur FNE a retourné du HTML au lieu de JSON — token expiré ou URL incorrecte"
            )

        data = response.json()

        if not data.get("bSucces"):
            logger.warning("Erreur API FNE : %s", data.get("sMessage"))
            return None

        factures = data.get("tabFactures", [])
        if not factures:
            logger.warning("Aucune facture trouvée pour : %s", sNoFacture)
            return None

        facture = factures[0]
        return {
            "token": sToken,
            "numero_facture": sNoFacture,
            "reference_fne": facture.get("sReference"),
            "url_qr": facture.get("sTokenCertif"),
        }

    except HTTPException:
        raise

    except (requests.exceptions.RequestException, ValueError) as e:
        logger.error("Erreur lors de la récupération : %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Erreur de connexion au serveur FNE : {str(e)}"
        )

# --- Endpoints ---

@app.get("/")
def accueil():
    return {"message": "API FNE opérationnelle", "version": "1.0.0"}


@app.post("/certification", response_model=CertificationResponse)
def get_certification(body: CertificationRequest):
    resultat = recuperer_certification(body.sToken, body.sNoFacture)

    if resultat is None:
        raise HTTPException(
            status_code=404,
            detail="Certification introuvable ou erreur API FNE"
        )

    return resultat


# --- Lancement (production) ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

---

## `requirements.txt`
```
fastapi
uvicorn
requests
pydantic
```

---

## `Procfile` (pour Railway)
```
web: uvicorn code:app --host 0.0.0.0 --port $PORT
```

---

## Structure de ton dossier
```
C:\Applications\FNE\
├── code.py
├── requirements.txt
└── Procfile