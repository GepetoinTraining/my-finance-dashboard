# src/api/get_logs.py
import os
import json
import psycopg2
import psycopg2.extras
from typing import Optional

# Framework FastAPI
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
app = FastAPI(
    title="Log API",
    description="Busca os logs de ingestão.",
    docs_url="/docs" # /api/get_logs/docs
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
#  Classe de Gerenciamento do DB (Simplificada)
# ==============================================================================
class DatabaseManager:
    def __init__(self):
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise Exception("Variável de ambiente DATABASE_URL não definida.")
            
    def get_logs(self, job_id: str) -> list:
        """Busca todos os logs para um job_id específico, ordenados por tempo."""
        logs = []
        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT log_type, message, timestamp
                        FROM ingestion_logs
                        WHERE job_id = %s
                        ORDER BY timestamp ASC
                        """,
                        (job_id,)
                    )
                    results = cur.fetchall()
                    for row in results:
                        logs.append({
                            "type": row["log_type"],
                            "text": row["message"]
                        })
            return logs
        except Exception as e:
            print(f"Erro ao buscar logs: {e}")
            raise 

# ==============================================================================
#  Endpoint da API FastAPI
# ==============================================================================
# O roteador da Vercel já nos colocou em /api/get_logs.
# Então, o endpoint que o FastAPI precisa criar é a RAIZ (/).
@app.get("/")
async def handle_get_logs(job_id: Optional[str] = Query(None)):
    """
    Lida com a busca de logs por job_id.
    """
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id é obrigatório.")
        
    db = DatabaseManager()
    
    try:
        logs = db.get_logs(job_id)
        return JSONResponse(
            status_code=200,
            content={'status': 'success', 'logs': logs}
        )
        
    except Exception as e:
        error_message = f"Falha ao buscar logs: {str(e)}"
        print(f"--- ERRO CRÍTICO (get_logs): {error_message} ---")
        raise HTTPException(
            status_code=500,
            detail={'status': 'error', 'message': error_message}
        )