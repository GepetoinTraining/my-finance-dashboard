import os
import json
import uuid
import tempfile
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import cast, IO, Any, Optional, List, Dict

# Framework FastAPI
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Nossa biblioteca de parser
from lib.parsers.bank_parser import parse_2024, parse_2025

# ==============================================================================
#  Inicialização do App FastAPI
# ==============================================================================
# Vercel irá rodar este arquivo e procurar pela variável 'app'
app = FastAPI(
    title="Ingestion API",
    description="Lida com o parsing e ingestão de extratos bancários.",
    # O Vercel serve isso em /api/ingest, então a rota /docs
    # estará em /api/ingest/docs
    docs_url="/docs" 
)

# Configuração do CORS para permitir o 'vercel dev' (localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
#  Classe de Gerenciamento do DB (Refatorada)
# ==============================================================================
class DatabaseManager:
    """Gerencia a conexão com o banco de dados e as operações de logging/inserção."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            print("ERRO CRÍTICO: Variável de ambiente DATABASE_URL não definida.")
    
    def _get_conn(self):
        if not self.db_url: raise Exception("DATABASE_URL não está configurada.")
        return psycopg2.connect(self.db_url)

    def log(self, log_type: str, message: str):
        """Grava um log no console e no DB."""
        print(f"LOG [job: {self.job_id}] ({log_type}): {message}")
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ingestion_logs (job_id, log_type, message)
                        VALUES (%s, %s, %s)
                        """,
                        (self.job_id, log_type, message)
                    )
                conn.commit()
        except Exception as e:
            print(f"Erro ao gravar log no DB: {e}")

    def _format_date_for_sql(self, date_str: str) -> Optional[str]:
        if not date_str: return None
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError:
            return None

    def insert_transactions(self, transactions: List[Dict[str, Any]]) -> int:
        if not transactions: return 0
        rows_to_insert = [
            (
                self._format_date_for_sql(t["transaction_date"]),
                self._format_date_for_sql(t["posting_date"]),
                t["type"],
                t["amount"],
                t["raw_history_text"],
                t["raw_value_text"],
                t["raw_balance_text"],
                t["source_file_name"],
                json.dumps(t["raw_json_data"])
            ) for t in transactions
        ]
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO bank_transactions (
                        transaction_date, posting_date, type, amount_decimal,
                        raw_history_text, raw_value_text, raw_balance_text,
                        source_file_name, raw_json_data
                    ) VALUES %s
                    """,
                    rows_to_insert
                )
            conn.commit()
        return len(rows_to_insert)

# ==============================================================================
#  Lógica de Background Task
# ==============================================================================
def process_file_task(job_id: str, file_path: str, filename: str):
    """Esta função roda em background para que a API possa retornar o job_id imediatamente."""
    db = DatabaseManager(job_id)
    try:
        db.log("info", f"Arquivo recebido: {filename}")
        db.log("info", f"Arquivo salvo temporariamente em: {file_path}")

        if filename.startswith('ComprovanteBB'):
            db.log("info", "Usando parser 2025 (Regex)...")
            transactions = parse_2025(file_path, filename)
        else:
            db.log("info", "Usando parser 2024 (Tabela)...")
            transactions = parse_2024(file_path, filename)
        
        db.log("server", f"Parsing concluído. {len(transactions)} transações encontradas.")

        if transactions:
            db.log("server", "Iniciando inserção no PostgreSQL...")
            rows_inserted = db.insert_transactions(transactions)
            db.log("success", f"Inserção concluída. {rows_inserted} linhas adicionadas.")
        else:
            db.log("info", "Nenhuma transação encontrada para inserir.")
        
        db.log("success", "Job de ingestão finalizado com sucesso.")
        
    except Exception as e:
        error_message = f"Job falhou: {str(e)}"
        print(f"--- ERRO CRÍTICO: {error_message} ---")
        db.log("error", error_message)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# ==============================================================================
#  Endpoint da API FastAPI
# ==============================================================================
# O roteador da Vercel já nos colocou em /api/ingest.
# Então, o endpoint que o FastAPI precisa criar é a RAIZ (/).
@app.post("/")
async def handle_ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Lida com o upload do arquivo, inicia o job em background e retorna um job_id.
    """
    job_id = str(uuid.uuid4())
    db = DatabaseManager(job_id)
    
    try:
        db.log("info", "Job de ingestão iniciado.")
        
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
        print(f"--- ERRO CRÍTICO (Ingest): {error_message} ---")
        db.log("error", error_message)
        raise HTTPException(
            status_code=500,
            detail={'job_id': job_id, 'status': 'error', 'message': error_message}
        )