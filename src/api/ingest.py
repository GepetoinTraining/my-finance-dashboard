# src/api/ingest.py
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
from lib.prisma_client import Prisma, models # REMOVED 'register'
from pydantic import BaseModel

# Our parser library (no changes)
from lib.parsers.bank_parser import parse_2024, parse_2025
# --- FIM DA MODIFICAÇÃO PRISMA ---


# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
app = FastAPI(
    title="Ingestion API",
    description="Lida com o parsing e ingestão de extratos bancários.",
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
#  Gerenciamento do DB (Refatorado para PRISMA)
# ==============================================================================
# Pydantic model for type-hinting the create_many data
class TransactionCreateInput(BaseModel):
    transaction_date: Optional[datetime]
    posting_date: Optional[datetime]
    type: str
    amount_decimal: float
    raw_history_text: str
    raw_value_text: Optional[str]
    raw_balance_text: Optional[str]
    source_file_name: str
    raw_json_data: Optional[Dict[str, Any]]

class DatabaseManager:
    """Gerencia a conexão com o banco de dados e as operações de logging/inserção."""
    
    def __init__(self, job_id: str, db_client: Prisma):
        self.job_id = job_id
        self.db = db_client # Use the passed client

    async def log(self, log_type: str, message: str):
        """Grava um log no console e no DB (agora assíncrono)."""
        print(f"LOG [job: {self.job_id}] ({log_type}): {message}")
        try:
            await self.db.ingestionlogs.create(
                data={
                    'job_id': self.job_id,
                    'log_type': log_type,
                    'message': message
                }
            )
        except Exception as e:
            print(f"Erro ao gravar log no DB: {e}")

    def _format_date_for_prisma(self, date_str: str) -> Optional[datetime]:
        """Converte 'dd/mm/YYYY' para um objeto datetime.datetime."""
        if not date_str: return None
        try:
            # Retorna o objeto datetime, o Prisma cuida da formatação
            return datetime.strptime(date_str, '%d/%m/%Y')
        except ValueError:
            return None

    async def insert_transactions(self, transactions: List[Dict[str, Any]]) -> int:
        if not transactions: return 0
        
        rows_to_insert = [
            TransactionCreateInput(
                transaction_date=self._format_date_for_prisma(t["transaction_date"]),
                posting_date=self._format_date_for_prisma(t["posting_date"]),
                type=t["type"],
                amount_decimal=t["amount"],
                raw_history_text=t["raw_history_text"],
                raw_value_text=t["raw_value_text"],
                raw_balance_text=t["raw_balance_text"],
                source_file_name=t["source_file_name"],
                raw_json_data=t["raw_json_data"]
            ) for t in transactions
        ]
        
        # Converte os modelos Pydantic em dicts para o create_many
        data_to_create = [row.model_dump() for row in rows_to_insert]
        
        result = await self.db.banktransactions.create_many(
            data=data_to_create # type: ignore
        )
        return result

# ==============================================================================
#  Lógica de Background Task (Atualizada para async/await)
# ==============================================================================
async def process_file_task(job_id: str, file_path: str, filename: str):
    """Esta função roda em background para que a API possa retornar o job_id imediatamente."""
    
    # Conecta ao DB
    db_client = Prisma()
    await db_client.connect()
    db = DatabaseManager(job_id, db_client)
    
    try:
        await db.log("info", f"Arquivo recebido: {filename}")
        await db.log("info", f"Arquivo salvo temporariamente em: {file_path}")

        if filename.startswith('ComprovanteBB'):
            await db.log("info", "Usando parser 2025 (Regex)...")
            transactions = parse_2025(file_path, filename)
        else:
            await db.log("info", "Usando parser 2024 (Tabela)...")
            transactions = parse_2024(file_path, filename)
        
        await db.log("server", f"Parsing concluído. {len(transactions)} transações encontradas.")

        if transactions:
            await db.log("server", "Iniciando inserção no PostgreSQL...")
            rows_inserted = await db.insert_transactions(transactions)
            await db.log("success", f"Inserção concluída. {rows_inserted} linhas adicionadas.")
        else:
            await db.log("info", "Nenhuma transação encontrada para inserir.")
        
        await db.log("success", "Job de ingestão finalizado com sucesso.")
        
    except Exception as e:
        error_message = f"Job falhou: {str(e)}"
        print(f"--- ERRO CRÍTICO: {error_message} ---")
        await db.log("error", error_message)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        await db_client.disconnect()

# ==============================================================================
#  Endpoint da API FastAPI (Atualizado para async/await)
# ==============================================================================

# REMOVED: register(app) - This line was causing the error

@app.post("/")
async def handle_ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Lida com o upload do arquivo, inicia o job em background e retorna um job_id.
    """
    job_id = str(uuid.uuid4())
    
    # Log inicial (não-assíncrono) para criar o job o mais rápido possível
    # A task de background usará um gerenciador de DB completo
    db_client = Prisma()
    try:
        await db_client.connect()
        await db_client.ingestionlogs.create(
            data={
                'job_id': job_id,
                'log_type': 'info',
                'message': 'Job de ingestão iniciado.'
            }
        )
    except Exception as e:
         print(f"Erro no log inicial: {e}")
    finally:
        await db_client.disconnect() # Desconecta após o log inicial
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=file.filename) as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
        
        # Adiciona a task async
        background_tasks.add_task(process_file_task, job_id, temp_file_path, file.filename or "unknown_file")
        
        return JSONResponse(
            status_code=200,
            content={'job_id': job_id, 'status': 'processing_started'}
        )
        
    except Exception as e:
        error_message = f"Falha ao iniciar o job: {str(e)}"
        print(f"--- ERRO CRÍTICO (Ingest): {error_message} ---")
        # Log de erro
        try:
            await db_client.connect()
            await db_client.ingestionlogs.create(
                data={
                    'job_id': job_id,
                    'log_type': 'error',
                    'message': error_message
                }
            )
        except Exception as e_log:
            print(f"Erro ao logar erro: {e_log}")
        finally:
            await db_client.disconnect()

        raise HTTPException(
            status_code=500,
            detail={'job_id': job_id, 'status': 'error', 'message': error_message}
        )