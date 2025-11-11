# src/api/get_logs.py
import os
import json
from typing import Optional, List, Dict, Any
import sys

# Framework FastAPI
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# --- VERCEL PATH FIX (STILL REQUIRED) ---
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)
# --- FIM DA MODIFICAÇÃO ---

# --- INÍCIO DA MODIFICAÇÃO PRISMA ---
from lib.prisma_client import Prisma # REMOVED 'register'
# --- FIM DA MODIFICAÇÃO PRISMA ---


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
#  Endpoint da API FastAPI (Refatorado para PRISMA)
# ==============================================================================

# REMOVED: register(app) - This line was causing the error

@app.get("/")
async def handle_get_logs(job_id: Optional[str] = Query(None)):
    """
    Lida com a busca de logs por job_id.
    """
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id é obrigatório.")
        
    db = Prisma()
    
    try:
        await db.connect()
        log_entries = await db.ingestionlogs.find_many(
            where={'job_id': job_id},
            order={'timestamp': 'asc'}
        )
        
        # Formata a saída para corresponder ao que o frontend espera
        logs_formatted = [
            {"type": log.log_type, "text": log.message}
            for log in log_entries
        ]
        
        return JSONResponse(
            status_code=200,
            content={'status': 'success', 'logs': logs_formatted}
        )
        
    except Exception as e:
        error_message = f"Falha ao buscar logs: {str(e)}"
        print(f"--- ERRO CRÍTICO (get_logs): {error_message} ---")
        raise HTTPException(
            status_code=500,
            detail={'status': 'error', 'message': error_message}
        )
    finally:
        if db.is_connected():
            await db.disconnect()