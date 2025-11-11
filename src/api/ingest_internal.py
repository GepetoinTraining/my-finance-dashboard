# src/api/ingest_internal.py
import os
import json
import uuid
import tempfile
from datetime import datetime
from typing import cast, IO, Any, Optional, List, Dict
import sys

# Framework FastAPI
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
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
# Import the generated Prisma client
from lib.prisma_client import Prisma # REMOVED 'register'
from lib.prisma_client.models import InternalPayments, InternalReceivables
# --- FIM DA MODIFICAÇÃO PRISMA ---

# --- INÍCIO DA MODIFICAÇÃO PARSER ---
# Import our new internal parser
from lib.parsers.internal_parser import parse_pagamentos, parse_recebimentos
# --- FIM DA MODIFICAÇÃO PARSER ---


# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
app = FastAPI(
    title="Internal Ingestion API",
    description="Lida com o parsing e ingestão de relatórios internos (pagamentos/recebimentos).",
    docs_url="/docs" 
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
#  Lógica de Background Task
# ==============================================================================
async def process_file_task(job_id: str, file_path: str, filename: str):
    """Esta função roda em background para ingerir os relatórios internos."""
    
    db = Prisma()
    await db.connect()
    
    # Helper async para logar no DB
    async def db_log(log_type: str, message: str):
        print(f"LOG [job: {job_id}] ({log_type}): {message}")
        try:
            await db.ingestionlogs.create(
                data={'job_id': job_id, 'log_type': log_type, 'message': message}
            )
        except Exception as e:
            print(f"Erro ao gravar log no DB: {e}")

    try:
        await db_log("info", f"Arquivo interno recebido: {filename}")
        
        # Determina qual parser usar
        if "pagamentos" in filename.lower():
            await db_log("info", "Usando parser de Pagamentos...")
            parsed_data = parse_pagamentos(file_path, filename)
            
            if parsed_data:
                # Converte os dicts em Pydantic models para o create_many
                data_to_create = [InternalPayments(**d).model_dump() for d in parsed_data]
                
                await db_log("server", f"Iniciando inserção de {len(data_to_create)} pagamentos...")
                result = await db.internalpayments.create_many(
                    data=data_to_create # type: ignore
                )
                await db_log("success", f"Inserção concluída. {result} pagamentos adicionados.")
            else:
                await db_log("info", "Nenhum dado de pagamento encontrado.")

        elif "recebimentos" in filename.lower():
            await db_log("info", "Usando parser de Recebimentos...")
            parsed_data = parse_recebimentos(file_path, filename)
            
            if parsed_data:
                # Converte os dicts em Pydantic models para o create_many
                data_to_create = [InternalReceivables(**d).model_dump() for d in parsed_data]

                await db_log("server", f"Iniciando inserção de {len(data_to_create)} recebimentos...")
                result = await db.internalreceivables.create_many(
                    data=data_to_create # type: ignore
                )
                await db_log("success", f"Inserção concluída. {result} recebimentos adicionados.")
            else:
                await db_log("info", "Nenhum dado de recebimento encontrado.")
        
        else:
            await db_log("error", f"Nome de arquivo não reconhecido: {filename}. Esperado 'pagamentos' or 'recebimentos'.")

        await db_log("success", "Job de ingestão interna finalizado.")
        
    except Exception as e:
        error_message = f"Job falhou: {str(e)}"
        print(f"--- ERRO CRÍTICO (Internal Ingest): {error_message} ---")
        await db_log("error", error_message)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if db.is_connected():
            await db.disconnect()

# ==============================================================================
#  Endpoint da API FastAPI
# ==============================================================================

# REMOVED: register(app) - This line was causing the error

@app.post("/")
async def handle_internal_ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Lida com o upload do relatório, inicia o job em background e retorna um job_id.
    """
    job_id = str(uuid.uuid4())
    db = Prisma()
    
    try:
        # Log inicial rápido
        await db.connect()
        await db.ingestionlogs.create(
            data={
                'job_id': job_id,
                'log_type': 'info',
                'message': 'Job de ingestão interna iniciado.'
            }
        )
        
        with tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=file.filename) as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
        
        background_tasks.add_task(process_file_task, job_id, temp_file_path, file.filename or "unknown_file")
        
        return JSONResponse(
            status_code=200,
            content={'job_id': job_id, 'status': 'processing_started'}
        )
        
    except Exception as e:
        error_message = f"Falha ao iniciar o job: {str(e)}"
        print(f"--- ERRO CRÍTICO (Internal Ingest): {error_message} ---")
        await db.ingestionlogs.create(
            data={
                'job_id': job_id,
                'log_type': 'error',
                'message': error_message
            }
        )
        raise HTTPException(
            status_code=500,
            detail={'job_id': job_id, 'status': 'error', 'message': error_message}
        )
    finally:
        if db.is_connected():
            await db.disconnect()